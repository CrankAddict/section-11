# Pre-Workout Report Template

> This template defines the standard output format for pre-workout reports.  
> Fields in `[brackets]` are placeholders. Omit fields that don't apply.

---

```
Data last_updated (UTC): [YYYY-MM-DDTHH:MM:SS]

Weather ([Location]): [icon] [temp]°C, [humidity]% humidity, [conditions], wind [speed] m/s from [direction].
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
ACWR: [X.XX] ([assessment])
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

Recommendation: [readiness_decision.recommendation — Go / Modify / Skip]

Interpretation:
[2-4 sentences: readiness vs baselines, load context,
suitability (proceed/modify/skip with rationale), coach tip.
Use readiness_decision.signals for individual signal values.
If recommendation is Modify, reference readiness_decision.modification
for adjustment directions (intensity/volume/cap_zone).
AI may override the pre-computed recommendation with explicit rationale.]
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
| Load/Recovery context | Include tolerance note only when within 0.2 of threshold |
| Next session | Include only on rest days |
| Modify/Skip rationale | Required when recommendation is not "Go" |

## Readiness Decision Logic

The `readiness_decision` object in `latest.json` provides a pre-computed go/modify/skip recommendation with priority level and individual signal statuses. Use this as the baseline.

**Signal statuses** are in `readiness_decision.signals` (hrv, rhr, sleep, tsb, acwr, ri — each with green/amber/red/unavailable and raw values).

**Phase-adjusted thresholds** are in `readiness_decision.phase_context` (shows which phase modifier shifted the amber threshold).

**Modification guidance** is in `readiness_decision.modification` when recommendation is "modify" (trigger categories + adjustment directions: intensity/volume/cap_zone).

> The AI may override the pre-computed recommendation with explicit rationale in the Interpretation section. The `readiness_decision` is the deterministic baseline, not a constraint. If contextual factors (dossier notes, conversation history, athlete-reported info) suggest a different call, explain why.

For the full priority ladder (P0–P3) and signal classification thresholds, see **Readiness Decision** in the protocol.

## Brevity Rule

- **Normal metrics, Go recommendation:** Keep interpretation to 2-3 sentences
- **Threshold breach or Modify/Skip:** Expand with specific reasoning
- **Rest day:** Brief — confirm recovery status, preview next session

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format — the formatted values are pre-calculated from raw seconds and avoid rounding errors.
