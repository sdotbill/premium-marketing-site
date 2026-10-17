"""ZERO-COLD-CALL LOOP — REFEREE rounds (companion to zerocall_loop.py / _loop2.py).

Why this exists: loop2's rounds 7-10 kept promoting, but the promotions ride
two engine artifacts, proven numerically:
  (1) The price-elasticity transform multiplies the inbound close rate by
      (697/price)^1.2 with NO re-clip. At $347, 3.0% of runs close >100% of
      inbound prospects; at $297, 25.6%; at $247, 70.2% (mean close 111%).
      Prices <= $347 are outside the engine's valid region. $397 is the
      lowest price with 0.0% contamination.
  (2) Cadence/volume stretches compound on the artifact bases.
So rounds 7-10's promotions are referee-KILLED, the champion reverts to the
round-6 stack ($397), and convergence is tested properly: referee rounds of
CREDIBLE challengers only (price >= $397, cadence <= x1.5 = the R6 value,
single-step lever stretches) until two consecutive rounds fail to beat the
champion by >1% — the actual convergence rule.

Run AFTER zerocall_loop.py and zerocall_loop2.py. 50,000 paired runs each.
All figures SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
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
_counter = [200]


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
    history = out["history"]
    kill_log = out["kill_log"]

    # --- referee reversal: champion reverts to the round-6 stack ---
    r6 = next(r for r in history if r["name"] == "statewide_x3")
    state = {"price": r6["price"], "knobs": dict(r6["knobs"])}
    champ = r6
    for nm, mech in (("price_297", "elasticity artifact: 25.6% of runs close >100% of inbound at $297"),
                     ("price_247", "elasticity artifact: 70.2% of runs close >100% (mean 111%) at $247"),
                     ("cadence_x2.5", "promoted on the $247 artifact base; also 10 campaigns/mo vs the 4/mo approval gate"),
                     ("everything_x1.1", "promoted on the $247 artifact base")):
        kill_log.append({"name": nm, "round": "7-10 (referee)", "verdict": "KILLED-ARTIFACT",
                         "detail": f"promotion reversed by referee: {mech}"})
    print(f"referee: champion reverts to R6 stack ${state['price']} "
          f"score ${champ['score']/1e6:.2f}M")

    def run_round(rnum, title, entries):
        nonlocal champ, state
        print(f"\n===== REFEREE ROUND {rnum}: {title} =====")
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
        return promoted, results

    rr1 = [("ref_book_show_retention", None,
            {"book_mu": 0.85, "show_mu": 0.90, "churn_scale": 0.75},
            "R6's three near-winners, stacked on the true champion"),
           ("ref_referral_0.01", None, {"referral_rate": 0.01}, "referral doubled, credible base"),
           ("ref_recovery_0.45", None, {"recover_f": 0.45}, "recovery pushed, credible base"),
           ("ref_followup_x1.4", None, {"convo_mult": 1.4, "extra_camp_mo": 100.0},
            "deepest follow-up sequence"),
           ("ref_pool_start_x2", None, {"pool_start_scale": 3.0},
            "starting pool x2 vs champion (total x3 incl. stack's 1.5)"),
           ("ref_sms_month_1", None, {"sms_start": 1},
            "SMS day one; TCPA draw is the only priced risk")]
    promo_a, res_a = run_round(11, "credible stretches on the R6 champion", rr1)

    rr2 = [("ref_content_x2", None, {"inbound_boost": 7.0}, "organic inbound to 13.5/mo"),
           ("ref_camp_churn_x0.2", None, {"camp_churn_scale": 0.2},
            "campaign churn penalty ~erased (1.05x)"),
           ("ref_growth_x4", None, {"pool_growth_scale": 4.0},
            "growth x4 — lead quality unmodeled, noted"),
           ("ref_price_447", 447, {}, "price probe one step up from champion"),
           ("ref_friction_edge", None, {"book_mu": 0.88, "show_mu": 0.92},
            "friction means at their clip edges")]
    promo_b, res_b = run_round(12, "second credible wave", rr2)

    consec_fail = (0 if promo_b else 1) + (0 if (promo_a or promo_b) else 1) if not promo_b else 0
    consec_fail = 0 if promo_b else (1 if promo_a else 2)
    if consec_fail < 2:
        # one more round: stack whatever beat the champion they faced by >0%
        wins = {}
        for rec in res_a + res_b:
            if rec["score"] > champ["score"] * 0.99 and rec["name"] != champ["name"]:
                for k, v in rec["knobs"].items():
                    if state["knobs"].get(k) != v:
                        wins[k] = v
        rr3 = []
        if wins:
            rr3.append(("ref_stack_of_near_winners", None, wins,
                        "every referee near-winner stacked"))
        rr3.append(("ref_price_397_recheck", 397, {}, "champion price sanity recheck"))
        rr3.append(("ref_all_friction_max", None,
                    {"book_mu": 0.88, "show_mu": 0.92, "recover_f": 0.45},
                    "all friction levers maxed together"))
        promo_c, _ = run_round(13, "final combinations", rr3)
        consec_fail = 0 if promo_c else consec_fail + 1

    converged = consec_fail >= 2
    print(f"\nreferee convergence: consecutive no-promotion rounds = {consec_fail}; "
          f"converged = {converged}")

    # Break points in the JSON were last computed at the loop2 $247 artifact
    # champion — invalid for any other config. ALWAYS re-run at the final
    # referee champion.
    if True:
        print("re-running break points at the final referee champion")
        fp, fk = state["price"], dict(state["knobs"])

        def probe(name, delta):
            rec = evaluate("BP3_" + name, fp, {**fk, **delta})
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
    out["referee"] = {"artifact_kills": ["price_297", "price_247", "cadence_x2.5", "everything_x1.1"],
                       "contamination": {"347": "3.0% of runs close >100% of inbound",
                                         "297": "25.6%", "247": "70.2% (mean close rate 111%)",
                                         "397": "0.0% — lowest valid price"}}
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
    print(f"FINAL REFEREE CHAMPION: ${state['price']} | score ${champ['score']/1e6:.2f}M | "
          f"cust {champ['customers_p50']:.0f} | cash P50 ${champ['cash_p50']/1e6:.2f}M | "
          f"converged {converged}")


if __name__ == "__main__":
    main()
