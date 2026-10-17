"""ZERO-COLD-CALL LOOP — Round 21: TRUE increments past the volume max
(companion to zerocall_loop5.py).

Correction to loop5: its round-20 ladder re-applied the values the round-19
winner already held (cadence 2.5 / growth 5 / start 4), so its +0.0% results
were the champion racing itself — not evidence of a plateau. This round
increments PAST those values (cadence 3.0, growth 6, pool start 5, all
combined, price probes). If nothing beats the champion by >1%, rounds 20+21
count as the two consecutive no-promotion rounds ONLY for the increments
round 21 actually tested — stated plainly in the verdict. Break points are
re-run at the final champion either way.
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
_counter = [500]


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
    k = state["knobs"]
    print(f"round 21 from volume-max champion ${state['price']} score ${champ['score']/1e6:.2f}M knobs={k}")
    kill_log.append({"name": "round20_ladder", "round": 20, "verdict": "VOIDED",
                     "detail": "loop5 round 20 re-applied the champion's own knob values "
                               "(no-op configs); its +0.0% results are not evidence. "
                               "Superseded by round 21 true increments."})

    entries = [
        ("u_cadence_x3.0", state["price"], {**k, "cad_mult": 3.0}, "12 campaigns/mo"),
        ("u_growth_x6", state["price"], {**k, "pool_growth_scale": 6.0}, "sweep growth x6"),
        ("u_pool_start_x5", state["price"], {**k, "pool_start_scale": 5.0}, "starting pool x5"),
        ("u_all_beyond_max", state["price"],
         {**k, "cad_mult": 3.0, "pool_growth_scale": 6.0, "pool_start_scale": 5.0},
         "every volume lever one step past the max, together"),
        ("u_price_497", 497, dict(k), "price back up to base on the maxed stack"),
    ]
    results = []
    for name, price, knobs, why in entries:
        rec = evaluate(name, price, knobs)
        rec["round"] = 21
        rec["rationale"] = why
        rec["delta_vs_champion_pct"] = (rec["score"] / champ["score"] - 1) * 100
        results.append(rec)
        history.append(rec)
    best = max(results, key=lambda r: r["score"])
    promoted = best["score"] > champ["score"] * 1.01
    for rec in results:
        kill_log.append({"name": rec["name"], "round": 21,
                         "verdict": "PROMOTED" if (promoted and rec is best) else "KILLED",
                         "detail": f"score ${rec['score']/1e6:.2f}M vs champion "
                                   f"${champ['score']/1e6:.2f}M ({rec['delta_vs_champion_pct']:+.1f}%); "
                                   f"{rec['rationale']}"})
    if promoted:
        state = {"price": best["price"], "knobs": dict(best["knobs"])}
        champ = best
        print(f"  ** PROMOTED: {best['name']} — ${champ['score']/1e6:.2f}M (loop continues in principle)")
    else:
        print(f"  no promotion (best {best['name']} {best['delta_vs_champion_pct']:+.1f}%)")
    # Convergence accounting, stated exactly: round 19 promoted; round 20 voided;
    # round 21 is the first VALID consecutive no-promotion round if not promoted.
    converged = False
    out["convergence_note"] = (
        "Loop terminated by referee after 21 rounds. Formal status: the mandate's "
        "two-consecutive-no-promotion rule was met on the world-parameter surface "
        "never (it is a sensitivity surface — see world_param_ceiling) and on the "
        "choices ladder it was approached asymptotically: gains decayed +17% -> "
        "+1.0% -> +1.1% per stretch, the volume surface went flat at the caps "
        "(round 21 pending), and the only lever still moving the score at the "
        "boundary is cadence — a standing-rule (governance) variable, not a "
        "model discovery. Remaining headroom, if any, is inside the 1% bar or "
        "behind rule changes only Bill can make.")

    fp, fk = state["price"], dict(state["knobs"])

    def probe(name, delta):
        rec = evaluate("BP5_" + name, fp, {**fk, **delta})
        return {"name": name, "delta": delta, "cash_p50": rec["cash_p50"],
                "prob_cash_positive": rec["prob_cash_positive"], "score": rec["score"]}

    bp = {}
    bp["email_reply_scale"] = [probe(f"email_{s}", {"email_scale": s}) for s in (0.10, 0.05, 0.02)]
    bp["sms_reply_scale"] = [probe(f"sms_{s}", {"sms_scale": s}) for s in (0.5, 0.25, 0.1, 0.05)]
    bp["book_rate_fixed"] = [probe(f"book_{v}", {"book_ovr": v}) for v in (0.10, 0.05)]
    bp["show_rate_fixed"] = [probe(f"show_{v}", {"show_ovr": v}) for v in (0.20, 0.15, 0.10)]
    bp["pool_scale"] = [probe(f"pool_{s}", {"pool_start_scale": fk.get("pool_start_scale", 1.0) * s,
                                            "pool_growth_scale": fk.get("pool_growth_scale", 1.0) * s})
                        for s in (0.5, 0.25, 0.1)]
    bp["combined_collapse"] = [probe("combined", {"email_scale": 0.25, "book_ovr": 0.35,
                                                  "show_ovr": 0.45})]
    out["breakpoints"] = bp
    out["breakpoints_at"] = "final ladder champion (loop5/loop6)"
    out["converged"] = converged
    out["champion"] = {"price": fp, "knobs": fk, "score": champ["score"],
                       "customers_p50": champ["customers_p50"], "arr_p50": champ["arr_p50"],
                       "cash_p10": champ["cash_p10"], "cash_p50": champ["cash_p50"],
                       "cash_p90": champ["cash_p90"],
                       "prob_cash_positive": champ["prob_cash_positive"]}
    out["history"] = history
    out["kill_log"] = kill_log
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("\nupdated", OUT)
    print(f"FINAL LADDER CHAMPION: ${fp} knobs={fk} score ${champ['score']/1e6:.2f}M "
          f"| cust {champ['customers_p50']:.0f} | cash P50 ${champ['cash_p50']/1e6:.2f}M "
          f"| R21 promoted={promoted}")


if __name__ == "__main__":
    main()
