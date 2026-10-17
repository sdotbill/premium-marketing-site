"""ZERO-COLD-CALL recursive LOOP — run to convergence (Bill, 2026-10-16 22:45).

Takes the base zero-call champion ($497, book~0.70, show~0.78, email-first,
SMS month 4+, aggressive cadence, Genesee pool) and attacks it round by round:
price frontier, funnel quality, scale & retention, stacks, boundary stretches.
Every challenger: 50,000 paired runs (seeds 20261016/20261017), scored on the
house risk-adjusted score = 0.6*P10 + 0.3*P50 + 0.1*P90 of 36-month cash.
Promotion rule: a challenger becomes champion only if it beats the champion's
score by >1%. Convergence: two consecutive rounds with no promotion.
Then break-point hunts at the final champion: minimum email/SMS reply,
minimum book, minimum show, market-size floor, combined-collapse config,
price ceiling.

COLAB: this file is self-contained. If unleashed_sim.py / zerocall_sim.py are
missing next to it, it downloads both from the GitHub repo's sims/ folder,
then runs every round locally in the notebook. No other local files needed.

All figures SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
"""
import json
import os
import sys
import time
import urllib.request

SIM_DIR = "/home/hatch/workspace/sims-unleashed"   # zerocall_sim.OUT_DIR
RAW = "https://raw.githubusercontent.com/sdotbill/premium-marketing-site/main/sims/"
for _f in ("unleashed_sim.py", "zerocall_sim.py"):
    _p = os.path.join(SIM_DIR, _f)
    if not os.path.exists(_p):
        os.makedirs(SIM_DIR, exist_ok=True)
        urllib.request.urlretrieve(RAW + _f, _p)
        print("downloaded", _f, "from GitHub")
sys.path.insert(0, SIM_DIR)

import numpy as np  # noqa: E402

import zerocall_sim as zs  # noqa: E402

OUT = os.path.join(SIM_DIR, "zerocall_loop_results.json")
_counter = [0]


def evaluate(name, price, knobs):
    _counter[0] += 1
    tag = f"L{_counter[0]:02d}_" + "".join(c if c.isalnum() else "_" for c in name)[:28]
    summ, raw, _turn = zs.run_config(price, "zerocall", tag, **knobs)
    sc = zs.score(summ["36"])
    rec = {"name": name, "price": price, "knobs": knobs, "score": sc,
           "customers_p50": summ["36"]["customers"]["p50"],
           "arr_p50": summ["36"]["arr"]["p50"],
           "cash_p10": summ["36"]["cash"]["p10"], "cash_p50": summ["36"]["cash"]["p50"],
           "cash_p90": summ["36"]["cash"]["p90"],
           "prob_cash_positive": summ["36"]["prob_cash_positive"]}
    print(f"    -> {name}: score ${sc/1e6:.2f}M | cust {rec['customers_p50']:.0f} | "
          f"cash P50 ${rec['cash_p50']/1e6:.2f}M")
    return rec


def main():
    t0 = time.time()
    state = {"price": 497, "knobs": {}}
    kill_log = []
    history = []

    print("===== CHAMPION C0: base zero-call verdict config =====")
    champ = evaluate("C0_base_497", state["price"], dict(state["knobs"]))
    history.append({"round": 0, **champ})
    print(f"  champion score ${champ['score']/1e6:.2f}M")

    def run_round(rnum, title, entries):
        """entries: list of (name, price_or_None, knob_delta, rationale)."""
        nonlocal champ, state
        print(f"\n===== ROUND {rnum}: {title} =====")
        champ_at_round = champ
        results = []
        for name, price, delta, why in entries:
            knobs = {**state["knobs"], **delta}
            rec = evaluate(name, price if price is not None else state["price"], knobs)
            rec["round"] = rnum
            rec["rationale"] = why
            rec["delta_vs_champion_pct"] = (rec["score"] / champ_at_round["score"] - 1) * 100
            results.append(rec)
            history.append(rec)
        best = max(results, key=lambda r: r["score"])
        promoted = best["score"] > champ_at_round["score"] * 1.01
        for rec in results:
            if promoted and rec is best:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "PROMOTED",
                                 "detail": f"score ${rec['score']/1e6:.2f}M beat champion "
                                           f"${champ_at_round['score']/1e6:.2f}M by "
                                           f"{rec['delta_vs_champion_pct']:+.1f}% (>1% bar)"})
            else:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "KILLED",
                                 "detail": f"score ${rec['score']/1e6:.2f}M vs champion "
                                           f"${champ_at_round['score']/1e6:.2f}M "
                                           f"({rec['delta_vs_champion_pct']:+.1f}%); {rec['rationale']}"})
        if promoted:
            state = {"price": best["price"], "knobs": best["knobs"]}
            champ = best
            print(f"  ** PROMOTED: {best['name']} — new champion score ${champ['score']/1e6:.2f}M")
        else:
            print(f"  no promotion (best {best['name']} {best['delta_vs_champion_pct']:+.1f}%)")
        return promoted, results

    # ---------- ROUND 1: price frontier ----------
    r1 = [(f"price_{p}", p, {}, "price frontier stretch")
          for p in (397, 597, 797, 1097, 1297)]
    promo1, _ = run_round(1, "price frontier ($397-$1,297)", r1)

    # ---------- ROUND 2: funnel quality ----------
    r2 = [("book_0.80", None, {"book_mu": 0.80}, "booking UX: one-tap slots in every reply"),
          ("show_0.88", None, {"show_mu": 0.88}, "reminder stack + calendar holds lift shows"),
          ("followup_depth", None, {"convo_mult": 1.25, "extra_camp_mo": 75.0},
           "5-touch follow-up sequence (+$75/mo infra) lifts reply->convo 25%"),
          ("noshow_recovery_0.30", None, {"recover_f": 0.30},
           "automated rebook sequence recovers 30% of no-shows"),
          ("sms_month_2", None, {"sms_start": 2}, "10DLC fast-tracked: SMS from month 2")]
    promo2, res2 = run_round(2, "funnel quality", r2)

    # ---------- ROUND 3: scale & retention ----------
    r3 = [("statewide_growth_x2", None, {"pool_growth_scale": 2.0},
           "lead sweeps expand statewide: pool growth 1,080 -> 2,160/mo"),
          ("bigger_pool_x1.5", None, {"pool_start_scale": 1.5, "pool_growth_scale": 1.5},
           "buy/import lists: pool and growth x1.5"),
          ("camp_churn_fix", None, {"camp_churn_scale": 0.4},
           "onboarding program: campaign churn penalty 1.25x -> ~1.10x"),
          ("retention_program", None, {"churn_scale": 0.85}, "base churn x0.85 (QBRs, Dave QC)"),
          ("content_machine", None, {"inbound_boost": 3.5},
           "video/content velocity: organic inbound 6.5 -> 10/mo"),
          ("referral_engine", None, {"referral_rate": 0.005},
           "every-job ask system: 0.5% of base closes a referral monthly")]
    promo3, res3 = run_round(3, "scale & retention", r3)

    # ---------- ROUND 4: stacks ----------
    winners = {}
    for rec in res2 + res3:
        for k, v in rec["knobs"].items():
            if state["knobs"].get(k) != v and rec["score"] > 0:
                pass
    # lever deltas that individually beat the champion they faced (>0%, pre->1% bar)
    faced = {}
    lever_wins = {}
    champ_score_timeline = [history[0]["score"]]
    # reconstruct: res2 faced the post-R1 champion; res3 faced post-R2 champion.
    # Simpler robust rule: a lever counts as a winner if its rec beat the C0 score.
    c0 = history[0]["score"]
    for rec in res2 + res3:
        if rec["score"] > c0:
            for k, v in rec["knobs"].items():
                if {**{}}.get(k) is None:
                    lever_wins[k] = v
    # only keep levers not already in the champion's knobs at same value
    lever_wins = {k: v for k, v in lever_wins.items() if state["knobs"].get(k) != v}
    r4 = []
    if lever_wins:
        r4.append(("stack_all_winners", None, dict(lever_wins),
                   "every individually-winning lever stacked"))
        if "referral_rate" in lever_wins:
            d = {k: v for k, v in lever_wins.items() if k != "referral_rate"}
            if d:
                r4.append(("stack_minus_referral", None, d,
                           "stack without the most invented lever (referrals)"))
        if "inbound_boost" in lever_wins:
            d = {k: v for k, v in lever_wins.items() if k != "inbound_boost"}
            if d:
                r4.append(("stack_minus_content", None, d,
                           "stack without the content-velocity assumption"))
    else:
        r4 = [("cadence_x1.5", None, {"cad_mult": 1.5}, "approval gate relaxed to 6 campaigns/mo"),
              ("cadence_x0.75", None, {"cad_mult": 0.75}, "gentler cadence: deliverability bet")]
    promo4, _ = run_round(4, "stacks", r4)

    # ---------- ROUND 5: stretch the champion ----------
    cp = state["price"]
    r5 = [("price_minus_50", max(297, cp - 50), {}, "probe below-champion price"),
          ("price_plus_50", cp + 50, {}, "probe above-champion price"),
          ("cadence_x1.5", None, {"cad_mult": 1.5}, "approval gate relaxed to 6 campaigns/mo")]
    if state["knobs"].get("recover_f", 0) > 0:
        r5.append(("recovery_0.45", None, {"recover_f": 0.45}, "recovery pushed to 45%"))
    else:
        r5.append(("book_0.85", None, {"book_mu": 0.85}, "booking pushed harder"))
    if state["knobs"].get("referral_rate", 0) > 0:
        r5.append(("referral_0.01", None, {"referral_rate": 0.01},
                   "referral engine at 1% of base/mo"))
    else:
        r5.append(("followup_x1.4", None, {"convo_mult": 1.4, "extra_camp_mo": 100.0},
                   "deeper sequence: convo x1.4"))
    promo5, _ = run_round(5, "stretch the champion", r5)

    # ---------- ROUND 6: extremes (only if still promoting) ----------
    promos = [promo1, promo2, promo3, promo4, promo5]
    consec_fail = 0
    for p in reversed(promos):
        if not p:
            consec_fail += 1
        else:
            break
    promo6 = False
    if consec_fail < 2:
        r6 = [("book_0.85", None, {"book_mu": 0.85}, "extreme booking"),
              ("show_0.90", None, {"show_mu": 0.90}, "extreme show rate"),
              ("statewide_x3", None, {"pool_growth_scale": 3.0}, "pool growth x3"),
              ("retention_x0.75", None, {"churn_scale": 0.75}, "extreme retention")]
        promo6, _ = run_round(6, "extremes", r6)
        promos.append(promo6)
        consec_fail = 0 if promo6 else consec_fail + 1
    converged = consec_fail >= 2 or (len(promos) >= 6 and not promos[-1] and not promos[-2])
    print(f"\nconvergence: consecutive no-promotion rounds at end = {consec_fail}; "
          f"converged = {converged}")

    # ---------- BREAK POINTS at the final champion ----------
    print("\n===== BREAK POINTS at final champion =====")
    fp, fk = state["price"], dict(state["knobs"])

    def probe(name, delta):
        rec = evaluate("BP_" + name, fp, {**fk, **delta})
        return {"name": name, "delta": delta, "cash_p50": rec["cash_p50"],
                "prob_cash_positive": rec["prob_cash_positive"], "score": rec["score"]}

    bp = {}
    bp["email_reply_scale"] = [probe(f"email_{s}", {"email_scale": s})
                               for s in (0.10, 0.05, 0.02)]
    bp["sms_reply_scale"] = [probe(f"sms_{s}", {"sms_scale": s})
                             for s in (0.5, 0.25, 0.1, 0.05)]
    bp["book_rate_fixed"] = [probe(f"book_{v}", {"book_ovr": v}) for v in (0.10, 0.05)]
    bp["show_rate_fixed"] = [probe(f"show_{v}", {"show_ovr": v}) for v in (0.20, 0.15, 0.10)]
    bp["pool_scale"] = [probe(f"pool_{s}", {"pool_start_scale": s, "pool_growth_scale": s})
                        for s in (0.5, 0.25, 0.1)]
    bp["combined_collapse"] = [probe("combined", {"email_scale": 0.25, "book_ovr": 0.35,
                                                  "show_ovr": 0.45})]

    # price curve at C0 knobs: base-verdict JSON (497/697/997) + round 1 evals
    curve = {}
    try:
        base = json.load(open(os.path.join(SIM_DIR, "zerocall_results.json")))
        for p in ("497", "697", "997"):
            z = base["prices"][p]["zerocall"]
            curve[p] = {"customers_p50": z["36"]["customers"]["p50"],
                        "cash_p50": z["36"]["cash"]["p50"],
                        "score": base["prices"][p]["zerocall_score"]}
    except Exception as e:
        print("base curve load failed:", e)
    for rec in history:
        if rec["round"] == 1:
            curve[str(rec["price"])] = {"customers_p50": rec["customers_p50"],
                                        "cash_p50": rec["cash_p50"], "score": rec["score"]}
    curve = dict(sorted(curve.items(), key=lambda kv: int(kv[0])))

    out = {"note": "SIMULATIONS / PROJECTIONS — not existing revenue. Collected revenue to date: $0.",
           "promotion_rule": "score (0.6*P10+0.3*P50+0.1*P90 of 36mo cash) must beat champion by >1%",
           "convergence_rule": "two consecutive rounds with no promotion",
           "converged": bool(converged),
           "champion": {"price": fp, "knobs": fk, "score": champ["score"],
                        "customers_p50": champ["customers_p50"], "arr_p50": champ["arr_p50"],
                        "cash_p10": champ["cash_p10"], "cash_p50": champ["cash_p50"],
                        "cash_p90": champ["cash_p90"],
                        "prob_cash_positive": champ["prob_cash_positive"]},
           "history": history, "kill_log": kill_log, "breakpoints": bp,
           "price_curve_c0_knobs": curve,
           "seconds": round(time.time() - t0, 1)}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote", OUT)
    print(f"FINAL CHAMPION: ${fp} knobs={fk}")
    print(f"  score ${champ['score']/1e6:.2f}M | cust {champ['customers_p50']:.0f} | "
          f"cash P10/50/90 ${champ['cash_p10']/1e6:.2f}M/${champ['cash_p50']/1e6:.2f}M/"
          f"${champ['cash_p90']/1e6:.2f}M | cash+ {champ['prob_cash_positive']:.1f}%")
    return out


if __name__ == "__main__":
    main()
