"""ZERO-COLD-CALL Monte Carlo — Premium Marketing Solutions (Bill, 2026-10-16).

Question: can PMS be profitable with ZERO cold calls — nobody dials anybody —
acquisition 100% inbound/automated, Bill only closing booked appointments?

Built on the unleashed engine (unleashed_sim.py) + the nextpath winning build
($497 it3 params: ELAST=1.2, CPE=0.35, email-first, SMS month 4+ 10DLC,
aggressive cadence, flat pricing). Two modes per price, paired seeds
(20261016 shared / 20261017 campaign — identical draws; new ZC draws are
APPENDED to the campaign stream so all upstream draws stay paired):

  dialbill  = the current with-dialing winner mechanics (Bill dials, setters
              dial — nextpath_loop.py's "dialbill" build, verbatim transforms).
  zerocall  = dialbill MINUS the phone, PLUS appointment friction:
    Z1. Bill dials = 0 (closer-only, nextpath transform E).
    Z2. Setter outbound closes = 0 on Path C (new_outbound zeroed — setters
        were dialing staff; their appointment output dies with the phone).
    Z3. No dialing setters on Path C: setter payroll zeroed, setter2
        appointment multiplier removed (both is_c-guarded; Path A canon intact).
    Z4. NEW — appointment friction (no human chases anyone):
        book_rate ~ N(0.70, 0.10) clip 0.45-0.90: share of engaged
          conversations / inbound prospects that actually BOOK (Dave offers
          times in-thread, or prospect clicks the website booking link).
          Basis: these prospects already replied and conversed — reply_to_convo
          (25% mean) already filtered for intent; booking is the low-friction
          next step when times are offered directly.
        show_rate ~ N(0.78, 0.08) clip 0.55-0.92: share of booked
          appointments that SHOW. Basis: published local-services/B2B no-show
          rates run ~20-30% with no phone chasing; automated reminders (texts/
          emails from Dave — automation, not cold calls) keep PMS at the
          better end: mean 22% no-show. Honest friction, not 100%.
        Applied: campaign closes x book x show; organic inbound closes
          x book x show; hired-closer closes x show (rooms are pre-booked).
    Z5. Monthly cumulative-cash tracking (first month P50 cum cash >= 0).

Price sweep $497/$697/$997 (setup+monthly matched, price_loop discipline),
50,000 runs per config. Sensitivity at the zero-call winning price:
break-even scales/floors for email reply rate, book rate, show rate
(P50 36-month cash > 0 criterion).

All figures SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
"""
import json
import os
import time

import numpy as np

OUT_DIR = "/home/hatch/workspace/sims-unleashed"
SRC = open(os.path.join(OUT_DIR, "unleashed_sim.py")).read()

ELAST, CPE = 1.2, 0.35          # converged price-loop params (it3)


def build_source(price, mode, tag, email_scale=1.0, book_ovr=0.0, show_ovr=0.0):
    """mode in {'dialbill', 'zerocall'}. Returns transformed engine source."""
    src = SRC
    em = (697.0 / price) ** ELAST
    pr = price / 697.0

    # A. price constants + ZC knobs (Path C only; Path A keeps $697 canon)
    old = "SETUP = 697.0\nMRR_STD = 697.0"
    new = ("SETUP = 697.0\nMRR_STD = 697.0\n"
           f"PRICE_C = {price}.0\n"
           f"ELAST_MULT_C = {em:.6f}\n"
           f"CHURN_PEXP_C = {CPE:.4f}\n"
           f"PRICE_RATIO_C = {pr:.6f}\n"
           f"EMAIL_REPLY_SCALE = {email_scale:.6f}\n"
           f"BOOK_OVERRIDE = {book_ovr:.6f}\n"
           f"SHOW_OVERRIDE = {show_ovr:.6f}")
    assert old in src, "A: price const anchor missing"
    src = src.replace(old, new)

    # B. elasticity + effective price inside run_path (Path C only)
    old = '    d2c, inbound_close, churn = P["d2c"], P["inbound_close"], P["churn"]'
    new = ("    em = ELAST_MULT_C if is_c else 1.0\n"
           '    d2c, inbound_close, churn = P["d2c"] * em, P["inbound_close"] * em, P["churn"]\n'
           "    churn = churn * ((PRICE_RATIO_C if is_c else 1.0) ** CHURN_PEXP_C)\n"
           "    MRR_EFF = PRICE_C if is_c else MRR_STD\n"
           "    SETUP_EFF = PRICE_C if is_c else SETUP\n"
           "    book_show = (Pc[\"book_rate\"] * Pc[\"show_rate\"]) if is_c else 1.0\n"
           "    show_f = Pc[\"show_rate\"] if is_c else 1.0")
    assert old in src, "B1: unpack anchor missing"
    src = src.replace(old, new)
    old = '    closer_month, closer_closes = P["closer_month"], P["closer_closes"]'
    new = '    closer_month, closer_closes = P["closer_month"], P["closer_closes"] * em'
    assert old in src, "B2: closer anchor missing"
    src = src.replace(old, new)

    # C. price usages -> effective price
    assert src.count("* MRR_STD") == 5, f"C: MRR count {src.count('* MRR_STD')}"
    src = src.replace("* MRR_STD", "* MRR_EFF")
    assert src.count("* SETUP") == 2, f"C: SETUP count {src.count('* SETUP')}"
    src = src.replace("* SETUP", "* SETUP_EFF")

    # D. EMAIL-FIRST locked: SMS only month 4+ (10DLC lead time)
    old = ("            sms_sent = np.minimum(cad * SMS_SEG, pool / 3.0)"
           "  # 90-day cooldown")
    new = ("            sms_sent = np.where(m >= 4, np.minimum(cad * SMS_SEG, pool / 3.0), 0.0)"
           "  # EMAIL-FIRST locked: SMS month 4+")
    assert old in src, "D: sms anchor missing"
    src = src.replace(old, new)

    # S. appointment-friction draws APPENDED to the campaign stream (pairing-safe)
    old = "    tcpa_uniform = rng_c.random((36, n))  # one draw per month per run"
    new = (old + "\n"
           "    book_rate = np.clip(rng_c.normal(0.70, 0.10, size=n), 0.45, 0.90)\n"
           "    book_rate = np.full(n, BOOK_OVERRIDE) if BOOK_OVERRIDE > 0 else book_rate\n"
           "    show_rate = np.clip(rng_c.normal(0.78, 0.08, size=n), 0.55, 0.92)\n"
           "    show_rate = np.full(n, SHOW_OVERRIDE) if SHOW_OVERRIDE > 0 else show_rate")
    assert old in src, "S: tcpa_uniform anchor missing"
    src = src.replace(old, new)
    old = ("                camp_churn_mult=camp_churn_mult, tcpa_cost_draw=tcpa_cost_draw,\n"
           "                tcpa_uniform=tcpa_uniform)")
    new = ("                camp_churn_mult=camp_churn_mult, tcpa_cost_draw=tcpa_cost_draw,\n"
           "                tcpa_uniform=tcpa_uniform, book_rate=book_rate, show_rate=show_rate)")
    assert old in src, "S2: campaign return anchor missing"
    src = src.replace(old, new)

    # M. monthly cumulative-cash tracking (both modes; reporting only)
    old = "    snaps = {}  # m -> dict of arrays"
    new = old + "\n    monthly_cash = []"
    assert old in src, "M1: snaps anchor missing"
    src = src.replace(old, new)
    old = "        cum_cash = cum_cash + (revenue - costs)"
    new = old + "\n        monthly_cash.append(cum_cash.copy())"
    assert old in src, "M2: cum_cash anchor missing"
    src = src.replace(old, new)
    old = "    out = dict(snaps=snaps, cross_month=cross_month, sms_total=sms_total,"
    new = "    out = dict(snaps=snaps, monthly_cash=np.array(monthly_cash), cross_month=cross_month, sms_total=sms_total,"
    assert old in src, "M3: out anchor missing"
    src = src.replace(old, new)

    # email-reply sensitivity knob (both modes; only binds when scale != 1)
    old = '            replies = (sms_sent * Pc["sms_reply"] + email_sent * Pc["email_reply"])'
    new = ('            replies = (sms_sent * Pc["sms_reply"]'
           ' + email_sent * Pc["email_reply"] * EMAIL_REPLY_SCALE)')
    assert old in src, "K: replies anchor missing"
    src = src.replace(old, new)

    if mode == "zerocall":
        # E. CLOSER-ONLY Bill: zero outbound dialing from month 1 (nextpath E)
        old = ("        dials = np.where(setter_any | (dial_off if is_c else False), 0.0,\n"
               "                         sell_hrs / 60.0 * 1200.0)")
        new = (old + "\n        if is_c:\n"
               "            dials = np.zeros(n)  # ZERO-CALL: Bill never dials")
        assert old in src, "E: dials anchor missing"
        src = src.replace(old, new)
        # Z2. setter outbound closes = 0 ON PATH C (nobody dials => no dialing
        # closes). is_c-guarded: Path A keeps its canon outbound for calibration.
        old = ("        new_outbound = np.where(setter_any, 1.5 * (d2c / 0.0025) * appt_mult,\n"
               "                                dials * d2c)")
        new = ("        new_outbound = (np.zeros(n) if is_c else np.where(setter_any, "
               "1.5 * (d2c / 0.0025) * appt_mult,\n"
               "                                dials * d2c))"
               "  # ZERO-CALL: no outbound dialing closes (Path C)")
        assert old in src, "Z2: new_outbound anchor missing"
        src = src.replace(old, new)
        # Z3. no dialing staff on Path C: setter payroll zeroed in the cost
        # line and the setter2 appointment boost removed — both guarded by
        # is_c so Path A (the calibration path) keeps exact canon mechanics.
        old = ("                 + (setter1_on.astype(float) + setter2_on.astype(float))"
               " * SETTER_COST")
        new = ("                 + (setter1_on.astype(float) + setter2_on.astype(float))"
               " * (0.0 if is_c else SETTER_COST)  # ZERO-CALL: no dialing setters")
        assert old in src, "Z3a: setter cost anchor missing"
        src = src.replace(old, new)
        old = "        appt_mult = 1.0 + 0.5 * setter2_on.astype(float)"
        new = ("        appt_mult = np.ones(n) if is_c else 1.0 + 0.5 * setter2_on.astype(float)"
               "  # ZERO-CALL: no setter2 appointment boost")
        assert old in src, "Z3b: appt_mult anchor missing"
        src = src.replace(old, new)
        # Z4. appointment friction on appointment-driven acquisition (Path C only
        # via book_show/show_f, which are 1.0 for Path A)
        old = "        new_inbound_org = inbound * inbound_close"
        new = "        new_inbound_org = inbound * inbound_close * book_show"
        assert old in src, "Z4a: inbound anchor missing"
        src = src.replace(old, new)
        old = '            camp_closes = convos * inbound_close * Pc["camp_close_disc"]'
        new = old + " * book_show"
        assert old in src, "Z4b: camp_closes anchor missing"
        src = src.replace(old, new)
        old = ("        new_closer = np.where(closer_on,\n"
               "                              closer_closes * appt_mult * np.where(proven, 1.5, 1.0), 0.0)")
        new = ("        new_closer = np.where(closer_on,\n"
               "                              closer_closes * appt_mult * np.where(proven, 1.5, 1.0) * show_f, 0.0)")
        assert old in src, "Z4c: closer anchor missing"
        src = src.replace(old, new)

    src = src.replace("unleashed_results.json", f"zerocall_{tag}.json")
    return src


def run_config(price, mode, tag, **kw):
    t0 = time.time()
    src = build_source(price, mode, tag, **kw)
    ns = {"__builtins__": __builtins__, "__name__": f"zerocall_{tag}",
          "__file__": os.path.join(OUT_DIR, "unleashed_sim.py")}
    exec(compile(src, "unleashed_sim.py", "exec"), ns)  # noqa: S102 (own sim code)
    res = ns["results"]["paths"]["C"]
    RC = ns["RC"]
    summ = {}
    for h in ("12", "24", "36"):
        v = res[h]
        summ[h] = {"customers": v["customers"], "arr": v["arr"], "cash": v["cash"],
                   "prob_cash_positive": v["prob_cash_positive"]}
    # first month the P50 cumulative-cash curve turns positive and stays positive
    med_curve = np.median(RC["monthly_cash"], axis=1)
    turn = None
    for i, v in enumerate(med_curve):
        if v >= 0 and (i == 35 or (med_curve[i:] >= 0).all()):
            turn = i + 1
            break
    raw = {"cash36": RC["snaps"][36]["cash"], "monthly_med": med_curve,
           "email_reply_draws": ns["Pc"]["email_reply"],
           "book_draws": ns["Pc"]["book_rate"], "show_draws": ns["Pc"]["show_rate"]}
    print(f"  [{tag}] m36: cust {summ['36']['customers']['p50']:.0f} "
          f"({summ['36']['customers']['p10']:.0f}-{summ['36']['customers']['p90']:.0f}) | "
          f"ARR ${summ['36']['arr']['p50']/1e6:.2f}M | cash P10/50/90 "
          f"${summ['36']['cash']['p10']/1e6:.2f}M/${summ['36']['cash']['p50']/1e6:.2f}M/"
          f"${summ['36']['cash']['p90']/1e6:.2f}M | cash+ {summ['36']['prob_cash_positive']:.1f}% | "
          f"turn m{turn} ({time.time()-t0:.1f}s)")
    return summ, raw, turn


def score(s36):
    c = s36["cash"]
    return 0.6 * c["p10"] + 0.3 * c["p50"] + 0.1 * c["p90"]


def paired_delta(raw_v, raw_b):
    d = raw_v - raw_b
    return {"p10": float(np.percentile(d, 10)), "p50": float(np.percentile(d, 50)),
            "p90": float(np.percentile(d, 90)),
            "prob_variant_beats": float((d > 0).mean() * 100)}


def p50_cash36(summ):
    return summ["36"]["cash"]["p50"]


def main():
    out = {"note": "SIMULATIONS / PROJECTIONS — not existing revenue. Collected revenue to date: $0.",
           "model": "ZERO-COLD-CALL: no dialing by anyone; inbound/automated acquisition only; "
                    "appointment book/show friction modeled (see verdict assumptions)",
           "runs_per_config": 50000, "seeds": "paired 20261016/20261017",
           "prices": {}, "sensitivity": {}}

    print("===== PRICE SWEEP: zerocall vs dialbill (paired) =====")
    raw_by = {}
    for price in (497, 697, 997):
        zc, zc_raw, zc_turn = run_config(price, "zerocall", f"zc{price}")
        db, db_raw, _ = run_config(price, "dialbill", f"db{price}")
        raw_by[price] = (zc_raw, db_raw)
        out["prices"][str(price)] = {
            "zerocall": zc, "dialbill": db,
            "zerocall_score": score(zc["36"]),
            "dialbill_score": score(db["36"]),
            "zerocall_turn_month_p50": zc_turn,
            "paired_delta_zerocall_minus_dialbill_cash36": paired_delta(
                zc_raw["cash36"], db_raw["cash36"]),
        }
    zc_winner = max((497, 697, 997), key=lambda p: out["prices"][str(p)]["zerocall_score"])
    db_winner = max((497, 697, 997), key=lambda p: out["prices"][str(p)]["dialbill_score"])
    out["zerocall_winner_price"] = zc_winner
    out["dialbill_winner_price"] = db_winner
    print(f"  zero-call winner: ${zc_winner} | with-dialing winner: ${db_winner}")

    # ---------- SENSITIVITY at the zero-call winning price ----------
    wp = zc_winner
    zc_raw = raw_by[wp][0]
    email_med = float(np.median(zc_raw["email_reply_draws"]))
    book_med = float(np.median(zc_raw["book_draws"]))
    show_med = float(np.median(zc_raw["show_draws"]))
    out["sensitivity"]["base_draw_medians"] = {"email_reply": email_med,
                                              "book_rate": book_med, "show_rate": show_med}
    print(f"\n===== SENSITIVITY @ ${wp} zerocall (base medians: email {email_med:.4f}, "
          f"book {book_med:.2f}, show {show_med:.2f}) =====")

    def sweep_email(scale):
        s, _, _ = run_config(wp, "zerocall", f"sens_email_{scale}", email_scale=scale)
        return p50_cash36(s), s["36"]["prob_cash_positive"]

    # email reply scale: coarse grid, then bisect the P50>0 crossing
    grid = [1.0, 0.8, 0.6, 0.45, 0.35, 0.25, 0.15]
    email_pts = {}
    for g in grid:
        email_pts[g] = sweep_email(g)
    pos = [g for g in grid if email_pts[g][0] > 0]
    neg = [g for g in grid if email_pts[g][0] <= 0]
    be_email_scale = None
    if pos and neg:
        lo, hi = max(neg), min(pos)          # cash(lo)<=0 < cash(hi)
        for _ in range(4):
            mid = round((lo + hi) / 2, 4)
            v = sweep_email(mid)
            email_pts[mid] = v
            if v[0] > 0:
                hi = mid
            else:
                lo = mid
        be_email_scale = hi
    elif pos and not neg:
        be_email_scale = "<=0.15 (below grid floor)"
    out["sensitivity"]["email_reply_scale"] = {
        "points": {str(k): {"p50_cash36": v[0], "prob_cash_positive": v[1]}
                   for k, v in sorted(email_pts.items())},
        "breakeven_scale": be_email_scale,
        "breakeven_absolute_rate": (be_email_scale * email_med
                                    if isinstance(be_email_scale, float) else be_email_scale),
    }

    def sweep_book(val):
        s, _, _ = run_config(wp, "zerocall", f"sens_book_{val}", book_ovr=val)
        return p50_cash36(s), s["36"]["prob_cash_positive"]

    book_pts = {}
    for v in (0.55, 0.45, 0.35, 0.25, 0.15):
        book_pts[v] = sweep_book(v)
    be_book = None
    bpos = [v for v in book_pts if book_pts[v][0] > 0]
    if bpos:
        be_book = min(bpos)
        # one refinement step between the lowest positive and next lower tested
        lower = [v for v in book_pts if v < be_book and book_pts[v][0] <= 0]
        if lower:
            mid = round((be_book + max(lower)) / 2, 3)
            mv = sweep_book(mid)
            book_pts[mid] = mv
            if mv[0] > 0:
                be_book = mid
    out["sensitivity"]["book_rate_fixed"] = {
        "points": {str(k): {"p50_cash36": v[0], "prob_cash_positive": v[1]}
                   for k, v in sorted(book_pts.items())},
        "breakeven_book_rate": be_book,
        "note": "book rate held FIXED at the swept value (stochastic draws replaced)",
    }

    def sweep_show(val):
        s, _, _ = run_config(wp, "zerocall", f"sens_show_{val}", show_ovr=val)
        return p50_cash36(s), s["36"]["prob_cash_positive"]

    show_pts = {}
    for v in (0.65, 0.55, 0.45, 0.35, 0.25):
        show_pts[v] = sweep_show(v)
    be_show = None
    spos = [v for v in show_pts if show_pts[v][0] > 0]
    if spos:
        be_show = min(spos)
        lower = [v for v in show_pts if v < be_show and show_pts[v][0] <= 0]
        if lower:
            mid = round((be_show + max(lower)) / 2, 3)
            mv = sweep_show(mid)
            show_pts[mid] = mv
            if mv[0] > 0:
                be_show = mid
    out["sensitivity"]["show_rate_fixed"] = {
        "points": {str(k): {"p50_cash36": v[0], "prob_cash_positive": v[1]}
                   for k, v in sorted(show_pts.items())},
        "breakeven_show_rate": be_show,
        "note": "show rate held FIXED at the swept value (stochastic draws replaced)",
    }

    # monthly P50 curve for the winner (context for the turn month)
    out["winner_monthly_p50_cumcash"] = [float(v) for v in zc_raw["monthly_med"]]

    with open(os.path.join(OUT_DIR, "zerocall_results.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote", os.path.join(OUT_DIR, "zerocall_results.json"))
    z = out["prices"][str(wp)]["zerocall"]
    d = out["prices"][str(wp)]["paired_delta_zerocall_minus_dialbill_cash36"]
    print(f"ZERO-CALL WINNER ${wp}: cust {z['36']['customers']['p50']:.0f} | "
          f"cash P50 ${z['36']['cash']['p50']/1e6:.2f}M | "
          f"paired cost of removing the phone: ${d['p50']/1e6:+.2f}M P50 "
          f"(P10 ${d['p10']/1e6:+.2f}M / P90 ${d['p90']/1e6:+.2f}M)")
    print(f"break-evens @ ${wp}: email scale {be_email_scale} | book {be_book} | show {be_show}")


if __name__ == "__main__":
    main()
