# Post-Workout Report Template

> This template defines the standard output format for post-workout reports.
>
> Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) before writing the report.
> Fields in `[brackets]` are placeholders. Omit fields that don't apply to the activity type.  
> **Data Freshness:** Take every number from a current read of the source that owns it: training metrics and planned sessions from the source JSON file, stable athlete facts (such as a tested bottle quantity) from the current official dossier, athlete-reported values from the athlete's explicit current statement, and external conditions such as weather from their current source (see SECTION_11.md §Output Format Guidelines). Never take a number from memory or an earlier chat. Do not carry forward values from earlier reports or earlier in the conversation. Re-read before quoting.  
> **Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON; they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. See SECTION_11.md §Display Unit Semantics.

---

```
**Post-workout: [Weekday D Month]**
Data updated: [local date time; zone only when different from athlete timezone or UTC fallback]

Summary: [One naturally wrapping line about completed sessions and the key observation.]

**[Sport: WorkoutName; omit sport prefix when already in the name]**
[Outdoor ride / Indoor ride; rides only]
Start: [HH:MM]
Moving time: [XhYm]
Total time: [XhYm; elapsed, omit when equal to moving after minute rounding]
Planned: [XhYm; exact paired duration only; omit for Walk/Hike]

Distance: [display.distance.value] [display.distance.unit]
Ascent: [display.elevation.value] [display.elevation.unit]
Avg speed: [x.x] [display.avg_speed.unit; rides and outdoor NordicSki only]
Pace: [display.pace.value] [display.pace.unit] ([display.avg_speed.value] [display.avg_speed.unit]; runs only; walks/hikes omit parenthesis)
Terrain: [course_character] ([display.elevation_per_distance.value] [unit])
Temperature: [display.avg_temp.value] [unit] avg (min [display.min_temp.value], max [display.max_temp.value])
Wind: [descriptor] ([speed and unit], gusts up to [gust and unit])

Climbs
[display.position.value and unit]: [display.distance.value and unit] at [avg_gradient_pct]% (max [max_gradient_pct]%)
[One line per supplied climb, outdoor only; no climb time or power]

Power: [avg_power] W avg ([avg_power_wkg] W/kg)
NP: [normalized_power] W
Max power: [power_curve["1"]] W
Peaks
5 s: [power_curve["5"]] W
1 min: [power_curve["60"]] W
5 min: [power_curve["300"]] W
20 min: [power_curve["1200"]] W
60 min: [power_curve["3600"]] W
Executed structure: [method/status; supported step/set measurements with actual means and agreement, or descriptive thirds/WORK efforts; say unavailable when absent; omit for Walk/Hike]
Compliance: [only with an exact paired plan containing power-targeted main work: main work completed / incomplete / completion not evaluable; when formal adherence is evaluable, N/M atomic steps or work bouts on target, with percentage only when comparable; for sets give per-set bout counts, e.g. "set 2 12/13 on target (bout 1 −5.1 W, below band)"; ≤20 s sprints use best W seconds (W = max(3, ceil(0.30 × prescribed seconds))) at target or above, or at the range's lower bound, with signed standard-window mean and best-W-second watts for information and no upper ceiling; longer efforts identify every off-target or above-target item by step or set/bout with signed watts and band side; otherwise give the short reason adherence is not evaluable; omit otherwise]
Sets
Set [N] ([target] W): [on target/count], [avg] W avg
Reason: [short supported miss reason]
Not ridden: [known set/bout IDs, separate from below-target reps]
Non-main steps: [supported confirmation; otherwise unavailable]
[Only expand applicable deviating sets; use qualified atomic counts, never set means]

IF: [X.XX] [omit line if null]
Power Z1+Z2/Z3/Z4+: [X]/[X]/[X]%
Session profile: [Classification]
Variability Index: [X.XX] ([assessment])

HR: [XXX] avg, [XXX] max
HR Z1+Z2/Z3/Z4+: [X]/[X]/[X]%
Cadence: [XX] avg
Decoupling: [X.XX]%
Early → late: [decoupling_detail.early.avg_power_w] → [late.avg_power_w] W, HR [early.avg_hr_bpm] → [late.avg_hr_bpm][; comparability flag when present]
EF: [X.XX; omit unless 0 < VI ≤ 1.05]
HRRc: [XX] bpm [omit line if null]
DFA a1: [X.XX] avg, [X]% easy/[X]% endurance/[X]% tempo/[X]% supra ([status-aware drift summary]) [omit line entirely if no dfa block on this activity; one-line quality notice with no readings if sufficient=false]

Work: [work_kj] kJ
Calories: [XXXX] kcal
Carbs used: [XXX] g
TSS: [XXX] (planned [XXX])
Feel: [X/5] ([label])
RPE: [X/10]
Effort response: [positive/neutral/negative] [omit line if null]
Note: [description or chat_notes text]

[Repeat block for every completed activity whose date falls on the report day (athlete local time). One block per activity ID; never merge. Include walks, ski-erg, short rides, aborted rides, commutes. Never drop secondary sessions. Within a block, omit only fields the activity type does not have (e.g., no power for a walk).]

**Last 7 days**
Phase: [phase_detection.phase] Wk[phase_detection.phase_duration_weeks]

**Intensity ([sport], [basis/mapping], [complete coverage])**
Z1+Z2: [XX]%
Z3: [X]%
Z4+: [X]%
TID 7d: [Classification]
PI: [X.XX]
[Repeat selected-sport blocks; partial coverage on its own line]

**Capability (7d / 28d)**
Durability (cycling): [X.XX]% 7d mean([X]) / [X.XX]% 28d mean([X]) ([trend])
EF: [X.XX] 7d mean([X]) / [X.XX] 28d mean([X]) ([trend])
HRRc: [XX] bpm 7d mean([X]) / [XX] bpm 28d mean([X]) ([trend]) [4 cases: (a) 28d ≥ 3 and 7d ≥ 1: full line as shown; (b) 28d ≥ 3 and 7d = 0: "[XX] bpm 28d mean([X]); 7d: no data"; (c) 28d < 3 and 7d ≥ 1: "[XX] bpm 7d mean([X]); 28d: insufficient data"; (d) 28d < 3 and 7d = 0: omit entirely]
TID 28d ([sport], [basis], [coverage]): [Classification] (PI: [X.XX]); drift: [consistent/shifting/acute_depolarization]

**Load (last 7 days)**
CTL: [XX.XX]
ATL: [XX.XX]
TSB: [X.XX]
Ramp rate: [X.XX]
ACWR: [X.XX] ([assessment]); live, includes today's completed load; retrospective context only
Recovery Index: [X.XX]

Hours: [XhYm]
TSS: [XXX]

**Interpretation**
Quality: [1-2 naturally wrapping sentences on supported execution.]

Load: [1-2 sentences on load and recovery.]

Watch: [Supported uncertainty or flagged context, if relevant.]

Next: [Forward look and the next decision.]

**Tomorrow**
[Sport]: [WorkoutType] [Duration][, main set condensed, e.g., "3×12m @260W"][, HH:MM]
[Use workout_summary as source. Condense to main set using SECTION_11's Main work rule: identify roles from prescription structure, durations and targets, using its name or description as context only; workout step text is optional. Omit a warm-up, cool-down or recovery step only when that role is clear from this evidence. A lower target alone is insufficient, and sustained endurance work or an active connector must not disappear from the main set. If the distinction is ambiguous, retain the relevant steps and state the uncertainty. Square-bracketed text in workout_summary (`[step not summarized]`, `[repeat not summarized]`, `[target not shown]`) marks a step, repeat or target the summary could not render. A summary without a marker lists every step with its duration and its power target (or HR target when no power target is set); it does not carry secondary targets such as cadence or an HR target set alongside power, and where it compresses repeated steps it shows them at the first step's value when each is within 2 W and 2 s of that first step. If workout_summary is null or carries a marker, take the plan from whichever of `description` (entries up to 7 days ahead) or `description_preview` (later entries; its first 3 lines only, so say the plan may continue) the entry carries; if that field is absent or empty, report a marked summary as given and say it is incomplete, or for a null summary give the workout name and duration and say the structure is not in the data. Never invent targets or step roles.]
[List ALL planned sessions, one per line in start-time order; omit time only when absent. Never drop secondary sessions. Omit the whole Tomorrow section only if no planned sessions exist tomorrow.]
```

---

Whole-session average/NP cannot establish main-set power. Apply the structure rule in comparisons, interpretation and tomorrow's prescription as well as in the session block. Thirds, small mean deviations and a low VI do not by themselves prove steady work for DFA or decoupling interpretation.

Use one labelled fact per line and blank lines between time, distance/context, climbs, power, HR and energy groups. Omit empty groups. No middle-dot separators or hyphen continuation lines. Last 7 days retains Phase, selected-sport Intensity, capability, load/recovery and Hours/TSS with labelled groups. Keep CTL, ATL, TSB, Ramp rate, Hours and TSS. Keep Summary on one source line and use labelled 1-2 sentence Interpretation paragraphs ending with Next. Supported terrain/heat/wind causal clauses belong in Interpretation, using the existing evidence gates.

## Rounding Convention

Write watts with a space before the unit (`300 W`). Set and step averages use whole watts; a deficit may keep one decimal (`−4.2 W`). Compliance percentages round to the nearest whole number. Producer-supplied workout summaries such as `3×10m @245W` keep their own text.

Round zone percentages to the nearest **whole number** (1%). The JSON data source carries precise values for detailed analysis. Use raw zone seconds to form the three bands before rounding; a few seconds reports as `0%`, not `0.1%`. A missing band distribution is unavailable, not zero.

Round report durations to the nearest whole minute (30 seconds rounds up), retaining hours and minutes. Use `display.moving_time` and `display.elapsed_time`; `elapsed_formatted` has the same minute rounding. Use the exact paired `interval_data.plan_match.plan.duration_s` when present, otherwise the verified paired plan's exact `duration_formatted`; round at presentation, never decimal hours or a duration parsed from a name. A missing start is omitted; otherwise show HH:MM without seconds. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).

## Field Notes

Repeat Intensity blocks in shared selected-sport order for each actual basis/mapping. Put complete covered/period weeks and covered/sport sessions in headings, partial coverage on its own line. Weeks mean rolling chunks in current reports and configured weeks in Season/months; a covered week is not necessarily fully measured. Decode the file-level report_intensity_schema; require matching rule_version in each block, otherwise unavailable. Display keys of selected; sports[sport] supplies totals, active-week and zone columns, while zones[mapping] supplies three raw seconds and session/week counts. Show active-week counts and partial coverage without inferring exact covered dates. Resolve explicit rolling refs using the consuming chunk's dates, and monthly blocks by first occurrence in monthly_1y, monthly_2y, monthly_3y. Distinct mappings of the same basis stay separately labelled. Selected sports without zones get a short zones-unavailable line; pace/GAP is deferred. Missing report_intensity blocks mean unavailable; a present empty block is authoritative. Never use legacy primary/all-sport fields as fallback. Use ready-block tid[sport][mapping] percentages; for compact rows divide each bucket's raw seconds by their sum, never average percentages. Keep observed coverage and unknown activity-fetch completeness explicit.

| Field | When to include | Notes |
|-------|----------------|-------|
| Header / Data updated | Every report | Bold Post-workout date in athlete local time; convert last_updated to athlete timezone. Append a zone only if it differs or is a UTC fallback. This post-workout header rule does not change the pre-workout template |
| Activity heading / type | Every activity ID on the local report day | Bold name, with short sport label only if the name lacks it (Ride: Aalborg Road Cycling; SkiErg 10m). Add Outdoor ride or Indoor ride for cycling. Preserve secondary, short, aborted and commute activities |
| Start / Moving time / Total time / Planned | Start and moving when available; total only if rounded elapsed differs; planned only for an exact paired plan with duration, never Walk/Hike | HH:MM; minute-rounded durations on separate lines. Total time is elapsed, never an inferred pause amount |
| Distance | Cycling, running, walking/hiking and outdoor NordicSki when applicable | Use display.distance; omit for SkiErg and strength; do not infer distance from speed |
| Avg speed / Pace | Rides and outdoor NordicSki use Avg speed; runs including VirtualRun use Pace plus speed; walks/hikes use Pace alone | Quote display.avg_speed and display.pace, including /mi and mph for imperial. No speed/pace for SkiErg/VirtualSki, rowing ergs or strength. Omit unavailable values; never calculate pace in the report |
| Terrain | Outdoor and usable terrain_summary | Quote course_character and display.elevation_per_distance; omit unavailable parts or the line if none. Never infer flatness from no_elevation |
| Temperature | Outdoor when available; indoor only for temp_source=device | Quote display.avg_temp with same-source min/max, with one decimal and long ranges split into labelled lines. Weather takes precedence over device; omit each missing endpoint without borrowing the other source. If the average is absent, omit the line. Temperature values already use account units |
| Wind | Outdoor with usable weather_summary | Use avg_wind_speed, avg_wind_gust and units.wind. Apply the protocol's calm/breezy/windy/very windy bands in the correct units. Omit unavailable parts independently; no invented calm or gusts. Causal explanation moves to Interpretation |
| Climbs | Outdoor with nonempty terrain_summary.climbs | One line per supplied climb: display.position, display.distance, avg_gradient_pct and max_gradient_pct. Omit missing parts, never add time or power |
| Ascent | Walks, runs and rides, indoors and outdoors, when recorded elevation is present | Quote display.elevation.value and unit. Retain zero; omit when unavailable. Source-dependent and descriptive only: never compare barometric, GPS and virtual ascent, or replace recorded total with detector ascent |
| Executed structure | Completed activities except Walk/Hike | Read latest.json interval_data.plan_match method/status/issues. When has_structure is true, load intervals.json's session_structure for window bounds, HR, cadence, kJ, coverage and zero-power share; qualify any stale/cache or partial-data issue. For paired_plan_windows, quote actual mean power and measured duration beside target; follow SECTION_11's recording-time alignment and set contract. Render a repeat descriptor as reps × bout duration, with measured work-bout mean and time; never describe it as continuous work. A step with insufficient coverage has no metric numbers; retain usable neighbouring steps. Clipping is disclosed separately from original workout duration. Match is power agreement, not completion. For fixed_elapsed_thirds, label thirds and upstream WORK efforts descriptive; never call them prescribed steps. no_plan means no paired event; no_steps means an exactly paired plan with an explicit empty steps list, retaining supplied plan name/duration without a step comparison. Missing intent remains unknown. When detail has expired, use the last captured summary under its method version and say detail is unavailable; older no_plan summaries may include empty paired plans. Broad followed status is not formal adherence; roles require authoritative context See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use). |
| Compliance | Exact paired plan with power-targeted main work | Read interval_data.compliance.steps using the canonical positional schema: every power step/set is present, with evaluator, completion and power/time availability. Select main work from the authoritative prescription, never automatically exclude lower targets; do not sum the rows into a new session count. Apply SECTION_11's roles, mapping and completion rules first; completion always uses standard windows. With structure-version-6, evidence-marker-4 detail, ≤20 s sprints pass the power test when best rolling W-second mean within the standard window reaches sprint_target_w, the scalar target or range lower bound. Require W consecutive observed seconds and display the recorded sprint_window_s; no lower tolerance or upper ceiling. Report signed standard-window mean and best-W-second differences for information, never call high sprint power non-compliant. Above 20 s use the asymmetric average band: exclude the first two aligned seconds and the final aligned second through 60 s, otherwise only the first, regardless of grouping/recovery/count. Use the protocol's adherence end before clipping; standard completion and sprint windows stay unchanged. Show per-set bout counts where applicable and identify off-target/above-target items; use band-side wording only for the average rule. Consecutive items may be grouped only when every affected item and signed value remain explicit. Set means are observations, never bout counts. Sprints, including range targets, count atomically in the ≥95% gate. Aggregate only comparable main work after full completion and all essential evaluators; mixed-duration pyramids require an explicit combination evaluator. Otherwise report known differences descriptively without a percentage. Expired detail, legacy rows, unsupported nesting or missing inputs leave affected adherence not evaluable, not failed. A followed status alone is never compliance. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use); compact scoped counts require context review, and detected intervals never judge. |
| Power / Power zones | Activities with power data | Power is whole-session average and NP; omit each missing component. Add avg_power_wkg in parentheses only when present, using activity power_weight_kg guarded to 30–200 kg. Power zones use three bands on one line: Z1+Z2 / Z3 / Z4+. Sum the corresponding raw zone seconds, then round each band's percentage; retain zero bands and do not sum already-rounded individual percentages. These remain per-activity observations for every sport; zone_reference records the aggregation's selected basis and activity FTP/environment, never current athlete FTP. See [Report intensity source](../../SECTION_11.md#report-intensity-source) |
| Max power / Peaks | Exact points present in the activity power_curve | Max power is key "1"; Peaks uses "5", "60", "300", "1200", "3600" in that order. Use a Peaks label and one present duration per line; omit missing durations and omit Peaks if none. Never use icu_pm_p_max or interpolate. These describe this activity only, never tests, bests or capability, and never derive FTP, zones or readiness from them |
| HR / HR zones | Available HR data | Average and maximum separated by a comma; omit missing values. Use the same three-band line and sum-before-rounding rule as power, with the supplied activity HR zones; missing distribution stays unavailable, never all zero |
| IF | Activities with `intensity_factor` present | Intensity Factor (session-level, NP ÷ FTP). Rendered to 2 decimals (divide the stored percentage by 100). Omit line when null. Source for Effort Response band lookup |
| Session profile | Qualified structured work-step actuals or executed zone data | Classify executed intensity (Recovery, Endurance, Tempo, Sweetspot, Threshold, VO2max, Anaerobic, Neuromuscular, Mixed). For structured sessions use qualified work-step mean power relative to the FTP applicable to that activity/environment, with authoritative work roles, supported mapping and adequate coverage. Consistent work steps at 88–94% FTP inclusive are Sweetspot even with whole-session VI >1.05 or diluted IF; different work intensities are Mixed or the supported executed class. Targets, names, whole-session IF and NP cannot substitute for work actuals. Missing roles/actuals/FTP means work-step classification unavailable; use executed zones descriptively without assuming Sweetspot. For unstructured sessions Sweetspot still requires IF 0.88–0.94 and 0 < VI ≤1.05; with VI >1.05 classify by dominant executed power zone instead. No change to formal adherence or progression |
| Cadence | Cycling, running | Omit for SkiErg, strength |
| Decoupling | Activities with power + HR | Key aerobic efficiency marker. Display the value whenever present; interpret or label it only when the session passes the per-session gate: ≥ 90 min (5400 s) with `variability_index` ≤ 1.05 and > 0, checked against `duration_formatted`, not rounded hours (SECTION_11.md §Evidence handling). A short or surgy session still carries a decoupling number; it is not evidence. Per-session scale (<5% good) per Friel/Coggan. Aggregate durability uses tighter scale (<3% good) |
| Early → late | decoupling_detail present; directly under Decoupling | Round supplied half power/HR to whole W/bpm. Add “rising power” or “falling power” for those measured trends; plan_changes_power takes precedence as “plan changes power; no drift verdict”, even if the duration/VI gate passes. For steady_power no extra flag is needed. State incomplete bucket coverage or unavailable plan context when material. These are upstream lag-aligned bucket estimates using average power, not NP; do not shift HR again. Window start/mid/end, warm-up/cool-down, work and coverage are available for explanation, but never replace the whole-ride moving-time gate. Plan comparison uses supplied step-work time, not reconstructed clock bounds. No model-based expected drift or correction. Falling power with rising HR is adverse coupling, never explained away by power. Omit this line when detail is unavailable; never fill it from whole-session means or infer steady power from its absence |
| EF | Activities with power + HR | Aerobic efficiency (NP ÷ HR). Omit the session EF line when VI is missing, nonpositive or above 1.05; display a present value only when 0 < VI ≤ 1.05, and interpret it only when the session passes the per-session gate: ≥ 20 min (1200 s) with `variability_index` ≤ 1.05 and > 0, checked against `duration_formatted`, not rounded hours (SECTION_11.md §Evidence handling). Track trend over like-for-like eligible sessions. Absolute value is individual-dependent |
| HRRc | Activities where HR exceeded threshold for >1min | Heart rate recovery (largest 60s HR drop in bpm). Higher = faster parasympathetic recovery. Absent on easy rides, rides stopped before cooldown, or no HR data. Omit line when null |
| Variability Index | Cycling with power | 1.00–1.05 = steady, >1.05 = variable. Assessment labels apply to steady-state only; omit label for interval sessions where high VI is expected |
| DFA a1 | Activities with a `dfa` block in `intervals.json` | **Source:** session-level `dfa.avg` and each `tiz_*` band's `pct`, or their compact-summary equivalents. These describe retained samples; use `quality.coverage_by_third` to explain missing-data limits. Per-interval `avg_dfa_a1` was removed in v11.52; stale values must not be used or averaged. **Branching:** (a) `dfa` block absent → omit the line entirely, do not announce absence; (b) `dfa` present with `quality.sufficient: false` → one-line notice reporting the available quality counts and percentage and each failed gate per **DFA a1 Protocol §Quality Gates**; if the supplied quality data cannot resolve the reason, say so; no DFA reading; (c) `sufficient: true` → full line, using the drift rules below. **Validated sports only:** the protocol's interpretive rules apply to cycling. For other sports, surface values descriptively without threshold conclusions |
| Carbs used | Sessions with power data | Omit if unavailable |
| Work / Calories / TSS | When present | Work comes from existing work_kj; Calories retain kcal. TSS includes planned value only when paired and present. No Carbs eaten line |
| Feel | Omit line if null | 1=Strong, 2=Good, 3=Normal, 4=Poor, 5=Weak. Set in Intervals.icu or pushed from device (e.g. Garmin post-ride prompt). Can appear on any activity type |
| RPE | Omit line if null | Rate of Perceived Exertion, 1–10 scale. Set in Intervals.icu or pushed from device. Can appear on any activity type |
| Effort response | Omit line if null | Session IF vs reported RPE against the RPE Expectation Bands (SECTION_11.md §Testing Protocol). `positive` = RPE below band (fitness/freshness tell), `neutral` = within band, `negative` = above band (fatigue/under-recovery tell). Null when IF absent, RPE absent or ≤ 0, or IF < 0.65 (out of band coverage: recovery rides and aborted sessions). Interpretive overlay: does NOT alter Feel/RPE Override rules (v11.14) and does NOT alter the readiness decision. A single `positive`/`negative` is an observation to surface; a repeated pattern across sessions deserves Interpretation-section commentary |
| Note | Omit line if neither present and no `chat_notes_status` marker | Athlete's own text or coach messages attached to the activity. If both `description` and `chat_notes` exist, combine. Omit line entirely when neither is present. If the activity carries `chat_notes_status: "unavailable"`, the chat notes fetch failed: do not report the activity as having no note. Either omit the line silently or, where the note would have mattered to the interpretation, state that chat notes could not be retrieved |
| Heat context | When `avg_temp` indicates Tier 1+ heat stress (delta above 14d thermal baseline, or absolute fallback) | Contextualize decoupling, power, and RPE against temperature in the Interpretation section. Do not flag heat-elevated decoupling as durability decline. See **Environmental Conditions Protocol** in SECTION_11.md |
| Durability (cycling, weekly) | Aggregate decoupling 7d/28d | Steady-state sessions only (VI ≤ 1.05, ≥ 90min). Trend direction matters more than absolute value |
| EF (weekly) | Aggregate EF 7d/28d | Steady-state cycling only (VI ≤ 1.05, ≥ 20min). Trend direction matters more than absolute value |
| TID 28d (weekly) | Selected sports' observed 28d classification | Use derived_metrics.report_intensity_28d and capability.report_intensity_comparison, matched by sport/basis/mapping with coverage read from both ready blocks. Include only supported observed-session drift; partial or unavailable evidence supplies no drift |
| Polarization (weekly) | Selected sport/basis Seiler groups | Use derived_metrics.report_intensity_7d.selected and tid[sport][mapping] percentages as Z1+Z2 / Z3 / Z4+, with sport, actual basis/mapping and weeks/sessions coverage. See [Report intensity source](../../SECTION_11.md#report-intensity-source) |
| Last 7 days | Always | Rolling last 7 days including today, not calendar week. Retain CTL, ATL, TSB, Ramp rate, Hours, TSS and existing conditional context under labelled groups |
| Interpretation | Every report | Bold heading; labelled 1-2 sentence Quality, Load, Watch and Next paragraphs as applicable, preserving compliance, metric-validity, load and recovery rules, with supported terrain/heat/wind causal clauses here |
| Tomorrow | Any planned session tomorrow | Bold heading then one session per line in start-time order, with sport, type, duration, condensed supported main set and time when supplied. Keep every session and the summary/description fallback rules above |

### DFA drift wording

Read `drift_quality.status` and ordered `reasons`, not the boolean alone. For a sufficient session:

- `unavailable`: `(drift unavailable: [reasons])`; no numeric drift or zero substitute. Other sufficient-session readings may remain.
- `descriptive_only`: `(drift [+/−X.XX], descriptive_only: [reasons])`. Name all emitted reasons in order; always explain `short_session` as fewer than 90 recorded minutes. Retain the number without a physiological flag, even if it is below -0.2. Do not label a false boolean "structural".
- `eligible`: `(drift [+/−X.XX], eligible)`. This reports numerical eligibility, not a physiological conclusion. A flag additionally requires delta < -0.2 and steady easy/endurance cycling confirmed from session structure, with fueling/hydration, heat and fatigue cross-checks per **DFA a1 Protocol §Session Interpretation Rules**. Low supra time alone is insufficient; selective loss can still bias the result.
- Missing, contradictory or unsupported metadata: report that drift eligibility cannot be established; do not infer it from a legacy boolean. Request a current producer export where needed.

The 90-minute rule uses 5400 original DFA slots with verified 1 Hz timing, not rounded activity hours or retained samples. Whole-session insufficiency always takes precedence over these drift-specific branches and retains the v11.72 refusal wording.

## Assessment Labels

| Metric | Good | Watch | Flag |
|--------|------|-------|------|
| Decoupling (per-session, gated sessions only) | < 5% | 5–10% | > 10% |
| Variability Index | ≤ 1.05 | 1.05–1.10 | > 1.10 |
| ACWR (live retrospective) | 0.8–<1.3 | 1.3–<1.5 | ≥1.5 |
| Grey Zone (Z3) | < 5% (base) | 5–10% | > 10% (base phase) |
| Durability (cycling, 7d mean) | < 3% (good) | 3–5% (moderate) | > 5% (declining) |
| EF trend | improving/stable | — | declining |
| DFA a1 (cycling, sufficient) | Internal response matches prescription (very-easy/recovery → predominantly `tiz_easy`; endurance/Z2 → a `tiz_easy`/`tiz_endurance` mix, `tiz_endurance` = working toward LT1; SS/tempo → `tiz_tempo`) | Mild mismatch; note in Interpretation | Significant mismatch OR eligible drift below -0.2 on confirmed steady easy/endurance cycling, with the context checks above |
| TID drift | consistent | shifting | acute_depolarization |

ACWR <0.8 is reduced-load context, not a Watch/Flag classification.

## Formatting Rule

- **Durations and sleep:** Use the producer's rounded display durations for completed activities. Elsewhere round exact `_formatted` durations to whole minutes for this report. Never convert decimal `_hours` fields. Preserve the exact duration_formatted for eligibility gates; display rounding cannot make a short session eligible.
