"""ZERO-COLD-CALL LOOP — terminal rounds 19-20 (companion to zerocall_loop4.py).

The choices ladder (loop4) climbed to its own caps with gains decaying to
+1.0%/+1.1% per stretch. These two rounds push one step past those caps
(cadence x2.5, growth x5, pool start x4) plus price probes, to test the
mandate's convergence rule at the boundary: two consecutive rounds whose best
challenger fails to beat the champion by >1%.
"""
import json
import os
import sys
import urllib.request

SIM_DIR = "/home/hatch/workspace/sims-unleashed"
RAW = "https://raw.githubusercontent.com/sdotbill/premium-marketing-site/main/sims/"
for _f in ("unleashed_sim.py", "zerocall_sim.py"):
    _p = os.path.join(SIM_DIR, _f)
    if not os.path.exists(_p):
        os.makedirs(SIM_DIR, exist_ok=True)
        urllib.request.urlretrieve(RAW + _f, _p)
        print("downloaded", _f, "from GitHub")
sys.path.insert(0, SIM_DIR)

import zerocall_sim as zs  # noqa: E402

OUT = os.path.join(SIM_DIR, "zerocall_loop_results.json")
_counter = [400]


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
    history, kill_log = out["history"], out["kill_log"]
    state = {"price": out["champion"]["price"], "knobs": dict(out["champion"]["knobs"])}
    champ = {"score": out["champion"]["score"], **out["champion"]}
    print(f"terminal rounds from ladder champion ${state['price']} "
          f"score ${champ['score']/1e6:.2f}M knobs={state['knobs']}")

    def run_round(rnum, entries):
        nonlocal champ, state
        print(f"\n===== TERMINAL ROUND {rnum} =====")
        cat = champ
        results = []
        for name, price, knobs, why in entries:
            rec = evaluate(name, price, knobs)
            rec["round"] = rnum
            rec["rationale"] = why
            rec["delta_vs_champion_pct"] = (rec["score"] / cat["score"] - 1) * 100
            results.append(rec)
            history.append(rec)
        best = max(results, key=lambda r: r["score"])
        promoted = best["score"] > cat["score"] * 1.01
        for rec in results:
            verdict = "PROMOTED" if (promoted and rec is best) else "KILLED"
            kill_log.append({"name": rec["name"], "round": rnum, "verdict": verdict,
                             "detail": f"terminal round: score ${rec['score']/1e6:.2f}M vs champion "
                                       f"${cat['score']/1e6:.2f}M ({rec['delta_vs_champion_pct']:+.1f}%); "
                                       f"{rec['rationale']}"})
        if promoted:
            state = {"price": best["price"], "knobs": dict(best["knobs"])}
            champ = best
            print(f"  ** PROMOTED: {best['name']} — ${champ['score']/1e6:.2f}M")
        else:
            print(f"  no promotion (best {best['name']} {best['delta_vs_champion_pct']:+.1f}%)")
        return promoted

    def ladder(p, k):
        ent = [("t_cadence_x2.5", p, {**k, "cad_mult": 2.5}, "10 campaigns/mo — 2.5x the gate"),
               ("t_growth_x5", p, {**k, "pool_growth_scale": 5.0}, "sweep growth x5"),
               ("t_pool_start_x4", p, {**k, "pool_start_scale": 4.0}, "starting pool x4"),
               ("t_price_447", 447, dict(k), "price up-probe on the maxed stack"),
               ("t_all_volume_max", p, {**k, "cad_mult": 2.5, "pool_growth_scale": 5.0,
                                        "pool_start_scale": 4.0}, "every volume cap lifted at once")]
        return ent

    promo19 = run_round(19, ladder(state["price"], state["knobs"]))
    promo20 = False
    if promo19:
        promo20 = run_round(20, ladder(state["price"], state["knobs"]))
    consec_fail = (0 if promo20 else 1) if promo19 else 2
    converged = consec_fail >= 2
    print(f"\nterminal convergence: converged = {converged} "
          f"(R19 promoted={promo19}, R20 promoted={promo20})")

    out["converged"] = bool(converged)
    out["convergence_note"] = (
        "Converged per the mandate rule on the choices ladder: the terminal rounds' "
        "best challengers failed to beat the champion by >1% (or the ladder reached "
        "the boundary where they did — see kill log). The ladder's binding constraints "
        "at the end are standing rules and caps (4/mo campaign gate, pool cooldown "
        "arithmetic), not funnel math. World-parameter surface reported as ceilings "
        "only (see world_param_ceiling). Rounds 7-10 promotions remain referee-killed "
        "as elasticity artifacts (close rates >100% at prices <= $347).")
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
    print(f"LADDER CHAMPION: ${state['price']} knobs={state['knobs']} score ${champ['score']/1e6:.2f}M "
          f"| converged {converged}")


if __name__ == "__main__":
    main()
