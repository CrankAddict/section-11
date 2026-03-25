# Weekly Report Examples

> Anonymized examples using realistic placeholder data.
> These demonstrate Section 11-compliant weekly report output.

---

## Example 1: Normal Training Week (Build Phase, Mid-Block)

```
Week 2 Summary (27 Jan – 02 Feb 2026)
Block: Threshold Development — Week 2/4
Phase: Build — week 4 (confidence: high)
  Basis: Rising CTL, 2-3 hard days sustained

Compliance: 6/6 sessions completed
Planned TSS: 520 | Actual TSS: 537 (103%)
Hours: 14h12m (prev week: 13h48m)

Session Breakdown:
  Mon: Recovery spin — 32 TSS ✅
  Tue: Sweetspot 2x20 — 89 TSS ✅
  Wed: Endurance 2h30m — 78 TSS ✅
  Thu: VO2max 5x4min — 95 TSS ✅
  Fri: Endurance 3h + SkiErg — 112 TSS ✅
  Sat: Rest — 0 TSS ✅
  Sun: Long ride 4h — 131 TSS ✅

Quality Session Detail:
  Sweetspot 2x20:
    Target: 248W | Actual: 251W avg / 254W NP
    Decoupling: 2.1% (good)
    VI: 1.01 (good)
    HR: 158 avg / 167 max
  VO2max 5x4min:
    Target: 310W | Actual: 306W avg / 315W NP
    Decoupling: 4.8% (good)
    VI: 1.03 (good)
    HR: 168 avg / 178 max
    HRRc: 42 bpm

Polarization:
  Z1+Z2: 83%
  Z3 (Grey Zone): 3% (target <5%)
  Z4+ (Quality): 14% (target ~20% of intensity sessions)
  TID 7d: Polarized (PI: 2.92)
  TID 28d: Polarized (PI: 3.05) — drift: consistent

Durability (steady-state sessions, VI ≤ 1.05, ≥ 90min):
  7d mean(3): 2.10% | 28d mean(11): 2.65%
  Trend: improving | High drift (>5%): 0 sessions

Efficiency Factor (steady-state cycling, VI ≤ 1.05, ≥ 20min):
  7d mean(4): 1.47 | 28d mean(14): 1.44
  Trend: stable

HRRc:
  7d mean(2): 38 bpm | 28d mean(6): 36 bpm
  Trend: stable

Power Curve Delta (28d vs prior 28d):
  Rotation: +0.4 (sprint-biased)
  Notable shifts: 5min +3.1%, 20min +2.4%

HR Curve Delta (28d vs prior 28d):
  Rotation: -0.2 (endurance-biased)
  No significant shifts

Fitness:
  CTL: 78.2 → 80.6 (Δ +2.4)
  ATL: 82.1 → 85.3
  TSB: -3.9 → -4.7
  Recovery Index: 0.89 (good)
  Ramp rate: 1.20
  ACWR: 1.06 (optimal)
    Acute (7d): 537 TSS | Chronic (28d avg): 507 TSS

Wellness Trends:
  HRV: 48–62 ms (avg 54, prev week 56) →
  RHR: 47–52 bpm (avg 49, prev week 48) →
  Sleep: 7h12m avg, quality 2.2/4 avg →
  Avg Feel: 2.2/5 (5 sessions) →
  Avg RPE: 4.8/10 (5 sessions) →

Section 11 Flags: None

Interpretation:
Strong compliance week — all six sessions completed as planned. Both
quality sessions hit targets: sweetspot power slightly above target with
excellent pacing (VI 1.01), and VO2max intervals within 2% of target
despite being end of a build week. Grey zone well controlled at 3%.
TSB drifting slightly negative but manageable heading into week 3.

Next Week Preview:
Week 3 is peak load before deload. Tuesday sweetspot extends to 2x25,
Thursday VO2max adds a 6th interval. Sunday long ride targets 4h30m.
Monitor HRV early in the week — if it drops below 45ms, consider
modifying Thursday's session.
```

---

## Example 2: Week With Flags and Modifications (Base Phase)

```
Week 3 Summary (03 Feb – 09 Feb 2026)
Block: Aerobic Base — Week 3/5
Phase: Base — week 7 (confidence: high)
  Basis: Sustained endurance focus, no intensity progression

Compliance: 5/7 sessions completed (1 modified, 1 missed)
Planned TSS: 480 | Actual TSS: 392 (82%)
Hours: 12h6m (prev week: 14h48m)

Session Breakdown:
  Mon: Recovery spin — 28 TSS ✅
  Tue: Tempo 3x15 — 76 TSS ⚠️ (cut to 2x15, fatigue)
  Wed: Endurance 2h — 62 TSS ✅
  Thu: Rest (unplanned) — 0 TSS ❌ (poor sleep, HRV drop)
  Fri: Endurance 3h — 98 TSS ✅
  Sat: Yoga/mobility — 0 TSS ✅
  Sun: Long ride 3h30m — 128 TSS ✅

Quality Session Detail:
  Tempo 3x15 (modified to 2x15):
    Target: 235W | Actual: 228W avg / 232W NP
    Decoupling: 6.2% (elevated)
    VI: 1.02 (good)
    HR: 155 avg / 164 max

Polarization:
  Z1+Z2: 91%
  Z3 (Grey Zone): 7% (target <5%) ⚠️
  Z4+ (Quality): 2%
  TID 7d: Pyramidal (PI: 1.85)
  TID 28d: Polarized (PI: 2.90) — drift: acute_depolarization ⚠️

Durability (steady-state sessions, VI ≤ 1.05, ≥ 90min):
  7d mean(2): 4.80% | 28d mean(9): 2.90%
  Trend: declining | High drift (>5%): 1 session

Efficiency Factor (steady-state cycling, VI ≤ 1.05, ≥ 20min):
  7d mean(3): 1.38 | 28d mean(11): 1.44
  Trend: declining

HRRc:
  22 bpm 28d mean(3) — 7d: no data

Power Curve Delta (28d vs prior 28d):
  Rotation: -0.8 (endurance-biased)
  Notable shifts: 5min -3.4%, 1min -2.8%

HR Curve Delta (28d vs prior 28d):
  Rotation: +0.5 (intensity-biased)
  Notable shifts: 5min +3.1%, 20min +2.6%
  Cross-reference: HRV declining, RHR elevated — rising HR likely fatigue, not fitness

Fitness:
  CTL: 72.4 → 71.1 (Δ -1.3)
  ATL: 88.6 → 78.2
  TSB: -16.2 → -7.1
  Recovery Index: 0.72 (moderate)
  Ramp rate: -0.65
  ACWR: 0.89 (optimal)
    Acute (7d): 392 TSS | Chronic (28d avg): 441 TSS

Wellness Trends:
  HRV: 39–51 ms (avg 44, prev week 52) ↓ declining — monitor
  RHR: 50–56 bpm (avg 53, prev week 49) ↑ elevated — monitor
  Sleep: 6h6m avg, quality 3.2/4 avg ↓ declining — monitor
  Avg Feel: 3.6/5 (4 sessions) ↓ declining — monitor
  Avg RPE: 6.8/10 (4 sessions) ↑ elevated — monitor

Section 11 Flags:
  - HRV below 7-day baseline by >15% on Thu → triggered rest day
  - Grey Zone >5% for the week → review Tuesday pacing
  - TID acute depolarization: 7d PI 1.85 vs 28d PI 2.90 → fatigue shifting distribution
  - Durability declining: 7d mean 4.80% vs 28d 2.90% → aerobic efficiency slipping

Interpretation:
Fatigue accumulated from weeks 1-2 surfaced mid-week. HRV dropped 15%
Thursday morning, prompting an unplanned rest day — correct decision per
Section 11 Tier 1 readiness hierarchy. Tuesday's tempo was modified
mid-session (cut third interval) due to elevated perceived effort, and
grey zone crept to 7% as a result of pacing drift. Durability declined
noticeably (4.8% vs 2.9% 28d average) and TID shifted from Polarized to
Pyramidal — both consistent with accumulated fatigue rather than a training
design issue. TSB recovering from -16 to -7, which was needed. Sleep
quality was the likely root cause — address sleep hygiene before next week.

Next Week Preview:
Week 4 was planned as continued base build but recommending a partial
deload given wellness trends. Reduce planned TSS by ~15%, keep Sunday
long ride but drop Thursday intensity session to endurance. Reassess
HRV trend by Wednesday — if restored to baseline, resume normal load
for week 5.
```

---

## Notes

- **Example 1** shows a clean week — brief flags section, concise overall
- **Example 2** shows how the template handles real-world disruptions — modifications, flags, and adaptive planning
- **Quality Session Detail** only appears for intensity sessions; endurance/recovery rides are covered in the Session Breakdown. Cap at 2–3 per week — if 4+ hard days occurred, prioritize the most notable sessions
- **Wellness arrows with labels** make trends immediately actionable without requiring the athlete to interpret raw numbers
- **Section 11 Flags** surfaced in the weekly report, not deferred to block report
