# Weekly Report Template

**Structure only — no data. Replace `[placeholders]` with actual values.**

Generated at end of training week (Saturday or Sunday morning).

---

## Template Structure

```
Week [X] Summary ([date range])
Block: [Name] — Week [X/Y]
Phase: [Base/Build/Peak/Taper/Recovery]

Compliance: [X/X] sessions completed
Planned TSS: [XXX] | Actual TSS: [XXX] ([XX]%)
Hours: [XX.X]h (prev week: [XX.X]h)

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
    Decoupling: [X.XX]% ([assessment])
    VI: [X.XX] ([assessment])
    HR: [XXX] avg / [XXX] max
  [Session 2 name]:
    Target: [XXX]W | Actual: [XXX]W avg / [XXX]W NP
    Decoupling: [X.XX]% ([assessment])
    VI: [X.XX] ([assessment])
    HR: [XXX] avg / [XXX] max

Polarization:
  Z1+Z2: [XX.X]%
  Z3 (Grey Zone): [X.X]% (target <5%)
  Z4+ (Quality): [X.X]% (target ~20% of intensity sessions)
  Classification 7d: [Classification] (PI: [X.XX]) | 28d: [Classification] (PI: [X.XX]) — [drift status]

Durability (steady-state sessions, VI ≤ 1.05, ≥ 90min):
  7d mean: [X.XX]% ([X] sessions) | 28d mean: [X.XX]% ([X] sessions)
  Trend: [improving/stable/declining] | High drift (>5%): [X] sessions

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
  Sleep: [X.X]h avg, quality [X.X]/4 avg [↑/↓/→]

Section 11 Flags: [list any triggered flags, or "None"]

Overall:
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
| **ACWR breakdown** | 7d acute / 28d chronic | Show components so athlete understands the ratio |
| **Wellness arrows** | Week-over-week comparison | ↑ improving, ↓ declining, → stable |
| **Section 11 Flags** | Protocol flag triggers | Surface mid-week flags here, don't wait for block report |
| **Ramp rate** | CTL change per week | >1.5 = aggressive, monitor closely |

## Assessment Labels

| Metric | Good | Watch | Flag |
|--------|------|-------|------|
| ACWR | 0.80–1.30 (optimal) | 1.30–1.50 (elevated) | >1.50 (high risk) |
| Ramp rate | <1.0 (conservative) | 1.0–1.5 (moderate) | >1.5 (aggressive) |
| Grey Zone % | <5% (excellent) | 5–10% (watch) | >10% (too much Z3) |
| Decoupling | <5% (good) | 5–10% (moderate) | >10% (drift) |
| Durability (7d mean) | <3% (good) | 3–5% (moderate) | >5% (declining) |
| Durability trend | improving/stable | declining | declining >2% vs 28d |
| TID drift | consistent | shifting | acute_depolarization |
| HRV trend | ↑ or → (stable) | ↓ <5% (minor) | ↓ >10% (flag) |

## Notes

- **Session Breakdown** starts on Monday (or user's configured week start)
- **Quality Session Detail** only includes hard/intensity sessions — omit recovery/endurance rides unless metrics were notable. Cap at 2–3 key sessions per week; if 4+ hard days occurred, prioritize sessions with the most notable targets, flags, or breakthroughs
- **Section 11 Flags** should surface immediately in weekly reports, not deferred to block reports
- **Wellness arrows** use simple thresholds: >5% change from previous week = ↑ or ↓, otherwise →
- Keep "Overall" concise — this is coaching interpretation, not data repetition
