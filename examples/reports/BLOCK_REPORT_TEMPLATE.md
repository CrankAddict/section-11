# Block Report Template

**Structure only — no data. Replace `[placeholders]` with actual values.**

**Data Freshness:** Every numeric value in a report must come from a current read of its source JSON file. Do not carry forward values from earlier reports or earlier in the conversation — re-read before quoting.

**Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON — they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. W/kg, kJ, IF, % are universal physics units, not pref-dependent. See SECTION_11.md §Display Unit Semantics.

Generated at end of each training block (3–5 weeks).

---

## Template Structure

```
Block [X] Report ([date range])
Weeks in block: [3/4/5]
Phase: [Base Build / Threshold Development / Peak / etc.]
Phase Timeline:
  Wk 1: [phase] ([confidence])
  Wk 2: [phase] ([confidence])
  Wk 3: [phase] ([confidence])
  [Wk 4: [phase] ([confidence])]

Volume Progression:
  Wk 1: [XX.X]h / [XXX] TSS | CTL [XX.X]
  Wk 2: [XX.X]h / [XXX] TSS | CTL [XX.X]
  Wk 3: [XX.X]h / [XXX] TSS | CTL [XX.X]
  [Wk 4: deload — [XX.X]h / [XXX] TSS | CTL [XX.X]]
  Block total: [XX.X]h / [XXXX] TSS

Compliance:
  Sessions: [XX/XX] completed ([XX]%)
  Missed/modified: [list with brief reason, or "None"]

Fitness Progression:
  CTL: [XX.X] → [XX.X] (Δ [+/-X.X])
  ATL: [XX.X] → [XX.X]
  TSB: [X.X] → [X.X]
  Avg ramp rate: [X.XX]/week
  FTP: [XXX]W → [XXX]W ([change or "unchanged"])
  eFTP: [XXX]W → [XXX]W

Key Performance Markers:
  Sweetspot power: [XXX]W → [XXX]W (target: [XXX]W — [hit/miss])
  VO2max power: [XXX]W → [XXX]W (target: [XXX]W — [hit/miss])
  Long ride duration: [XhYm] → [XhYm]
  Long ride decoupling trend: [X.X]% → [X.X]% [↑/↓/→]
  Best 20-min power: [XXX]W (week [X])
  Best 5-min power: [XXX]W (week [X])
  Power curve rotation: [+/-X.X] ([sprint-biased/endurance-biased/balanced])
  Strongest adaptation: [anchor] ([+/-X.X]%) — omit both lines if power_curve_delta null
  HR curve rotation: [+/-X.X] ([intensity-biased/endurance-biased/balanced])
  HR context: [cross-ref with HRV/RHR trend] — omit both lines if hr_curve_delta null

Sustainability Ceilings (omit section if sustainability_profile null):
  Coverage: [X/Y] anchors observed ([XX]%) — [sport]
  [duration]: [XXX]W ([X.XX] W/kg) — [source] | Coggan [XXX]W | CP model [XXX]W | divergence [+/-X.X]%
  [duration]: [XXX]W ([X.XX] W/kg) — [source] | Coggan [XXX]W | CP model [XXX]W | divergence [+/-X.X]%
  [repeat per observed anchor — skip anchors with null actual_watts]
  FTP used: [XXX]W | W′: [XXXXX]J | FTP staleness: [XX] days
  Model trust: CP/W′ primary ≤20min, Coggan reference ≥60min
  [For non-cycling sports: show actual_watts + actual_hr + pct_lthr only, no model columns]
  Block-over-block: [did ceilings move? did coverage improve? did model divergence shift?]

DFA a1 Calibration (omit section entirely if dfa_a1_profile null, OR cycling block missing, OR trailing_by_sport.cycling.confidence in {null, "low"}, OR trailing_by_sport.cycling.validated false):
  Sessions in window: [N] sufficient (LT1 crossings: [X], LT2 crossings: [Y])
  Confidence: [moderate / high]
  Average DFA a1: [X.XX] (drift mean: [+/-X.XX])
  Empirical LT1: [XXX] bpm (from [N] sessions) / outdoor [XXX] W (from [N] sessions) / indoor [XXX] W (from [N] sessions) [omit environment line if n_sessions_outdoor or n_sessions_indoor is 0]
  Empirical LT2: [XXX] bpm (from [N] sessions) / outdoor [XXX] W (from [N] sessions) / indoor [XXX] W (from [N] sessions) [omit line if lt2_estimate null — happens when athlete rarely crosses 0.5; omit environment if n_sessions is 0]
  Dossier LT1 (cycling): [XXX] bpm / outdoor [XXX] W / indoor [XXX] W
  Dossier LT2 (cycling): [XXX] bpm / outdoor [XXX] W / indoor [XXX] W
  Delta: [LT1 outdoor +X% / LT1 indoor -Y% / LT2 outdoor +Z% / no notable delta] [report only deltas >5% per DFA a1 Protocol §Zone Validation Use; per-environment watts deltas require environment-specific n_sessions ≥4 for moderate confidence]
  [If delta surfaced: 1-2 sentence note flagging the delta as a coaching observation, NOT an auto-update. Recommend formal retest before any dossier change.]

Polarization (block average):
  Z1+Z2: [XX]%
  Z3 (Grey Zone): [X]% (target <5%)
  Z4+ (Quality): [X]% (target ~20% of intensity sessions)
  TID 28d (block-scale): [Classification] (PI: [X.XX])
  Hard days/week avg: [X.X]

Polarization by Week:
  Wk 1: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]%
  Wk 2: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]%
  Wk 3: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]%
  Wk 4: Z1+Z2 [XX]%, Z3 [X]%, Z4+ [X]%

Durability by Week:
  Wk 1: mean([X]) dec [X.X]%, [X] high-drift
  Wk 2: mean([X]) dec [X.X]%, [X] high-drift
  Wk 3: mean([X]) dec [X.X]%, [X] high-drift
  Wk 4: mean([X]) dec [X.X]%, [X] high-drift
  Block trend: [improving/stable/declining]

Efficiency Factor by Week:
  Wk 1: mean([X]) EF [X.XX]
  Wk 2: mean([X]) EF [X.XX]
  Wk 3: mean([X]) EF [X.XX]
  Wk 4: mean([X]) EF [X.XX]
  Block trend: [improving/stable/declining]

HRRc by Week (omit section if block total < 3 qualifying sessions):
  Wk 1: mean([X]) [XX] bpm [or "— no data" if 0 qualifying]
  Wk 2: mean([X]) [XX] bpm
  Wk 3: mean([X]) [XX] bpm
  Wk 4: mean([X]) [XX] bpm
  Block trend: [improving/stable/declining]

Wellness (block avg vs previous block):
  HRV: [XX] ms (prev block: [XX] ms) [↑/↓/→] [assessment]
  RHR: [XX] bpm (prev block: [XX] bpm) [↑/↓/→] [assessment]
  Sleep: [XhYm] (prev block: [XhYm]) [↑/↓/→] [assessment]
  Avg Feel: [X.X]/5 ([X] sessions) (prev block: [X.X]/5)
  Avg RPE: [X.X]/10 ([X] sessions) (prev block: [X.X]/10)
  Avg RI: [X.XX] (prev block: [X.XX])
  Avg Monotony: [X.XX] ([note])

Section 11 Flags During Block:
  [List each flag with date and resolution, or "None"]

Phase Progression Check:
  Block objective: [what this block was designed to achieve]
  Criteria met: [Y/N — reference Section 11 phase detection triggers]
  Phase recommendation: [Continue current / Progress to next / Extend / Insert recovery]
  Rationale: [1-2 sentences explaining why, based on metrics above]

Interpretation:
[3-5 sentences — did the block achieve its goals? What adapted?
What stalled? Recovery status entering next block. Key wins and
concerns. Block-over-block comparison where relevant.]

Next Block Plan:
  Phase: [planned phase]
  Duration: [X] weeks
  Focus: [primary training objective]
  Key changes: [what's different from this block]
  Targets: [specific metrics to hit — CTL target, FTP test date, etc.]
```

---

## Field Definitions

| Field | Source | Notes |
|-------|--------|-------|
| **Volume Progression** | Weekly hours + TSS + CTL | Week-by-week CTL shows load trajectory, not just endpoints |
| **Compliance** | Planned vs completed across block | Include reasons for misses — illness, fatigue, life |
| **Fitness Progression** | Start vs end of block | CTL delta is the headline number |
| **eFTP** | Intervals.icu estimated FTP | Track alongside formal FTP — catches drift |
| **Performance Markers** | Best efforts + target comparison | Shows whether stimulus is producing adaptation |
| **Power Curve Rotation** | rotation_index from capability.power_curve_delta | Sprint-biased (positive) vs endurance-biased (negative) adaptation across the block. Omit if null |
| **HR Curve Rotation** | rotation_index from capability.hr_curve_delta | Intensity-biased (positive) vs endurance-biased (negative) HR shift. AMBIGUOUS — cross-reference with HRV/RHR. Omit if null |
| **Sustainability Ceilings** | capability.sustainability_profile.{sport}.anchors | Per-sport MMP + HR at race-relevant durations. Cycling: Coggan + CP/W' model layers with divergence. Coverage ratio flags data gaps. Block-over-block: compare ceilings, coverage, and divergence shift. Omit if null |
| **DFA a1 Calibration** | capability.dfa_a1_profile.trailing_by_sport.cycling | Empirical LT1/LT2 estimates from artifact-filtered AlphaHRV data, surfaced only when cycling block present, validated=true, and confidence is moderate or high. HR estimates are pooled across all sessions. Watts estimates are split by environment: `watts_outdoor` / `watts_indoor` (always present, null when no sessions in that environment). Compare `watts_outdoor` against dossier `ftp`, `watts_indoor` against `ftp_indoor`. Per-environment `n_sessions_outdoor` / `n_sessions_indoor` must meet the same 3/4–5/≥6 confidence thresholds before surfacing a watts calibration delta for that environment. If only one environment has sufficient data and the dossier lacks a threshold for the other, the available estimate may inform directionally with cross-environment caveat. Never auto-updates dossier zones. lt2_estimate may be null even at moderate/high confidence if the athlete rarely crosses 0.5 — that's by design, surface lt1 only in that case. See `lt1_crossing_sessions` / `lt2_crossing_sessions` for diagnostic counts. Tier-2 interpretive signal — does NOT affect the Phase Progression Check |
| **Decoupling trend** | Long ride aerobic efficiency | Improving decoupling = aerobic base building |
| **Polarization by Week** | Weekly zone distributions | Catches grey zone creep within a block. Append classification + PI only when week diverges from block-scale TID |
| **Durability by Week** | Weekly mean decoupling from steady-state sessions | VI ≤ 1.05, ≥ 90min. Shows aerobic efficiency trajectory across block |
| **Efficiency Factor by Week** | Weekly mean EF from steady-state cycling | VI ≤ 1.05, ≥ 20min. Shows aerobic fitness trajectory across block |
| **HRRc by Week** | Weekly mean HRRc from qualifying sessions | Omit entire section if block has < 3 qualifying sessions total. Weeks with 0 qualifying show "— no data". Shows recovery quality trajectory |
| **Phase Timeline** | `phase_detected` from each weekly_180d row | Shows phase stability across block — did it hold Build the whole time or flip to Overreached? |
| **TID 28d** | Block-scale Seiler classification | 28d window roughly matches block length; confirms or challenges weekly TID |
| **Wellness assessment** | Directional + threshold label | "declining — monitor" / "stable — no concern" / "improving" |
| **Avg Feel** | Activity-level average from `weekly_180d.avg_feel` | 1=Strong to 5=Weak. Omit if 0 sessions across block. Rising feel (higher number) across block = accumulating fatigue |
| **Avg RPE** | Activity-level average from `weekly_180d.avg_rpe` | 1–10 Borg scale. Omit if 0 sessions across block. Rising RPE at constant load = fatigue signal |
| **Phase Progression Check** | Section 11 phase detection criteria | Explicitly states whether block met progression criteria |
| **Section 11 Flags** | All flags triggered during block | With dates and how they were resolved |

## Assessment Labels

### Wellness Direction
| Direction | Threshold | Label |
|-----------|-----------|-------|
| ↑ >5% improvement | HRV up, RHR down | "improving" |
| → <5% change | Stable | "stable — no concern" |
| ↓ 5–10% decline | Mild drift | "declining — monitor" |
| ↓ >10% decline | Significant | "declining — flag" |

### Phase Progression Criteria (Reference)
| Current Phase | Progress When | Stay When | Regress When |
|---------------|---------------|-----------|--------------|
| Base Build | CTL target met, decoupling <5%, compliance >85% | Approaching targets, no flags | HRV declining, compliance <70%, flags triggered |
| Threshold | FTP improved or eFTP trending up, key sessions hit targets | Making progress, manageable fatigue | Stalled power, wellness declining |
| Peak | Race-specific targets met, form (TSB) improving | Still sharpening | Overreached indicators |
| Deload | Hard sessions resume, CTL stabilized, wellness restored | TSS still reduced, wellness not yet recovered | Overreached indicators persist |
| Recovery | RI >0.90, HRV baseline restored, TSB >+10 | Still recovering | N/A — extend until criteria met |
| Overreached | ACWR <1.3, monotony <2.5, wellness improving | ACWR still elevated or monotony still high | N/A — mandatory recovery until resolved |

## Notes

- **Week-by-week CTL** is critical — the trajectory tells a different story than just start/end
- **Polarization by Week** catches grey zone creep that block averages can mask
- **Durability by Week** catches aerobic efficiency regression that single-session decoupling can miss; the block trend is the headline
- **Efficiency Factor by Week** catches aerobic fitness trends that complement durability; rising EF at same intensity = improving fitness
- **HRRc by Week** shows recovery quality trajectory across the block; omit entire section if fewer than 3 qualifying sessions in the block. Individual weeks with 0 qualifying sessions show "— no data". Context-dependent: varies with exercise intensity, type, and recording conditions
- **Sustainability Ceilings** show what the athlete can sustain right now at race-relevant durations. Block-over-block: rising ceilings confirm adaptation; narrowing model divergence confirms model inputs are current; improving coverage means the athlete is producing efforts across more durations. Low coverage (<50%) means the profile is heavily model-dependent — note this. Indoor source on key anchors means outdoor race ceiling is likely 3–5% higher
- **DFA a1 Calibration** is the appropriate cadence for surfacing empirical-vs-dossier threshold deltas — block-scale, not weekly. The section is heavily gated (cycling only, validated=true, confidence ≥ moderate) because non-validated or low-confidence estimates create more noise than signal. When the section appears, treat the deltas as coaching observations: flag the discrepancy, recommend formal retest, do not modify dossier or workouts based on the estimate alone. The protocol explicitly forbids auto-updating zones from DFA — see SECTION_11.md DFA a1 Protocol §Boundaries
- **Phase Timeline** makes phase stability visible across the block — the Phase Progression Check is more meaningful when you can see the phase held steady or oscillated
- **Phase Progression Check** makes the protocol's decision logic transparent to the athlete
- **Next Block Plan** should flow directly from the Phase Progression Check — if criteria aren't met, explain what the next block does differently
- Keep "Interpretation" to coaching interpretation — the data is already presented above
- Block reports are the most detailed report type (~45-60 lines) — this is where the deep analysis lives

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format — the formatted values are pre-calculated from raw seconds and avoid rounding errors.
