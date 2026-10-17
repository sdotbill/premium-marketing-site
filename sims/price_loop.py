"""Price-loop extension for the unleashed sim (Bill, 2026-10-16).

Re-runs Path C (unleashed) at $497 / $697 / $997 (setup+monthly), email-first
sequencing locked (SMS month 4+ with 10DLC), price elasticity on close rates.
Path A is untouched ($697 canon anchor) — the decision is which price Path C
should charge, so only Path C moves.

Pairing: identical seeds (20261016/20261017) across prices => the ONLY difference
between price runs is price (+ elasticity transform). Paired price comparison.

Elasticity model (MODELED, stated): close-rate multiplier em = (697/price)^elast
applied to dial-to-close, inbound close, and closer absolute closes — Path C only.
Reply rates are price-invariant (price doesn't change whether someone replies,
only whether they buy). Optional churn-price link: churn x (price/697)^cpe.

Risk-adjusted score (stated): 0.6*P10 + 0.3*P50 + 0.1*P90 of 36-month cash.
A price with a higher P50 but a collapsed P10 loses by construction.

Convergence: iterate (adversarial critique -> refine -> re-run) until the winner
is unchanged between consecutive iterations AND |dP50 36mo cash| < 10%.
Cap 3 iterations; report honestly if not converged.

All figures SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
"""
import json
import os
import time

import numpy as np

OUT_DIR = "/content/sims"
SRC = open(os.path.join(OUT_DIR, "unleashed_sim.py")).read()
PRICES = (497, 697, 997)


def build_src(price, elast, cpe, tag, flop=False):
    em = (697.0 / price) ** elast
    pr = price / 697.0
    src = SRC

    # A. price constants (Path C only; Path A keeps $697 canon)
    old = "SETUP = 697.0\nMRR_STD = 697.0"
    new = ("SETUP = 697.0\nMRR_STD = 697.0\n"
           f"PRICE_C = {price}.0\n"
           f"ELAST_MULT_C = {em:.6f}\n"
           f"CHURN_PEXP_C = {cpe:.4f}\n"
           f"PRICE_RATIO_C = {pr:.6f}")
    assert old in src, "A: price const anchor missing"
    src = src.replace(old, new)

    # B. elasticity + price applied inside run_path, Path C only (Path A pristine)
    old = '    d2c, inbound_close, churn = P["d2c"], P["inbound_close"], P["churn"]'
    new = ("    em = ELAST_MULT_C if is_c else 1.0\n"
           '    d2c, inbound_close, churn = P["d2c"] * em, P["inbound_close"] * em, P["churn"]\n'
           "    churn = churn * ((PRICE_RATIO_C if is_c else 1.0) ** CHURN_PEXP_C)\n"
           "    MRR_EFF = PRICE_C if is_c else MRR_STD\n"
           "    SETUP_EFF = PRICE_C if is_c else SETUP")
    assert old in src, "B1: unpack anchor missing"
    src = src.replace(old, new)
    old = '    closer_month, closer_closes = P["closer_month"], P["closer_closes"]'
    new = '    closer_month, closer_closes = P["closer_month"], P["closer_closes"] * em'
    assert old in src, "B2: closer anchor missing"
    src = src.replace(old, new)

    # C. price usages -> effective price (Path C only). Murphy's 699.0 stays:
    #    his $697/$697 terms are already negotiated (locked deal).
    #    Maki's re-quote is NOT signed -> her MRR/setup move with the price too.
    assert src.count("* MRR_STD") == 5, f"C: MRR count {src.count('* MRR_STD')}"
    src = src.replace("* MRR_STD", "* MRR_EFF")
    assert src.count("* SETUP") == 2, f"C: SETUP count {src.count('* SETUP')}"
    src = src.replace("* SETUP", "* SETUP_EFF")

    # D. EMAIL-FIRST locked: SMS only month 4+ (10DLC lead time); email from month 1.
    old = ("            sms_sent = np.minimum(cad * SMS_SEG, pool / 3.0)"
           "  # 90-day cooldown")
    new = ("            sms_sent = np.where(m >= 4, np.minimum(cad * SMS_SEG, pool / 3.0), 0.0)"
           "  # EMAIL-FIRST locked: SMS month 4+")
    assert old in src, "D: sms anchor missing"
    src = src.replace(old, new)

    # E. optional flop stress (S1): reply rates at 1/4 — robustness check
    if flop:
        subs = [
            ('np.log(0.012), sigma=0.50, size=n), 0.004, 0.030',
             'np.log(0.003), sigma=0.50, size=n), 0.001, 0.008'),
            ('np.log(0.005), sigma=0.50, size=n), 0.002, 0.012',
             'np.log(0.00125), sigma=0.50, size=n), 0.0005, 0.003'),
        ]
        for o, n_ in subs:
            assert o in src, f"E: flop pattern missing: {o[:40]}"
            src = src.replace(o, n_)

    src = src.replace("unleashed_results.json", f"price_{tag}.json")
    ns = {"__builtins__": __builtins__, "__name__": f"price_{tag}",
          "__file__": os.path.join(OUT_DIR, "unleashed_sim.py")}
    exec(compile(src, "unleashed_sim.py", "exec"), ns)  # noqa: S102 (own sim code)
    return ns["results"]


def summarize(results):
    c = results["paths"]["C"]
    out = {}
    for h in ("12", "24", "36"):
        v = c[h]
        out[h] = {"customers": v["customers"], "arr": v["arr"], "cash": v["cash"],
                  "prob_cash_positive": v["prob_cash_positive"]}
    out["crossover_month_p50"] = c["crossover_month_p50"]
    out["crossover_share_pct"] = c["crossover_share_pct"]
    out["camp_closes_total_p50"] = c["camp_closes_total_p50"]
    out["tcpa_event_share_pct"] = c["tcpa_event_share_pct"]
    return out


def score(s36):
    c = s36["cash"]
    return 0.6 * c["p10"] + 0.3 * c["p50"] + 0.1 * c["p90"]


def run_iteration(tag, elast, cpe, note):
    print(f"\n===== ITERATION {tag}: elast={elast}, churn_pexp={cpe} — {note} =====")
    it = {}
    for p in PRICES:
        t0 = time.time()
        it[p] = summarize(build_src(p, elast, cpe, f"{tag}_{p}"))
        s36 = it[p]["36"]
        print(f"  ${p}: m36 cust {s36['customers']['p50']:.0f} "
              f"({s36['customers']['p10']:.0f}-{s36['customers']['p90']:.0f}) | "
              f"ARR ${s36['arr']['p50']/1e6:.2f}M | "
              f"cash P10/50/90 ${s36['cash']['p10']/1e6:.2f}M / "
              f"${s36['cash']['p50']/1e6:.2f}M / ${s36['cash']['p90']/1e6:.2f}M | "
              f"score ${score(s36)/1e6:.2f}M | cash+ {s36['prob_cash_positive']:.0f}% "
              f"({time.time()-t0:.1f}s)")
    winner = max(it, key=lambda p: score(it[p]["36"]))
    print(f"  --> winner: ${winner} (score ${score(it[winner]['36'])/1e6:.2f}M)")
    return {"elast": elast, "churn_pexp": cpe, "note": note,
            "prices": it, "winner": winner,
            "winner_p50_cash_36": it[winner]["36"]["cash"]["p50"]}


def main():
    iterations = []
    # ITER 1 — central elasticity, no churn-price link
    iterations.append(run_iteration("it1", 0.7, 0.0,
                                    "central: em=(697/p)^0.7 on close rates; replies price-invariant"))

    # ITER 2 — adversarial refinement (see kill-log K11-K14):
    #   stronger elasticity (cold outbound buyers ARE price-sensitive),
    #   mild churn-price link (higher price -> higher expectations -> more churn).
    iterations.append(run_iteration("it2", 1.0, 0.25,
                                    "refined: em=(697/p)^1.0; churn x (p/697)^0.25"))

    w1, w2 = iterations[0]["winner"], iterations[1]["winner"]
    p1, p2 = iterations[0]["winner_p50_cash_36"], iterations[1]["winner_p50_cash_36"]
    converged = (w1 == w2) and (abs(p2 - p1) / p1 < 0.10)
    print(f"\nconvergence check: winner {w1}->{w2}, "
          f"|dP50| = {abs(p2-p1)/p1*100:.1f}% -> {'CONVERGED' if converged else 'NOT converged'}")

    if not converged:
        # ITER 3 — push further in the direction the critique demands
        iterations.append(run_iteration("it3", 1.2, 0.35,
                                        "stress-refine: em=(697/p)^1.2; churn x (p/697)^0.35"))
        w3 = iterations[2]["winner"]
        p3 = iterations[2]["winner_p50_cash_36"]
        converged = (w2 == w3) and (abs(p3 - p2) / p2 < 0.10)
        print(f"convergence check: winner {w2}->{w3}, "
              f"|dP50| = {abs(p3-p2)/p2*100:.1f}% -> "
              f"{'CONVERGED' if converged else 'NOT converged after 3 iterations'}")

    fin = iterations[-1]
    wprice, welast, wcpe = fin["winner"], fin["elast"], fin["churn_pexp"]
    wsum = fin["prices"][wprice]

    # Robustness checks on the final winner (strongest-case-I'm-wrong probes)
    print(f"\n===== ROBUSTNESS on winner ${wprice} =====")
    r_flop = summarize(build_src(wprice, welast, wcpe, "robust_flop", flop=True))
    print(f"  flop replies (1/4 rates): m36 cash P50 ${r_flop['36']['cash']['p50']/1e6:.2f}M, "
          f"P10 ${r_flop['36']['cash']['p10']/1e6:.2f}M, cash+ {r_flop['36']['prob_cash_positive']:.0f}%")
    r_elas = summarize(build_src(wprice, 1.3, wcpe, "robust_elas13"))
    print(f"  very elastic (e=1.3): m36 cash P50 ${r_elas['36']['cash']['p50']/1e6:.2f}M, "
          f"P10 ${r_elas['36']['cash']['p10']/1e6:.2f}M")

    # Valuation inputs from the winner's P10/P50/P90 paths
    val = {"price": wprice, "bands": {}}
    for band, bi in (("p10", "p10"), ("p50", "p50"), ("p90", "p90")):
        c12, c24, c36 = (wsum[h]["cash"][bi] for h in ("12", "24", "36"))
        a36 = wsum["36"]["arr"][bi]
        e1, e2, e3 = c12, c24 - c12, c36 - c24
        r = 0.25
        tv = 3.0 * e3
        dcf = e1 / 1.25 + e2 / 1.25**2 + (e3 + tv) / 1.25**3
        val["bands"][band] = {"arr_36": a36, "cash_36": (c12, c24, c36),
                              "dcf_25pct": dcf,
                              "mult_2x": 2.0 * a36, "mult_3x": 3.0 * a36,
                              "mult_4x": 4.0 * a36}

    out = {"note": "SIMULATIONS / PROJECTIONS — not existing revenue. Collected revenue to date: $0.",
           "scoring": "risk-adjusted 36mo cash = 0.6*P10 + 0.3*P50 + 0.1*P90",
           "email_first": "locked: email from month 1, SMS month 4+ with 10DLC",
           "iterations": iterations,
           "converged": converged,
           "final_winner": wprice,
           "robustness": {"flop_replies_m36": r_flop["36"],
                          "very_elastic_m36": r_elas["36"]},
           "valuation": val}
    with open(os.path.join(OUT_DIR, "price_loop_results.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote", os.path.join(OUT_DIR, "price_loop_results.json"))


if __name__ == "__main__":
    main()
