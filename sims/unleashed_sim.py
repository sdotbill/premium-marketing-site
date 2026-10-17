"""
UNLEASHED OPERATOR sim — Path A (old structure) vs Path C (unleashed + inbound machine).
50,000 runs per path, 36-month horizon, vectorized numpy.

Path A = v15.2 conservative canon mechanics (verified: 69.4 customers / $706,110 ARR /
$269,155 cash / 100% cash-positive at 12mo P50), extended to 36 months, PLUS one
documented difference: Path A hires a $400/mo bookkeeper at month 6 (old structure:
Dave has no bank access; someone must keep the books). Labeled assumption.

Path C = Path A mechanics + unleashed levers (Bill, 2026-10-16):
  1. Organic inbound mean 5.0 -> 6.5/mo (ship-then-notify content velocity; assumption).
  2. Bill sell hours 60 -> 70/mo (QC/editing hours back to selling; assumption).
  3. Dave-run SMS+email campaigns to the Forge prospect pool -> campaign inbound closes.
  4. Per-campaign approval gate: max 4 campaigns/mo (Bill approves; standing rule).
  5. 90-day SMS / 30-day email contact cooldowns against pool size (pool binds early).
  6. No bookkeeper (Dave runs books post-Huntington; assumption).
  7. TCPA tail risk on cold SMS (assumption; sensitivity variant in verdict).
  8. Campaign-sourced customers churn 1.25x (colder relationship; assumption).
  9. Crossover: Bill stops dialing after campaign closes beat outbound closes 2 months
     running (month >= 4); thereafter 10 hrs/mo inbound closing.

PAIRING: shared params drawn once (seed 20261016); campaign params drawn once
(seed 20261017, consumed ONLY by Path C). Deltas = median of per-run (C - A).
Never difference-of-medians.

All figures are SIMULATIONS / PROJECTIONS. Collected revenue to date: $0.
"""

import json
import os
import time

import numpy as np

OUT_DIR = "/content/sims"
os.makedirs(OUT_DIR, exist_ok=True)

N = 50000

# ---------- economics (v15.2 canon) ----------
SETUP = 697.0
MRR_STD = 697.0
BILL_DRAW = 4000.0
BIZ_OH = 500.0
SETTER_COST = 2000.0
AM_COST = 2500.0
QC2_COST = 2500.0
CLOSER_COST = 3000.0
BOOKKEEPER_MO = 400.0          # Path A hires at month 6 (assumption)
EXCL_TAKE = 0.01
EXCL_BLOCKED_PER = 2.0
EXCL_CAP_FRAC = 0.25
EXCL_MRR = 2000.0
PIPE_ENTRY, PIPE_CONV, PIPE_DECAY, PIPE_CLOSE_RATE = 0.1, 0.05, 0.2, 0.25
STICKINESS = 0.35
HT_FRAC, HT_TAKE, HT_ADDON = 0.30, 0.06, 400.0
BASE_TAKE, BASE_ADDON = 0.015, 150.0
EXCL_UP_TAKE = 0.10
LEARN_DIV = 0.008
BILL_HRS, BUFFER_HRS = 120.0, 15.0

# ---------- campaign economics (Path C; all assumptions, see assumptions.md) ----------
POOL_START = 15551.0
POOL_GROWTH_MO = 1080.0        # ~36/day automated sweeps
SMS_SEG = 3000.0
EMAIL_SEG = 8000.0
SMS_COST = 0.025               # $/SMS all-in
DLC_SETUP = 50.0               # 10DLC one-time (month 1)
DLC_MO = 10.0
COMPLIANCE_MO = 150.0          # opt-out handling, list hygiene, scrubbing

rng_s = np.random.default_rng(20261016)   # shared stream (both paths)
rng_c = np.random.default_rng(20261017)   # campaign stream (Path C only)


def sample_shared(n):
    d2c = np.clip(rng_s.lognormal(mean=np.log(0.0035), sigma=0.55, size=n), 0.0008, 0.010)
    inbound = np.clip(rng_s.normal(5.0, 1.6, size=n), 1.0, 10.0)
    inbound_close = np.clip(rng_s.normal(0.32, 0.06, size=n), 0.15, 0.50)
    churn = np.clip(rng_s.lognormal(mean=np.log(0.030), sigma=0.45, size=n), 0.012, 0.08)
    murphy = (rng_s.random(n) < 0.85).astype(float)
    maki = (rng_s.random(n) < 0.60).astype(float)
    santos_on = (rng_s.random(n) < 0.70).astype(float)
    santos_mo = np.clip(rng_s.normal(1600, 400, size=n), 800, 2400)
    closer_month = np.clip(rng_s.normal(6, 1.5, size=n).astype(int), 6, 12)
    closer_closes = np.clip(rng_s.normal(2.0, 0.5, size=n), 1.0, 3.5)
    return dict(d2c=d2c, inbound=inbound, inbound_close=inbound_close, churn=churn,
                murphy=murphy, maki=maki, santos_on=santos_on, santos_mo=santos_mo,
                closer_month=closer_month, closer_closes=closer_closes)


def sample_campaign(n):
    sms_reply = np.clip(rng_c.lognormal(mean=np.log(0.012), sigma=0.50, size=n), 0.004, 0.030)
    email_reply = np.clip(rng_c.lognormal(mean=np.log(0.005), sigma=0.50, size=n), 0.002, 0.012)
    reply_to_convo = np.clip(rng_c.normal(0.25, 0.07, size=n), 0.10, 0.45)
    camp_close_disc = np.clip(rng_c.normal(0.70, 0.10, size=n), 0.45, 0.95)
    camp_churn_mult = np.clip(rng_c.normal(1.25, 0.10, size=n), 1.0, 1.5)
    tcpa_cost_draw = np.clip(rng_c.lognormal(mean=np.log(25000), sigma=0.80, size=n),
                             5000, 150000)
    tcpa_uniform = rng_c.random((36, n))  # one draw per month per run
    return dict(sms_reply=sms_reply, email_reply=email_reply,
                reply_to_convo=reply_to_convo, camp_close_disc=camp_close_disc,
                camp_churn_mult=camp_churn_mult, tcpa_cost_draw=tcpa_cost_draw,
                tcpa_uniform=tcpa_uniform)


def run_path(is_c, P, Pc):
    n = N
    d2c, inbound_close, churn = P["d2c"], P["inbound_close"], P["churn"]
    inbound = P["inbound"] + (1.5 if is_c else 0.0)          # lever 1: content velocity
    sell_full = 70.0 if is_c else 60.0                        # lever 2: Bill's hours back
    murphy, maki = P["murphy"], P["maki"]
    santos_on, santos_mo = P["santos_on"], P["santos_mo"]
    closer_month, closer_closes = P["closer_month"], P["closer_closes"]

    customers_org = np.zeros(n)
    customers_camp = np.zeros(n)
    mrr_org = np.zeros(n)
    mrr_camp = np.zeros(n)
    up_mrr = np.zeros(n)
    excl_mrr = np.zeros(n)
    excl_cust = np.zeros(n)
    up_cust = np.zeros(n)
    cum_cash = np.zeros(n)
    pipeline = np.zeros(n)
    setter1_on = np.zeros(n, dtype=bool)
    setter2_on = np.zeros(n, dtype=bool)
    acct_on = np.zeros(n, dtype=bool)
    qc2_on = np.zeros(n, dtype=bool)
    closer_on = np.zeros(n, dtype=bool)
    murphy_done = np.zeros(n, dtype=bool)
    maki_done = np.zeros(n, dtype=bool)
    dial_off = np.zeros(n, dtype=bool)
    beat_streak = np.zeros(n, dtype=int)
    cross_month = np.zeros(n, dtype=int)
    sms_total = np.zeros(n)
    tcpa_events = np.zeros(n)
    camp_closes_total = np.zeros(n)

    snaps = {}  # m -> dict of arrays

    for m in range(1, 37):
        customers = customers_org + customers_camp
        setter1_on = setter1_on | (customers >= 10)
        setter2_on = setter2_on | (customers >= 20)
        setter_any = setter1_on | setter2_on
        acct_on = acct_on | (customers >= 15)
        n_ams = ((customers >= 15).astype(float) + (customers >= 50).astype(float)
                 + (customers >= 75).astype(float))
        qc2_on = qc2_on | (customers >= 50)
        closer_on = closer_on | (m >= closer_month)
        # NOTE (faithful to v15.2 engine): at_cap is dead code there — qc2 hires at
        # 50 customers, cap threshold is >= 90, so it can never bind. Replicated as-is.
        at_cap = (~qc2_on) & (customers >= 90 + 30.0 * (n_ams - 1.0))

        managed = np.where(acct_on, 0.0, customers)
        mgmt = managed * 1.5
        setter_mgmt = np.where(setter1_on & ~acct_on, 45.0, 0.0)
        avail = BILL_HRS - mgmt - BUFFER_HRS - setter_mgmt
        sell_hrs = np.clip(np.where(setter_any, 15.0, np.minimum(sell_full, avail)),
                           0, sell_full)
        if is_c:
            sell_hrs = np.where(dial_off, 10.0, sell_hrs)   # crossover: inbound closing only
        dials = np.where(setter_any | (dial_off if is_c else False), 0.0,
                         sell_hrs / 60.0 * 1200.0)
        appt_mult = 1.0 + 0.5 * setter2_on.astype(float)
        new_outbound = np.where(setter_any, 1.5 * (d2c / 0.0025) * appt_mult,
                                dials * d2c)
        proven = closer_on & (m >= closer_month + 3)
        new_outbound = np.where(proven, new_outbound * 0.33, new_outbound)  # Bill exit ramp
        new_inbound_org = inbound * inbound_close
        new_closer = np.where(closer_on,
                              closer_closes * appt_mult * np.where(proven, 1.5, 1.0), 0.0)

        camp_closes = np.zeros(n)
        camp_cost = np.zeros(n)
        if is_c:
            pool = POOL_START + POOL_GROWTH_MO * (m - 1)
            cad = np.where(m <= 2, 2.0, 4.0)                 # approval-gate ramp
            sms_sent = np.minimum(cad * SMS_SEG, pool / 3.0)  # 90-day cooldown
            email_sent = np.minimum(cad * EMAIL_SEG, pool)     # 30-day cooldown
            replies = (sms_sent * Pc["sms_reply"] + email_sent * Pc["email_reply"])
            convos = replies * Pc["reply_to_convo"]
            camp_closes = convos * inbound_close * Pc["camp_close_disc"]
            sms_total = sms_total + sms_sent
            camp_closes_total = camp_closes_total + camp_closes
            p_evt = 1.0 - (1.0 - 0.05) ** (1.0 / 12.0)        # 5%/yr TCPA event (assumption)
            evt = (Pc["tcpa_uniform"][m - 1] < p_evt) & (sms_sent > 0)
            tcpa_events = tcpa_events + evt.astype(float)
            tcpa_cost = evt.astype(float) * Pc["tcpa_cost_draw"]
            camp_cost = (sms_sent * SMS_COST + DLC_MO + COMPLIANCE_MO + tcpa_cost
                         + (DLC_SETUP if m == 1 else 0.0))
            # crossover: campaign beats outbound 2 months running (m >= 4)
            cond = (m >= 4) & (camp_closes >= new_outbound) & (new_outbound > 0.5)
            beat_streak = np.where(cond & ~dial_off, beat_streak + 1, beat_streak)
            newly_off = (~dial_off) & (beat_streak >= 2)
            dial_off = dial_off | newly_off
            cross_month = np.where((cross_month == 0) & newly_off, m, cross_month)

        new_noncamp = np.where(at_cap, 0.0, new_outbound + new_inbound_org + new_closer)
        new_camp = np.where(at_cap, 0.0, camp_closes)

        # specials: Murphy m1 (85%), Maki m2 (60%) — verified pending deals
        special_setup = np.zeros(n)
        do_murphy = (~murphy_done) & (m == 1)
        customers_org = customers_org + do_murphy * murphy
        mrr_org = mrr_org + do_murphy * murphy * 699.0
        special_setup = special_setup + do_murphy * murphy * 699.0
        murphy_done = murphy_done | do_murphy
        do_maki = (~maki_done) & (m == 2)
        customers_org = customers_org + do_maki * maki
        mrr_org = mrr_org + do_maki * maki * MRR_STD
        special_setup = special_setup + do_maki * maki * SETUP
        maki_done = maki_done | do_maki
        customers = customers_org + customers_camp  # refresh after specials

        # exclusivity module (v9, assumptions)
        new_excl_cust = (customers - excl_cust) * EXCL_TAKE
        new_excl_cust = np.minimum(new_excl_cust,
                                   np.maximum(0.0, customers * EXCL_CAP_FRAC - excl_cust))
        churn_pre = churn  # churn_eff computed below; excl churn uses it after
        # pipeline carryover (v15.2) — inferred from NON-campaign closes only
        conv = np.where(at_cap, 0.0, pipeline * PIPE_CONV)
        pipeline = pipeline - conv
        new_noncamp = new_noncamp + conv
        fresh_noncamp = np.maximum(0.0, new_noncamp - conv)
        noncloses = fresh_noncamp * (1.0 - PIPE_CLOSE_RATE) / PIPE_CLOSE_RATE
        pipeline = pipeline * (1.0 - PIPE_DECAY) + PIPE_ENTRY * noncloses

        # churn (AM -30%, learn dividend, upsell stickiness)
        churn_eff = np.where(acct_on, churn * 0.70, churn)
        churn_eff = churn_eff * (1.0 - LEARN_DIV * m)
        up_frac = up_cust / np.maximum(customers, 1.0)
        churn_eff = churn_eff * (1.0 - STICKINESS * np.clip(up_frac, 0.0, 1.0))
        excl_cust = excl_cust + new_excl_cust - excl_cust * churn_eff
        excl_mrr = excl_mrr + new_excl_cust * EXCL_MRR - excl_mrr * churn_eff
        # exclusivity blocks future closes (applied to non-campaign first)
        blocked = excl_cust * (EXCL_BLOCKED_PER / 12.0)
        new_noncamp = np.maximum(0.0, new_noncamp - blocked)
        new_camp = np.maximum(0.0, new_camp - np.maximum(0.0, blocked - new_noncamp))

        new_total = new_noncamp + new_camp
        churned_camp = customers_camp * np.minimum(churn_eff * Pc["camp_churn_mult"]
                                                   if is_c else churn_eff, 0.5)
        churned_org = customers_org * churn_eff
        customers_org = customers_org + new_noncamp - churned_org
        customers_camp = customers_camp + new_camp - churned_camp
        mrr_org = mrr_org + new_noncamp * MRR_STD - churned_org * MRR_STD
        mrr_camp = mrr_camp + new_camp * MRR_STD - churned_camp * MRR_STD
        customers = customers_org + customers_camp

        # tiered upsells on the whole base
        ht_cust = np.maximum(0.0, customers * HT_FRAC - excl_cust)
        rest_cust = np.maximum(0.0, customers - customers * HT_FRAC)
        new_up = (excl_cust * EXCL_UP_TAKE * HT_ADDON + ht_cust * HT_TAKE * HT_ADDON
                  + rest_cust * BASE_TAKE * BASE_ADDON)
        new_upgraders = (excl_cust * EXCL_UP_TAKE + ht_cust * HT_TAKE
                         + rest_cust * BASE_TAKE)
        up_mrr = up_mrr + new_up - up_mrr * churn_eff
        up_cust = up_cust + new_upgraders - up_cust * churn_eff

        mrr_total = mrr_org + mrr_camp + up_mrr + excl_mrr
        setup_rev = new_total * SETUP + special_setup
        santos_rev = np.where(m >= 3, santos_on * santos_mo, 0.0)
        revenue = mrr_total + setup_rev + santos_rev
        costs = (BILL_DRAW + BIZ_OH
                 + (setter1_on.astype(float) + setter2_on.astype(float)) * SETTER_COST
                 + n_ams * AM_COST + qc2_on.astype(float) * QC2_COST
                 + closer_on.astype(float) * CLOSER_COST)
        if not is_c:
            costs = costs + np.where(m >= 6, BOOKKEEPER_MO, 0.0)   # Path A hires books
        else:
            costs = costs + camp_cost                                # Path C: Dave does books
        cum_cash = cum_cash + (revenue - costs)

        if m in (12, 24, 36):
            snaps[m] = dict(customers=customers.copy(),
                            arr=(mrr_total * 12).copy(),
                            cash=cum_cash.copy())

    out = dict(snaps=snaps, cross_month=cross_month, sms_total=sms_total,
               tcpa_events=tcpa_events, camp_closes_total=camp_closes_total)
    return out


def pct(a, q):
    return float(np.percentile(a, q))


t0 = time.time()
P = sample_shared(N)
Pc = sample_campaign(N)
t_sample = time.time() - t0

t0 = time.time()
RA = run_path(False, P, Pc)
tA = time.time() - t0
t0 = time.time()
RC = run_path(True, P, Pc)
tC = time.time() - t0

results = {"runs": N, "horizons": [12, 24, 36],
           "note": "SIMULATIONS / PROJECTIONS — not existing revenue. Collected revenue to date: $0.",
           "seconds": {"sample": round(t_sample, 1), "path_A": round(tA, 1),
                       "path_C": round(tC, 1)},
           "paths": {}, "paired_deltas_C_minus_A": {}}

for name, R in (("A", RA), ("C", RC)):
    pd = {"label": "old structure (v15.2 canon + bookkeeper m6)" if name == "A"
          else "unleashed (content velocity + sell hrs + SMS/email inbound machine)"}
    for h in (12, 24, 36):
        s = R["snaps"][h]
        pd[str(h)] = {
            "customers": {"p10": pct(s["customers"], 10), "p50": pct(s["customers"], 50),
                          "p90": pct(s["customers"], 90)},
            "arr": {"p10": pct(s["arr"], 10), "p50": pct(s["arr"], 50),
                    "p90": pct(s["arr"], 90)},
            "cash": {"p10": pct(s["cash"], 10), "p50": pct(s["cash"], 50),
                     "p90": pct(s["cash"], 90)},
            "prob_cash_positive": float((s["cash"] > 0).mean() * 100),
        }
    if name == "C":
        pd["crossover_month_p50"] = float(np.median(R["cross_month"][R["cross_month"] > 0]))
        pd["crossover_share_pct"] = float((R["cross_month"] > 0).mean() * 100)
        pd["sms_sent_total_p50"] = float(np.median(R["sms_total"]))
        pd["tcpa_event_share_pct"] = float((R["tcpa_events"] > 0).mean() * 100)
        pd["camp_closes_total_p50"] = float(np.median(R["camp_closes_total"]))
    results["paths"][name] = pd

for h in (12, 24, 36):
    h = str(h)
    dc = RC["snaps"][int(h)]["customers"] - RA["snaps"][int(h)]["customers"]
    da = RC["snaps"][int(h)]["arr"] - RA["snaps"][int(h)]["arr"]
    dm = RC["snaps"][int(h)]["cash"] - RA["snaps"][int(h)]["cash"]
    results["paired_deltas_C_minus_A"][h] = {
        # PAIRED-MEDIAN deltas: median of per-run differences (AGENTS.md sim-delta rule)
        "customers": {"p10": pct(dc, 10), "p50": pct(dc, 50), "p90": pct(dc, 90)},
        "arr": {"p10": pct(da, 10), "p50": pct(da, 50), "p90": pct(da, 90)},
        "cash": {"p10": pct(dm, 10), "p50": pct(dm, 50), "p90": pct(dm, 90)},
        "prob_C_beats_A_customers": float((dc > 0).mean() * 100),
        "prob_C_beats_A_cash": float((dm > 0).mean() * 100),
    }

with open(os.path.join(OUT_DIR, "unleashed_results.json"), "w") as f:
    json.dump(results, f, indent=1)

# calibration check: Path A 12mo vs verified v15.2 canon
a12 = results["paths"]["A"]["12"]
print("CALIBRATION — Path A 12mo P50 vs verified v15.2 canon (69.4 / 706110 / 269155):")
print(f"  customers {a12['customers']['p50']:.1f} | arr ${a12['arr']['p50']:,.0f} | "
      f"cash ${a12['cash']['p50']:,.0f} | cash+ {a12['prob_cash_positive']:.1f}%")
print("(cash runs ~$2.8K under canon: the $400/mo Path-A bookkeeper from month 6)")
for name in ("A", "C"):
    for h in ("12", "24", "36"):
        v = results["paths"][name][h]
        print(f"Path {name} m{h}: cust {v['customers']['p50']:.0f} "
              f"({v['customers']['p10']:.0f}-{v['customers']['p90']:.0f}) | "
              f"ARR ${v['arr']['p50']/1e6:.2f}M | cash ${v['cash']['p50']/1e3:.0f}K | "
              f"cash+ {v['prob_cash_positive']:.0f}%")
for h in ("12", "24", "36"):
    d = results["paired_deltas_C_minus_A"][h]
    print(f"PAIRED DELTA C-A m{h}: cust {d['customers']['p50']:+.0f} "
          f"({d['customers']['p10']:+.0f}/{d['customers']['p90']:+.0f}) | "
          f"ARR ${d['arr']['p50']/1e3:+.0f}K | cash ${d['cash']['p50']/1e3:+.0f}K | "
          f"P(C>A cust) {d['prob_C_beats_A_customers']:.0f}% | "
          f"P(C>A cash) {d['prob_C_beats_A_cash']:.0f}%")
c = results["paths"]["C"]
print(f"Crossover: {c['crossover_share_pct']:.0f}% of runs, median month {c['crossover_month_p50']:.0f}")
print(f"TCPA: {c['tcpa_event_share_pct']:.1f}% of runs hit >=1 event; "
      f"median SMS sent {c['sms_sent_total_p50']:,.0f}; "
      f"median campaign closes {c['camp_closes_total_p50']:.0f}")
print("wrote", os.path.join(OUT_DIR, "unleashed_results.json"))
