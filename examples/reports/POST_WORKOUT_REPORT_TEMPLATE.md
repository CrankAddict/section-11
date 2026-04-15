# Post-Workout Report Template

> This template defines the standard output format for post-workout reports.  
> Fields in `[brackets]` are placeholders. Omit fields that don't apply to the activity type.

---

```
Data (last_updated UTC: [YYYY-MM-DDTHH:MM:SS])

[One-line summary of completed session(s) and key observation.]

Completed workout: [ActivityType] [WorkoutName]
Start time: [HH:MM:SS]
Duration: [XhYm] (planned [XhYm])
Distance: [XX.X] km
Power: [XXX] W avg / [XXX] W NP
Power zones: [XX]% Zone 1, [XX]% Zone 2
Grey Zone (Z3): [XX]%
Quality (Z4+): [XX]%
Session profile: [Classification]
HR: [XXX] avg / [XXX] max
HR zones: [XX]% Zone 1, [XX]% Zone 2
Cadence: [XX] avg
Decoupling: [X.XX]%
EF: [X.XX]
HRRc: [XX] bpm [omit line if null]
Variability Index: [X.XX] ([assessment])
DFA a1: [X.XX] avg, [X]% Z2/[X]% transition/[X]% SS/[X]% above LT2 ([drift summary if applicable]) [omit line entirely if no dfa block on this activity; one-line notice if dfa block present but sufficient=false]
Calories: [XXXX] kcal
Carbs used: [XXX] g
TSS: [XXX] (planned [XXX])
Feel: [X/5] ([label])
RPE: [X/10]
Note: [description or chat_notes text]

[Repeat block for every completed activity whose date falls on the report day (athlete local time). One block per activity ID — never merge. Include walks, ski-erg, short rides, aborted rides, commutes. Never drop secondary sessions. Within a block, omit only fields the activity type does not have (e.g., no power for a walk).]

Weekly totals (rolling 7d):
Phase: [phase_detection.phase] Wk[phase_detection.phase_duration_weeks]
Polarization: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]% — [Classification] (PI: [X.XX])
Durability: [X.XX]% 7d mean([X]) / [X.XX]% 28d mean([X]) ([trend])
EF: [X.XX] 7d mean([X]) / [X.XX] 28d mean([X]) ([trend])
HRRc: [XX] bpm 7d mean([X]) / [XX] bpm 28d mean([X]) ([trend]) [omit if 28d < 3 sessions; if 7d = 0: "[XX] bpm 28d mean([X]) — 7d: no data"]
TID 28d: [Classification] (PI: [X.XX]) — drift: [consistent/shifting/acute_depolarization]
TSB: [X.XX]
CTL: [XX.XX]
ATL: [XX.XX]
Ramp rate: [X.XX]
ACWR: [X.XX] ([assessment])
Recovery Index: [X.XX]
Hours: [XhYm]
TSS: [XXX]

Interpretation:
[2-4 sentences: compliance check, key quality metrics, load context, recovery note if applicable.]

Tomorrow: [WorkoutType] [Duration], [main set condensed, e.g., "3×12m @260W"]
[Use workout_summary as source. Condense to main set — omit warmup/cooldown/recovery steps. If workout_summary is null, use description_preview.]
[If multiple planned workouts tomorrow, list ALL sessions joined with " + " in start-time order:
 "Tomorrow: Endurance 2h15m, 1h30m @173W + SkiErg 10m Z2 HR"]
[Never drop secondary sessions. Omit the Tomorrow line only if no planned sessions exist tomorrow.]
```

---

## Rounding Convention

Round zone percentages to the nearest **whole number** (1%). The JSON data source carries precise values for detailed analysis. A few seconds in a zone is noise, not signal — report `0%` not `0.1%`.

## Field Notes

| Field | When to include | Notes |
|-------|----------------|-------|
| Distance | Cycling, running | Omit for SkiErg, strength |
| Power / Power zones | Activities with power data | Omit if no power meter |
| Grey Zone / Quality | Always for cycling | Highlights polarization compliance |
| Session profile | Activities with zone data | Per-session intensity classification based on **executed** zone distribution (e.g., Recovery, Endurance, Tempo, Sweetspot, Threshold, VO2max, Anaerobic, Neuromuscular, Mixed). When the planned workout name and the executed character disagree, classify by what was actually done — IF and zone-time distribution — not by the planned label. Sweetspot requires VI ≤ 1.05; sessions averaging IF 0.88–0.94 with VI > 1.05 classify by dominant power zone instead |
| Cadence | Cycling, running | Omit for SkiErg, strength |
| Decoupling | Sessions ≥ 1 hour | Key aerobic efficiency marker. Per-session scale (<5% good) per Friel/Coggan. Aggregate durability uses tighter scale (<3% good) |
| EF | Activities with power + HR | Aerobic efficiency (NP ÷ HR); track trend over like-for-like sessions. Absolute value is individual-dependent |
| HRRc | Activities where HR exceeded threshold for >1min | Heart rate recovery (largest 60s HR drop in bpm). Higher = faster parasympathetic recovery. Absent on easy rides, rides stopped before cooldown, or no HR data. Omit line when null |
| Variability Index | Cycling with power | 1.00–1.05 = steady, >1.05 = variable. Assessment labels apply to steady-state only; omit label for interval sessions where high VI is expected |
| DFA a1 | Activities with a `dfa` block in `intervals.json` | **Source:** session-level `dfa.avg` (artifact-filtered) plus the four `tiz_*_pct` bands. Use the session-level rollup, **not** per-interval `avg_dfa_a1` from interval segments — that field is the unfiltered Intervals.icu value, present only for completeness. Do not average it across intervals. **Branching:** (a) `dfa` block absent → omit the line entirely, do not announce absence; (b) `dfa` present with `quality.sufficient: false` → one-line notice "DFA a1: AlphaHRV recorded, quality below threshold ([X]% valid) — no reading"; (c) `sufficient: true` → full line. **Drift summary:** include `(drift [+/−X.XX], [interpretable/structural])` only when `drift` block present. When drift is interpretable AND significantly negative on a steady-state ride, address it in the Interpretation section per **DFA a1 Protocol §Session Interpretation Rules** — cross-reference fueling, heat (Environmental Conditions Protocol), and accumulated fatigue. Do not invent thresholds inline; the protocol owns them. **Validated sports only:** the protocol's interpretive rules apply to cycling. For other sports, surface the values descriptively but do not draw threshold conclusions |
| Carbs used | Sessions with power data | Omit if unavailable |
| Feel | Omit line if null | 1=Strong, 2=Good, 3=Normal, 4=Poor, 5=Weak. Set in Intervals.icu or pushed from device (e.g. Garmin post-ride prompt). Can appear on any activity type |
| RPE | Omit line if null | Rate of Perceived Exertion, 1–10 scale. Set in Intervals.icu or pushed from device. Can appear on any activity type |
| Note | Omit line if neither present | Athlete's own text or coach messages attached to the activity. If both `description` and `chat_notes` exist, combine. Omit line entirely when neither is present |
| Heat context | When `avg_temp` indicates Tier 1+ heat stress (delta above 14d thermal baseline, or absolute fallback) | Contextualize decoupling, power, and RPE against temperature in the Interpretation section. Do not flag heat-elevated decoupling as durability decline. See **Environmental Conditions Protocol** in SECTION_11.md |
| Durability (weekly) | Aggregate decoupling 7d/28d | Steady-state sessions only (VI ≤ 1.05, ≥ 90min). Trend direction matters more than absolute value |
| EF (weekly) | Aggregate EF 7d/28d | Steady-state cycling only (VI ≤ 1.05, ≥ 20min). Trend direction matters more than absolute value |
| TID 28d (weekly) | 28d Seiler classification + drift | Shows whether acute TID matches chronic pattern. Always include drift label |
| Weekly totals (rolling 7d) | Always | Rolling 7-day window (last 7 days including today). Not calendar week. |

## Assessment Labels

| Metric | Good | Watch | Flag |
|--------|------|-------|------|
| Decoupling (per-session) | < 5% | 5–10% | > 10% |
| Variability Index | ≤ 1.05 | 1.05–1.10 | > 1.10 |
| ACWR | 0.8–1.3 | 1.3–1.5 | > 1.5 or < 0.8 |
| Grey Zone (Z3) | < 5% (base) | 5–10% | > 10% (base phase) |
| Durability (7d mean) | < 3% (good) | 3–5% (moderate) | > 5% (declining) |
| EF trend | improving/stable | — | declining |
| DFA a1 (cycling, sufficient) | Internal response matches prescription (Z2 ride holds tiz_below_lt1 high; SS holds in transition_lt2 band) | Mild mismatch — note in Interpretation | Significant mismatch OR interpretable negative drift on Z2 ride |
| TID drift | consistent | shifting | acute_depolarization |

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format — the formatted values are pre-calculated from raw seconds and avoid rounding errors.
