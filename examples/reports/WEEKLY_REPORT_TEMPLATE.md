# Weekly Report Template

**Structure only — no data. Replace `[placeholders]` with actual values.**

**Data Freshness:** Every numeric value in a report must come from a current read of its source JSON file. Do not carry forward values from earlier reports or earlier in the conversation — re-read before quoting.

**Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON — they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. See SECTION_11.md §Display Unit Semantics.

Generated at end of training week (Saturday or Sunday morning).

---

## Template Structure

```
Week [X] Summary ([date range])
Block: [Name] — Week [X/Y]
Phase: [Phase] — week [phase_duration_weeks] (confidence: [confidence])
  [If previous_phase differs: "Transitioned from [previous_phase]"]
  [If key reason_codes: "[1-2 codes in plain English]"]

Compliance: [X/X] sessions completed
Planned TSS: [XXX] | Actual TSS: [XXX] ([XX]%)
Hours: [XhYm] (prev week: [XhYm])

Session Breakdown:
  Mon: [workout name] — [XXX] TSS ✅/⚠️/❌
  Tue: [workout name] — [XXX] TSS ✅/⚠️/❌
  Wed: [workout name] — [XXX] TSS ✅/⚠️/❌
  Thu: [workout name] — [XXX] TSS ✅/⚠️/❌
  Fri: [workout name] — [XXX] TSS ✅/⚠️/❌
  Sat: [workout name] — [XXX] TSS ✅/⚠️/❌
  Sun: [workout name] — [XXX] TSS ✅/⚠️/❌

Quality Session Detail:
  [Session 1 name]:
    Target: [XXX]W | Actual: [XXX]W avg / [XXX]W NP
    Decoupling: [X.XX]%
    VI: [X.XX] ([assessment])
    HR: [XXX] avg / [XXX] max
  [Session 2 name]:
    Target: [XXX]W | Actual: [XXX]W avg / [XXX]W NP
    Decoupling: [X.XX]%
    VI: [X.XX] ([assessment])
    HR: [XXX] avg / [XXX] max

Polarization:
  Z1+Z2: [XX]%
  Z3 (Grey Zone): [X]% (target <5%)
  Z4+ (Quality): [X]% (target ~20% of intensity sessions)
  TID 7d: [Classification] (PI: [X.XX])
  TID 28d: [Classification] (PI: [X.XX]) — drift: [consistent/shifting/acute_depolarization]

Durability (steady-state sessions, VI ≤ 1.05, ≥ 90min):
  7d mean([X]): [X.XX]% | 28d mean([X]): [X.XX]%
  Trend: [improving/stable/declining] | High drift (>5%): [X] sessions

Efficiency Factor (steady-state cycling, VI ≤ 1.05, ≥ 20min):
  7d mean([X]): [X.XX] | 28d mean([X]): [X.XX]
  Trend: [improving/stable/declining]

HRRc:
  [28d ≥ 3 and 7d ≥ 1]: [XX] bpm 7d mean([X]) / [XX] bpm 28d mean([X]) ([trend])
  [28d ≥ 3 and 7d = 0]: [XX] bpm 28d mean([X]) — 7d: no data
  [28d < 3 and 7d ≥ 1]: [XX] bpm 7d mean([X]) — 28d: insufficient data
  [28d < 3 and 7d = 0]: omit entire section

Power Curve Delta (28d vs prior 28d — omit section if null):
  Rotation: [+/-X.X] ([sprint-biased/endurance-biased/balanced])
  Notable shifts: [anchor] [+/-X.X]%, [anchor] [+/-X.X]% (list anchors with |pct_change| ≥ 2%)
  [If all |pct_change| < 2%]: No significant shifts

HR Curve Delta (28d vs prior 28d — omit section if null):
  Rotation: [+/-X.X] ([intensity-biased/endurance-biased/balanced])
  Notable shifts: [anchor] [+/-X.X]%, [anchor] [+/-X.X]% (list anchors with |pct_change| ≥ 2%)
  [If rising HR]: Cross-reference with HRV/RHR trends — rising HR is ambiguous
  [If all |pct_change| < 2%]: No significant shifts

Fitness:
  CTL: [XX.X] → [XX.X] (Δ [+/-X.X])
  ATL: [XX.X] → [XX.X]
  TSB: [X.X] → [X.X]
  Recovery Index: [X.XX] ([assessment])
  Ramp rate: [X.XX]
  ACWR: [X.XX] ([interpretation])
  Acute (7d): [XXX] TSS | Chronic (28d avg): [XXX] TSS
  Monotony: [X.XX] ([note]) (omit if ≤2.3)
  Strain: [XXXX] (omit if no monotony flag)

Wellness Trends:
  HRV: [XX]–[XX] ms (avg [XX], prev week [XX]) [↑/↓/→]
  RHR: [XX]–[XX] bpm (avg [XX], prev week [XX]) [↑/↓/→]
  Sleep: [XhYm] avg, quality [X.X]/4 avg [↑/↓/→]
  Avg Feel: [X.X]/5 ([X] sessions) [↑/↓/→]
  Avg RPE: [X.X]/10 ([X] sessions) [↑/↓/→]

Section 11 Flags: [list any triggered flags, or "None"]

Interpretation:
[2-4 sentences — week assessment, compliance, what went well, any flags,
recovery status. Reference Section 11 flag triggers if any were hit.]

Next Week Preview:
[Key sessions planned, any modifications based on this week's data,
focus areas. Reference load targets and phase progression.]
```

---

## Field Definitions

| Field | Source | Notes |
|-------|--------|-------|
| **Compliance** | Planned vs completed activities | ✅ completed as planned, ⚠️ modified, ❌ missed |
| **Quality Session Detail** | Hard/intensity sessions only | Matches post-workout report metrics for consistency |
| **Grey Zone %** | Z3 time / total time | Per Seiler — minimize; target <5% of weekly volume |
| **Quality Intensity %** | Z4+ time / total time | The work that drives adaptation |
| **TID 7d vs 28d** | Seiler classification comparison | Consistent = stable, shifting = classification changed, acute_depolarization = PI dropped |
| **Durability** | Aggregate decoupling from steady-state sessions | VI ≤ 1.05, ≥ 90min, power data. Trend direction matters more than absolute values |
| **Efficiency Factor** | Aggregate EF from steady-state cycling | VI ≤ 1.05, ≥ 20min, power+HR. Rising EF = improving aerobic fitness. Compare like-for-like only |
| **HRRc** | Aggregate heart rate recovery from capability.hrrc | Largest 60s HR drop after threshold. Higher = better. See Notes below for 4-case display rules. Display only when `hrrc` is non-null per activity |
| **Power Curve Delta** | MMP comparison from capability.power_curve_delta | Rotation index + notable anchor shifts (≥2% change). Omit section if power_curve_delta.anchors is null. Sprint-biased (positive rotation) vs endurance-biased (negative) |
| **HR Curve Delta** | Max sustained HR comparison from capability.hr_curve_delta | Rotation index + notable shifts (≥2%). Omit if null. AMBIGUOUS: rising HR may be fitness or fatigue — cross-reference with HRV/RHR/RPE required |
| **ACWR breakdown** | 7d acute / 28d chronic | Show components so athlete understands the ratio |
| **Wellness arrows** | Week-over-week comparison | ↑ improving, ↓ declining, → stable |
| **Avg Feel** | Activity-level average from `weekly_180d.avg_feel` | 1=Strong to 5=Weak. Count = sessions with feel populated. Omit line if 0 sessions. Lower is better |
| **Avg RPE** | Activity-level average from `weekly_180d.avg_rpe` | 1–10 Borg scale. Count = sessions with RPE populated. Omit line if 0 sessions |
| **Section 11 Flags** | Protocol flag triggers | Surface mid-week flags here, don't wait for block report |
| **Ramp rate** | CTL change per week | >1.5 = aggressive, monitor closely |

## Assessment Labels

| Metric | Good | Watch | Flag |
|--------|------|-------|------|
| ACWR | 0.80–1.30 (optimal) | 1.30–1.50 (elevated) | >1.50 (high risk) |
| Ramp rate | <1.0 (conservative) | 1.0–1.5 (moderate) | >1.5 (aggressive) |
| Grey Zone % | <5% (good) | 5–10% (watch) | >10% (too much Z3) |
| Decoupling (per-session) | <5% (good) | 5–10% (elevated) | >10% (flag) |
| Durability (7d mean) | <3% (good) | 3–5% (moderate) | >5% (declining) |
| Durability trend | improving/stable | declining | declining >2% vs 28d |
| EF trend | improving/stable | declining | declining >0.05 vs 28d |
| HRRc trend | improving (7d >10% above 28d) | stable (within 10%) | declining (7d >10% below 28d) |
| TID drift | consistent | shifting | acute_depolarization |
| HRV trend | ↑ or → (stable) | ↓ <5% (minor) | ↓ >10% (flag) |

## Notes

- **Session Breakdown** starts on Monday (or user's configured week start)
- **Phase narrative** is constructed from `phase_detection` fields: `phase_detection.phase` + `phase_detection.phase_duration_weeks` + `phase_detection.confidence`. If `phase_detection.previous_phase` differs from current phase, add transition note. Optionally surface 1-2 key `reason_codes` in plain English (e.g., `BUILD_HISTORY_REDUCED_LOAD_REBOUND_CONFIRMED` → "load resumed after deload")
- **Quality Session Detail** only includes hard/intensity sessions — omit recovery/endurance rides unless metrics were notable. Cap at 2–3 key sessions per week; if 4+ hard days occurred, prioritize sessions with the most notable targets, flags, or breakthroughs
- **HRRc** — four display cases: (1) 28d ≥ 3 and 7d ≥ 1: full trend line `[XX] bpm 7d mean([X]) / [XX] bpm 28d mean([X]) ([trend])`; (2) 28d ≥ 3 and 7d = 0: `[XX] bpm 28d mean([X]) — 7d: no data`; (3) 28d < 3 and 7d ≥ 1: `[XX] bpm 7d mean([X]) — 28d: insufficient data`; (4) 28d < 3 and 7d = 0: omit entire section. Per-session HRRc can still appear in Quality Session Detail when present. HRRc is context-dependent: varies with exercise intensity, type, and when recording stopped. Trend direction over multiple sessions matters; single-session values are noisy
- **Section 11 Flags** should surface immediately in weekly reports, not deferred to block reports
- **Wellness arrows** use simple thresholds: >5% change from previous week = ↑ or ↓, otherwise →
- Keep "Interpretation" concise — this is coaching interpretation, not data repetition

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format — the formatted values are pre-calculated from raw seconds and avoid rounding errors.
