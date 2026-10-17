"""ZERO-COLD-CALL LOOP — continuation rounds 7+ (companion to zerocall_loop.py).

zerocall_loop.py's scripted rounds ended after six straight promotions, which
is NOT the convergence rule (two consecutive rounds with no >1% promotion).
This continuation restores the champion from zerocall_loop_results.json and
keeps throwing challenger rounds — single-lever stretches on the reigning
champion plus stacks of near-winners — until two consecutive rounds produce
no promotion. If the champion moves, the break-point suite is re-run at the
new champion and the JSON is updated in place.

Run AFTER zerocall_loop.py. 50,000 paired runs per challenger.
All figures SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
"""
import json
import os
import sys
import time
import urllib.request

SIM_DIR = "/home/hatch/workspace/sims-unleashed"
RAW = "https://raw.githubusercontent.com/sdotbill/premium-marketing-site/main/sims/"
for _f in ("unleashed_sim.py", "zerocall_sim.py", "zerocall_loop.py"):
    _p = os.path.join(SIM_DIR, _f)
    if not os.path.exists(_p):
        os.makedirs(SIM_DIR, exist_ok=True)
        urllib.request.urlretrieve(RAW + _f, _p)
        print("downloaded", _f, "from GitHub")
sys.path.insert(0, SIM_DIR)

import zerocall_sim as zs  # noqa: E402

OUT = os.path.join(SIM_DIR, "zerocall_loop_results.json")
_counter = [100]


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
    out = json.load(open(OUT))
    state = {"price": out["champion"]["price"], "knobs": dict(out["champion"]["knobs"])}
    champ = {"score": out["champion"]["score"], "customers_p50": out["champion"]["customers_p50"],
             "arr_p50": out["champion"]["arr_p50"], "cash_p10": out["champion"]["cash_p10"],
             "cash_p50": out["champion"]["cash_p50"], "cash_p90": out["champion"]["cash_p90"],
             "prob_cash_positive": out["champion"]["prob_cash_positive"],
             "price": state["price"], "knobs": dict(state["knobs"])}
    champ_start = json.dumps({"price": state["price"], "knobs": state["knobs"]}, sort_keys=True)
    kill_log = out["kill_log"]
    history = out["history"]
    print(f"restored champion: ${state['price']} score ${champ['score']/1e6:.2f}M knobs={state['knobs']}")

    def run_round(rnum, title, entries):
        nonlocal champ, state
        print(f"\n===== ROUND {rnum}: {title} =====")
        cat = champ
        results = []
        for name, price, delta, why in entries:
            knobs = {**state["knobs"], **delta}
            rec = evaluate(name, price if price is not None else state["price"], knobs)
            rec["round"] = rnum
            rec["rationale"] = why
            rec["delta_vs_champion_pct"] = (rec["score"] / cat["score"] - 1) * 100
            results.append(rec)
            history.append(rec)
        best = max(results, key=lambda r: r["score"])
        promoted = best["score"] > cat["score"] * 1.01
        for rec in results:
            if promoted and rec is best:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "PROMOTED",
                                 "detail": f"score ${rec['score']/1e6:.2f}M beat champion "
                                           f"${cat['score']/1e6:.2f}M by {rec['delta_vs_champion_pct']:+.1f}%"})
            else:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "KILLED",
                                 "detail": f"score ${rec['score']/1e6:.2f}M vs champion "
                                           f"${cat['score']/1e6:.2f}M ({rec['delta_vs_champion_pct']:+.1f}%); "
                                           f"{rec['rationale']}"})
        if promoted:
            state = {"price": best["price"], "knobs": best["knobs"]}
            champ = best
            print(f"  ** PROMOTED: {best['name']} — champion score ${champ['score']/1e6:.2f}M")
        else:
            print(f"  no promotion (best {best['name']} {best['delta_vs_champion_pct']:+.1f}%)")
        return promoted

    rounds = [
        (7, "R6 near-winners retested on the new champion + frontier probes", [
            ("book_0.85", None, {"book_mu": 0.85}, "beat the R5 champion solo; untested on R6 champion"),
            ("show_0.90", None, {"show_mu": 0.90}, "beat the R5 champion solo; untested on R6 champion"),
            ("retention_x0.75", None, {"churn_scale": 0.75}, "beat the R5 champion solo; untested on R6 champion"),
            ("book_show_retention_stack", None,
             {"book_mu": 0.85, "show_mu": 0.90, "churn_scale": 0.75}, "the three R6 near-winners stacked"),
            ("price_347", 347, {}, "$347 on the stack (R5's price probe beat its champion but lost its round)"),
            ("price_297", 297, {}, "price floor probe"),
            ("cadence_x2.0", None, {"cad_mult": 2.0}, "8 campaigns/mo — gate fully relaxed"),
            ("pool_growth_x4", None, {"pool_growth_scale": 4.0}, "growth stretch beyond statewide x3"),
            ("referral_0.01", None, {"referral_rate": 0.01}, "referral engine doubled"),
        ]),
        (8, "extremes in every remaining direction", [
            ("sms_month_1", None, {"sms_start": 1}, "SMS from day one (pre-registration risk priced only via TCPA draw)"),
            ("content_x2", None, {"inbound_boost": 7.0}, "organic inbound 6.5 -> 13.5/mo"),
            ("camp_churn_x0.2", None, {"camp_churn_scale": 0.2}, "campaign churn penalty nearly erased (~1.05x)"),
            ("followup_x1.4", None, {"convo_mult": 1.4, "extra_camp_mo": 100.0}, "deepest follow-up sequence"),
            ("recovery_0.45", None, {"recover_f": 0.45}, "no-show recovery pushed to 45%"),
            ("price_247", 247, {}, "deep price floor probe"),
            ("pool_start_x2", None, {"pool_start_scale": 2.0}, "starting pool doubled (list purchase)"),
        ]),
        (9, "last combinations", [
            ("book_0.88_show_0.92", None, {"book_mu": 0.88, "show_mu": 0.92},
             "friction distributions pushed to their clip edges"),
            ("growth_x5", None, {"pool_growth_scale": 5.0}, "max market stretch"),
            ("cadence_x2.5", None, {"cad_mult": 2.5}, "10 campaigns/mo"),
            ("retention_x0.65", None, {"churn_scale": 0.65}, "max retention stretch"),
        ]),
        (10, "final confirmation attempts", [
            ("everything_x1.1", None, {"convo_mult": 1.375, "recover_f": 0.40,
                                        "inbound_boost": 5.0, "referral_rate": 0.0075},
             "fractional stack of the soft levers"),
            ("price_372", 372, {}, "fine price probe just under champion"),
            ("price_422", 422, {}, "fine price probe just over champion"),
        ]),
    ]

    consec_fail = 0
    for rnum, title, entries in rounds:
        if consec_fail >= 2:
            break
        promoted = run_round(rnum, title, entries)
        consec_fail = 0 if promoted else consec_fail + 1
    converged = consec_fail >= 2
    print(f"\nconvergence check: consecutive no-promotion rounds = {consec_fail}; converged = {converged}")

    champ_end = json.dumps({"price": state["price"], "knobs": state["knobs"]}, sort_keys=True)
    if champ_end != champ_start:
        print("\nchampion moved — re-running break points at the final champion")
        fp, fk = state["price"], dict(state["knobs"])

        def probe(name, delta):
            rec = evaluate("BP2_" + name, fp, {**fk, **delta})
            return {"name": name, "delta": delta, "cash_p50": rec["cash_p50"],
                    "prob_cash_positive": rec["prob_cash_positive"], "score": rec["score"]}

        bp = {}
        bp["email_reply_scale"] = [probe(f"email_{s}", {"email_scale": s}) for s in (0.10, 0.05, 0.02)]
        bp["sms_reply_scale"] = [probe(f"sms_{s}", {"sms_scale": s}) for s in (0.5, 0.25, 0.1, 0.05)]
        bp["book_rate_fixed"] = [probe(f"book_{v}", {"book_ovr": v}) for v in (0.10, 0.05)]
        bp["show_rate_fixed"] = [probe(f"show_{v}", {"show_ovr": v}) for v in (0.20, 0.15, 0.10)]
        bp["pool_scale"] = [probe(f"pool_{s}", {"pool_start_scale": s, "pool_growth_scale": s})
                            for s in (0.5, 0.25, 0.1)]
        bp["combined_collapse"] = [probe("combined", {"email_scale": 0.25, "book_ovr": 0.35,
                                                      "show_ovr": 0.45})]
        out["breakpoints"] = bp

    out["converged"] = bool(converged)
    out["champion"] = {"price": state["price"], "knobs": state["knobs"], "score": champ["score"],
                       "customers_p50": champ["customers_p50"], "arr_p50": champ["arr_p50"],
                       "cash_p10": champ["cash_p10"], "cash_p50": champ["cash_p50"],
                       "cash_p90": champ["cash_p90"],
                       "prob_cash_positive": champ["prob_cash_positive"]}
    out["history"] = history
    out["kill_log"] = kill_log
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("\nupdated", OUT)
    print(f"FINAL CHAMPION: ${state['price']} knobs={state['knobs']}")
    print(f"  score ${champ['score']/1e6:.2f}M | cust {champ['customers_p50']:.0f} | "
          f"cash P50 ${champ['cash_p50']/1e6:.2f}M | converged {converged}")


if __name__ == "__main__":
    main()
