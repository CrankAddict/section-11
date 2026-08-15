# Pre-Workout Report Template

> This template defines the standard output format for pre-workout reports.  
> Fields in `[brackets]` are placeholders. Omit fields that don't apply.  
> **Data Freshness:** Every numeric value in a report must come from a current read of its source JSON file. Do not carry forward values from earlier reports or earlier in the conversation — re-read before quoting.  
> **Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON — they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. See SECTION_11.md §Display Unit Semantics.

---

```
Data last_updated (UTC): [YYYY-MM-DDTHH:MM:SS]

Weather ([Location]): [icon] [temp][weather_summary.units.temp], [humidity]% humidity, [conditions], wind [speed] [weather_summary.units.wind] from [direction].
Coach note: [Brief weather-relevant tip. Omit if no actionable weather context.]

Current Status Summary:
Phase: [phase_detection.phase] Wk[phase_detection.phase_duration_weeks]
RHR: [XX] bpm (baseline: [XX] bpm)
HRV: [XX] ms (7d avg: [XX] ms)
Sleep: [XhYm]
Sleep Quality: [X/4]
TSB: [X.XX]
CTL: [XX.XX]
ATL: [XX.XX]
ACWR: [X.XX] ([assessment]) — start-of-day
Recovery Index: [X.XX] ([assessment])
Ramp Rate: [X.XX]
Load/Recovery: [X.X] (tolerance [X.X]) — [context note if near edge]
Polarization: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]% — [Classification] (PI: [X.XX])
TID 28d: [Classification] (PI: [X.XX]) — drift: [shifting/acute_depolarization] [only if not consistent]
Durability: [X.XX]% 7d mean([X]) ([trend])
EF: [X.XX] 7d mean([X]) ([trend])
Monotony: [X.XX] ([primary sport] [X.XX], total [X.XX]) — [note]
Total hours, last 7 days: [XhYm]
Total activities, last 7 days: [XX]
Total TSS, last 7 days: [XXX]

Planned Workouts for Today (Planned TSS: [XXX]):
[WorkoutType] [Duration] — [main set condensed, e.g., "3×12m @260W"]
[Use workout_summary as source. Condense to main set — omit warmup/cooldown/recovery steps. If workout_summary is null, use description_preview.]

[If rest day: "Rest day — no sessions scheduled."]
[If rest day: "Next session: [Day] — [workout preview]"]

Terrain Context ([course_character], [terrain_summary.display.total_distance.value] [terrain_summary.display.total_distance.unit], [terrain_summary.display.total_elevation.value][terrain_summary.display.total_elevation.unit]):
[Key climbs condensed — quote `display.position` / `display.distance` for each climb, e.g. "Cat 2 at [climb.display.position] (6.8 km, 6.3% avg, max 11%)". Use the climb's `display.*` for distance/position/elevation; gradient % is unit-universal.]
[Pacing note: one sentence connecting terrain to today's effort strategy.]

Recommendation: [readiness_decision.recommendation — Go / Modify / Skip]

Interpretation:
[2-4 sentences: readiness vs baselines, load context,
suitability (proceed/modify/skip with rationale), coach tip.
Use readiness_decision.signals for individual signal values.
If recommendation is Modify, reference readiness_decision.modification
for adjustment directions (intensity/volume/cap_zone).
AI may adjust the recommendation only under the override rules in SECTION_11.md
(Feel/RPE Override): athlete-reported state escalates unconditionally, de-escalation
is P2-only, P0 and P1 are not overridable. State the rationale.]
```

---

## Conditional Fields

| Field | Rule |
|-------|------|
| Phase | Include only when `phase_detection.confidence` is "high" or "medium". Omit when "low" or phase is null |
| Weather | Include if athlete location is available via profile or memory |
| Coach note (weather) | Include only if actionable (e.g., dress warm, indoor day). When forecast triggers heat stress Tier 1+: Tier 1 — note hydration emphasis. Tier 2 — specify session modification per Environmental Conditions Protocol session-type rules (e.g., "Threshold intervals planned — keep power targets, consider reducing from 4×8min to 3×8min"). Tier 3 — recommend reschedule or endurance-only. See **Environmental Conditions Protocol** in SECTION_11.md for tier definitions and session-type rules. |
| Monotony | Include **only** if > 2.3. Omit entirely when normal |
| Durability | Include if qualifying sessions exist. Omit if 0 qualifying sessions in 7d |
| EF | Include if qualifying sessions exist. Omit if 0 qualifying sessions in 7d |
| TID 28d + drift | Include as separate line **only** if drift is "shifting" or "acute_depolarization". Omit entire line when "consistent" |
| Polarization | Weekly Seiler TID rendered in power-zone labels. Source: `seiler_tid_7d.z1_pct/z2_pct/z3_pct`. Render as `Z1+Z2` (Seiler Easy / below LT1), `Z3` (Seiler Grey Zone / LT1–LT2), `Z4+` (Seiler Hard / above LT2). Do not output raw `Z1/Z2/Z3` labels — they collide with the per-session Power zones line above |
| Load/Recovery context | Include tolerance note only when within 0.2 of threshold |
| Next session | Include only on rest days |
| Terrain Context | Include when `has_terrain: true` on a planned event and `routes.json` has the corresponding terrain data. Omit entirely otherwise. Full pre-ride briefing available on request |
| Modify/Skip rationale | Required when recommendation is not "Go" |
| Same-day continuation | Include only when a session has already been completed today and a further session is in question. When triggered, output the **Same-Day Continuation Block** in place of the standard report body — not alongside it. Omit entirely on a first session of the day |

## Readiness Decision Logic

The `readiness_decision` object in `latest.json` provides a pre-computed go/modify/skip recommendation with priority level and individual signal statuses. Use this as the baseline.

**Signal statuses** are in `readiness_decision.signals` (hrv, rhr, sleep, tsb, acwr, ri — each with green/amber/red/unavailable and raw values).

**Phase-adjusted thresholds** are in `readiness_decision.phase_context` (shows which phase modifier shifted the amber threshold).

**Modification guidance** is in `readiness_decision.modification` when recommendation is "modify" (trigger categories + adjustment directions: intensity/volume/cap_zone).

> The `readiness_decision` is the deterministic baseline. The AI may adjust it only under the override rules in **Feel/RPE Override**: athlete-reported state escalates (Go → Modify → Skip) unconditionally; de-escalation is permitted at P2 only, with no more than 2 ambers and an attributed non-training cause; **P0 and P1 are not overridable**. Where contextual factors support a permitted adjustment, state them in the Interpretation section.
>
> `signals.acwr` is the **start-of-day** value — the same windows with today's activities excluded — so it does not move when a session is completed today. `derived_metrics.acwr` is live and today-inclusive: retrospective load context only, never used to approve, modify or veto a later same-day session or tomorrow's.
>
> **Sourcing the ACWR status line:** value from `readiness_decision.signals.acwr.value`, label from `derived_metrics.acwr_start_of_day.interpretation`. Do not read `derived_metrics.acwr` for this line — that is the live figure and belongs in the post-workout report.

For the full priority ladder (P0–P3) and signal classification thresholds, see **Readiness Decision** in the protocol.

## Same-Day Continuation Block

Use when a session has already been completed today and a later session is in question. When this block applies it **replaces the standard report body** — do not also emit Current Status Summary, Planned Workouts, Recommendation or Interpretation. See **Same-day Continuation** in SECTION_11.md for the decision rules.

```
Same-day continuation: [Go / Modify / Skip]

Morning readiness: [recommendation] P[priority] — [one-line reason]
Completed session: [type, duration] — [within/above/below intent; goal attained?]
Response: [RPE vs work performed; Feel at the time; power-to-HR evidence if the session passes the validity gate, otherwise "not eligible"]
Current state: [solicited — Feel now, soreness, any new pain or symptoms]
Remaining session: [planned/added; purpose and cost]
Decision: [one sentence]
ACWR: start-of-day [X.XX] — live post-session value excluded from this decision
```

- Current Feel must be solicited, not read from `recent_activities[].feel`
- Quote decoupling or EF only when the session passes its gate (`variability_index` ≤ 1.05 and > 0; `duration_formatted` ≥ 90 min for decoupling, ≥ 20 min for EF). Otherwise state that the evidence is not eligible rather than omitting the line silently
- `effort_response: null` is expected on an easy session and is not a data gap. The classifier is calibrated only at IF ≥ 0.65; `intensity_factor` is emitted on a 0–100+ percentage scale, so the cut-off reads as 65 in the JSON and 0.65 as a decimal IF

## Brevity Rule

- **Normal metrics, Go recommendation:** Keep interpretation to 2-3 sentences
- **Threshold breach or Modify/Skip:** Expand with specific reasoning
- **Rest day:** Brief — confirm recovery status, preview next session

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format — the formatted values are pre-calculated from raw seconds and avoid rounding errors.
