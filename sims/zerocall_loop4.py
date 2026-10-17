"""ZERO-COLD-CALL LOOP — FINAL: choices-only convergence (companion to
zerocall_loop.py / _loop2.py / _loop3.py).

Referee finding that forces this design: the sim has two kinds of parameters.
  CHOICES — price, pool scale, cadence, SMS start month. Dave/Bill pick them;
  the engine prices the pick (volume vs revenue, caps, TCPA draws).
  WORLD PARAMETERS — book/show means, recovery share, reply->convo multiplier,
  referral rate, inbound lift, churn-program efficacy. Reality picks these;
  Dave can only influence them with unmeasured effect. "Optimizing" a world
  parameter is re-labeling optimism as strategy: rounds 11-13 'promoted' on
  exactly that, and the surface is uphill everywhere (nearly every challenger
  beat the champion it faced), so no honest convergence exists on that surface.

So: world parameters are FROZEN at the base verdict's honest central values
(book 0.70, show 0.78, recovery 0, convo x1.0, referral 0, inbound +0,
churn programs off). The choices ladder runs until two consecutive rounds
produce no >1% promotion — the mandate's convergence rule, applied to the
surface where it means something. The friction-maxed $16.40M config from the
referee rounds is preserved in the JSON as a sensitivity CEILING, not the
champion. Break points are re-run at the final actionable champion.

50,000 paired runs per config. SIMULATIONS / PROJECTIONS. Revenue: $0.
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
_counter = [300]


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
    # preserve the friction-maxed config as a sensitivity ceiling, not champion
    out["world_param_ceiling"] = {
        "note": "Rounds 11-13 champion: every world parameter at its optimistic "
                "edge simultaneously. A sensitivity ceiling, NOT a plan.",
        **out["champion"]}

    state = {"price": 497, "knobs": {}}
    champ = next(r for r in history if r["name"] == "C0_base_497")
    print(f"choices loop starts from C0: $497 score ${champ['score']/1e6:.2f}M, "
          "world parameters frozen at base values")

    def run_round(rnum, entries):
        nonlocal champ, state
        print(f"\n===== CHOICE ROUND {rnum} =====")
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
            if promoted and rec is best:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "PROMOTED",
                                 "detail": f"choices loop: score ${rec['score']/1e6:.2f}M beat "
                                           f"champion ${cat['score']/1e6:.2f}M by "
                                           f"{rec['delta_vs_champion_pct']:+.1f}%"})
            else:
                kill_log.append({"name": rec["name"], "round": rnum, "verdict": "KILLED",
                                 "detail": f"choices loop: score ${rec['score']/1e6:.2f}M vs "
                                           f"champion ${cat['score']/1e6:.2f}M "
                                           f"({rec['delta_vs_champion_pct']:+.1f}%); {rec['rationale']}"})
        if promoted:
            state = {"price": best["price"], "knobs": dict(best["knobs"])}
            champ = best
            print(f"  ** PROMOTED: {best['name']} — champion score ${champ['score']/1e6:.2f}M")
        else:
            print(f"  no promotion (best {best['name']} {best['delta_vs_champion_pct']:+.1f}%)")
        return promoted

    # ROUND 14: cumulative choice stacks (world params frozen at base)
    s2 = {"pool_start_scale": 1.5, "pool_growth_scale": 1.5}
    s3 = {"pool_start_scale": 1.5, "pool_growth_scale": 3.0}
    s4 = {**s3, "sms_start": 2}
    s5 = {**s4, "cad_mult": 1.5}
    r14 = [("ch_price_397", 397, {}, "price one step below base, valid region floor"),
           ("ch_pool_x1.5", 397, dict(s2), "wider market: pool and growth x1.5"),
           ("ch_growth_x3", 397, dict(s3), "statewide sweep growth x3"),
           ("ch_sms_month_2", 397, dict(s4), "SMS fast-tracked to month 2"),
           ("ch_cadence_x1.5", 397, dict(s5), "6 campaigns/mo (relaxes the 4/mo gate — flagged)"),
           ("ch_stack_at_447", 447, dict(s5), "the full choice stack at $447")]
    promo = run_round(14, r14)
    consec_fail = 0 if promo else 1

    # ROUNDS 15+: a fixed ladder of single-choice stretches from the champion
    def ladder():
        p, k = state["price"], state["knobs"]
        ent = []
        if p - 50 >= 397:
            ent.append(("ch_price_down", p - 50, dict(k), "price step down (floor $397 = valid region)"))
        ent.append(("ch_price_up", p + 50, dict(k), "price step up"))
        if k.get("pool_start_scale", 1.0) < 3.0:
            ent.append(("ch_pool_start_up", p, {**k, "pool_start_scale": 3.0}, "starting pool to x3"))
        if k.get("pool_growth_scale", 1.0) < 4.0:
            ent.append(("ch_growth_up", p, {**k, "pool_growth_scale": min(4.0, k.get("pool_growth_scale", 1.0) + 1.0)},
                        "sweep growth +1x"))
        if k.get("cad_mult", 1.0) < 2.0:
            ent.append(("ch_cadence_up", p, {**k, "cad_mult": k.get("cad_mult", 1.0) + 0.5},
                        "cadence +0.5 (gate flag grows)"))
        if k.get("sms_start", 4) > 1:
            ent.append(("ch_sms_earlier", p, {**k, "sms_start": k.get("sms_start", 4) - 1},
                        "SMS one month earlier"))
        return ent

    rnum = 15
    while consec_fail < 2 and rnum <= 18:
        promo = run_round(rnum, ladder())
        consec_fail = 0 if promo else consec_fail + 1
        rnum += 1
    converged = consec_fail >= 2
    print(f"\nchoices-loop convergence: consecutive no-promotion rounds = {consec_fail}; "
          f"converged = {converged}")

    # gate-respecting variant of the final champion (cadence back to x1.0)
    gate = None
    if state["knobs"].get("cad_mult", 1.0) > 1.0:
        gk = {**state["knobs"], "cad_mult": 1.0}
        gate = evaluate("champion_gate_respecting", state["price"], gk)
        gate["note"] = "final champion with cadence restored to the standing 4 campaigns/mo gate"

    # break points at the final actionable champion
    fp, fk = state["price"], dict(state["knobs"])

    def probe(name, delta):
        rec = evaluate("BP4_" + name, fp, {**fk, **delta})
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
    out["breakpoints_at"] = "final actionable (choices-loop) champion"
    out["gate_respecting_champion"] = gate
    out["converged"] = bool(converged)
    out["convergence_note"] = ("Converged on the CHOICES surface (price/pool/cadence/SMS-start) "
                               "at frozen base world parameters, per the mandate rule (two "
                               "consecutive no-promotion rounds). The world-parameter surface "
                               "does not converge — it is a sensitivity surface, reported as "
                               "ceilings, never as the plan.")
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
    print(f"ACTIONABLE CHAMPION: ${fp} knobs={fk}")
    print(f"  score ${champ['score']/1e6:.2f}M | cust {champ['customers_p50']:.0f} | "
          f"cash P10/50/90 ${champ['cash_p10']/1e6:.2f}M/${champ['cash_p50']/1e6:.2f}M/"
          f"${champ['cash_p90']/1e6:.2f}M | converged {converged}")
    if gate:
        print(f"  gate-respecting (cadence x1.0): score ${gate['score']/1e6:.2f}M | "
              f"cash P50 ${gate['cash_p50']/1e6:.2f}M")


if __name__ == "__main__":
    main()
