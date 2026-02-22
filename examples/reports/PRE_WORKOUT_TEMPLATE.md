# Pre-Workout Report Template

> This template defines the standard output format for pre-workout reports.  
> Fields in `[brackets]` are placeholders. Omit fields that don't apply.

---

```
Data last_updated (UTC): [YYYY-MM-DDTHH:MM:SS]

Weather ([Location]): [icon] [temp]°C, [humidity]% humidity, [conditions], wind [speed] m/s from [direction].
Coach note: [Brief weather-relevant tip. Omit if no actionable weather context.]

Current Status Summary:
RHR: [XX] bpm (baseline: [XX] bpm)
HRV: [XX] ms (7d avg: [XX] ms)
Sleep Hours: [X.XX] hours
Sleep Quality: [X/4]
TSB: [X.XX]
CTL: [XX.XX]
ATL: [XX.XX]
ACWR: [X.XX] ([assessment])
Recovery Index: [X.XX] ([assessment])
Ramp Rate: [X.XX]
Load/Recovery: [X.X] (tolerance [X.X]) — [context note if near edge]
Polarization: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]% — [Classification] (PI: [X.XX]) [TID drift: shifting/depolarizing — only if not consistent]
Durability: [X.XX]% 7d mean ([trend]) — [X] qualifying sessions
Monotony: [X.XX] ([primary sport] [X.XX], total [X.XX]) — [note]
Total hours, last 7 days: [XX.XX] hours
Total activities, last 7 days: [XX]
Total TSS, last 7 days: [XXX]

Planned Workouts for Today (Planned TSS: [XXX]):
[WorkoutType] [Duration] — [structure/targets]

[If rest day: "Rest day — no sessions scheduled."]
[If rest day: "Next session: [Day] — [workout preview]"]

Recommendation: [Go / Modify / Skip]

Interpretation:
[Readiness assessment: 1-2 sentences on HRV, RHR, sleep vs baselines]
[Load context: TSB meaning, freshness/fatigue state]
[Suitability: proceed / modify / skip with rationale]
[Coach note: brief motivational or practical tip]
```

---

## Conditional Fields

| Field | Rule |
|-------|------|
| Weather | Include if athlete location is available via profile or memory |
| Coach note (weather) | Include only if actionable (e.g., dress warm, indoor day) |
| Monotony | Include **only** if > 2.3. Omit entirely when normal |
| Durability | Include if qualifying sessions exist. Omit if 0 qualifying sessions in 7d |
| TID drift | Append to Polarization line **only** if drift is "shifting" or "acute_depolarization". Omit when "consistent" |
| Load/Recovery context | Include tolerance note only when within 0.2 of threshold |
| Next session | Include only on rest days |
| Modify/Skip rationale | Required when recommendation is not "Go" |

## Readiness Decision Logic

| Signal | Go | Modify | Skip |
|--------|-----|--------|------|
| HRV | Within ±10% of 7d avg | ↓ 10-20% | ↓ >20% |
| RHR | At or below baseline | ↑ 3-4 bpm | ↑ ≥5 bpm |
| Sleep | ≥ 7h, quality 1-2 | 5-7h or quality 3 | < 5h or quality 4 |
| TSB | > -15 | -15 to -25 | < -25 |
| ACWR | 0.8–1.3 | 1.3–1.5 | > 1.5 |
| Feel | ≤ 3/5 | 4/5 | ≥ 4/5 + other flags |

> A single amber signal doesn't require modification. **Two or more amber signals** or **any red signal** should trigger Modify or Skip.

## Brevity Rule

- **Normal metrics, Go recommendation:** Keep interpretation to 2-3 sentences
- **Threshold breach or Modify/Skip:** Expand with specific reasoning
- **Rest day:** Brief — confirm recovery status, preview next session
