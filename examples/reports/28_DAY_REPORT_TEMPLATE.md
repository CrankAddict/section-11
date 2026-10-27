# 28-day Report Template

**Window:** today and the preceding 27 local dates. Use only latest.json.rolling_7d_chunks: four supplied disjoint windows, newest first. Display oldest first (4, 3, 2, 1) in one Week by week block, with four comma-separated values per metric. Chunk 1 equals the 7-day report window. Never compute, shift, reconstruct, backfill or substitute calendar weeks. If these chunks are missing/inconsistent, explain the unavailable breakdown and request a compatible current export.

Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) in SECTION_11.md before writing the report. That section owns the common layout and content rules; this template owns this report's field order, sources and gates.

## Template Structure

```text
**28-day report: [chunk 4 start] to [chunk 1 end]**
Data updated: [local timestamp]

Summary: [one short paragraph, 1-2 sentences]

Phase now: [current detected phase and supplied duration; state material uncertainty]

**Totals**
[Sport]: [time, sessions, TSS; one line per sport]
Total: [time, sessions, TSS]

**Plan**
Rides: [paired of recorded rides] planned [✅ only when all paired]
[Other sport plural]: [paired of recorded sessions] planned [no Walk/Hike marker]
Checked: [followed of assessed sessions] followed [✅ only when all followed]

**Fitness (start of period -> now)**
CTL: [start] -> [now] ([signed delta])
ATL: [start] -> [now] ([signed delta])
TSB: [start] -> [now] ([signed delta])

**Week by week (oldest first, 7-day avg for means, Durability/EF cycling)**
Weeks: [four supplied start dates]
Hours: [four values]
TSS: [four values]
CTL: [four end values]
Hard days: [four counts or unknown]
[Label partial hard-day coverage by chunk]
Durability: [four means]
EF: [four means]
HRRc: [four means, numbers only]
HRV: [four means]
RHR: [four means]
Sleep: [four means]
[Metric N: dated counts only for partial weeks]

**Weekly intensity ([sport], [basis], [complete coverage])**
Z1+Z2: [four percentages]
Z3: [four percentages]
Z4+: [four percentages]
[Partial coverage: identify affected chunk and mapping]

**Wellness (28-day avg, [shared complete coverage])**
HRV: [avg]
RHR: [avg]
Sleep: [avg]
Sleep quality: [avg]
[Metric coverage lines only where partial]
Weight latest: [value, date]
Weight avg: [mean, N weigh-ins]
Weight trend: [supplied kg/week slope]
Feel: [avg, N sessions]
RPE: [avg, N sessions]

**Intensity ([sport], [basis], [complete coverage])**
Z1+Z2: [percentage]
Z3: [percentage]
Z4+: [percentage]
TID 28d: [supplied classification]
PI: [supplied value]
[Partial coverage line only when needed]

**Highlights**
[Every warning/failure marker first, date and short key-session name]

**Key session: [status emoji] [date, short name]**
[One line per deviating session's set: target, count and supplied set avg]
Reason: [one short reason for a miss]
Not ridden: [known omitted reps]
Below target: [observed off-target reps]
[For an ordinary step use Target and same-window Actual]

**Key observations**
Long ride: [date, short name, duration]
[One supported observation if relevant]
Tempo [date]: [whole-ride decoupling]
[Each value on its own line; append its plan changes power mark when present]

**Best efforts ([sport], last 28 days, previous 28 days in brackets)**
5 s: [W, date] ([previous W])
1 min: [W, date] ([previous W])
5 min: [W, date] ([previous W])
20 min: [W, date] ([previous W])
60 min: [W, date] ([previous W])
HR [duration]: [current bpm] ([previous bpm])
Shift: [plain words describing the observed change]

**DFA a1 (28 days)**
DFA a1: [28-day avg]
Drift: [28-day avg, eligible N]
Sessions: [sufficient N and available coverage]
Easy-state guard: [eligible estimate and N, descriptive]
[LT1/LT2 only when an estimate exists]

**Section 11 flags**
⚠️ [Title]
[Fact label]: [one fact per line]
Analysis: [one short supported analysis]

**Fun facts ([sport], descriptive)**
[Groups below, without Peaks, with Most work in a week]

**Interpretation**
Load: [1-2 sentences on the four-week pattern]

Quality: [1-2 sentences on supported execution]

Watch: [1-2 sentences on material concerns]

Next: [1-2 sentences ending at the next decision]
```

## Sources and gates

Repeat Intensity blocks for every selected sport and actual basis/mapping in the shared sport order. Put complete covered/period weeks and covered/sport sessions in the heading; partial coverage gets a labelled line. Keep separate headings for distinct mappings. Weeks mean rolling chunks in current reports and configured weeks in Season/months; a covered week is not necessarily fully measured. Decode the file-level report_intensity_schema; require matching rule_version in each block, otherwise unavailable. Display keys of selected; sports[sport] supplies totals, active-week and zone columns, while zones[mapping] supplies three raw seconds and session/week counts. Show active-week counts and partial coverage without inferring exact covered dates. Resolve explicit rolling refs using the consuming chunk's dates, and monthly blocks by first occurrence in monthly_1y, monthly_2y, monthly_3y. Distinct mappings of the same basis stay separately labelled. Selected sports without zones get a short zones-unavailable line; pace/GAP is deferred. Missing report_intensity blocks mean unavailable; a present empty block is authoritative. Never use legacy primary/all-sport fields as fallback. Use ready-block tid[sport][mapping] percentages; for compact rows divide each bucket's raw seconds by their sum, never average percentages. Keep observed coverage and unknown activity-fetch completeness explicit.

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).
For compliance, read the compact per-step rows with their evaluator, completion and availability; select main work from the authoritative prescription. Unlabelled lower-target rows are not automatic exclusions, and compressed-set totals are never an all-steps aggregate.

- Totals by sport use exact-window recent_activities, distinct IDs, moving_time_s and achieved TSS. Total hours/TSS must reconcile with the four supplied chunks, allowing display rounding. Do not reconstruct chunk metrics from activities or history. Missing metrics remove their own lines, not other supplied observations.
- Pairing comes from plan_pairing for every sport. "Rides: 12 of 12 planned ✅" counts paired activities, not adherence. Walk/Hike count only in Plan participation, never as duration success/failure or in the checked denominator. A known uncompleted planned walk counts as not done only when explicit historical calendar evidence supplies it; the recent activity list alone cannot. Checked against plan includes assessed step statuses and paired no-step activities of other sports with a non-null duration result; only followed steps or within-tolerance no-step durations contribute to its followed numerator. Do not substitute a duration check for a structured plan assessment. Exclude unassessed/unknown results from the checked denominator; never show not-assessed counts. Explain material retained-step coverage without inventing assessments: full detail remains 14 days; older step results are last captured. Pairing identity/duration refresh across 28 days.
- Fitness uses exact dated start-of-period and current CTL/ATL/TSB. Start -> now is allowed here. If the start is missing, show only the dated current value. No seven-day ramp, FTP, eFTP, W/kg, ceilings or separate progression section.
- Week by week retains exactly four positions, oldest first, from each supplied chunk. Do not collapse missing weeks or shift values left: retain a meaningful observed zero and use unavailable in a missing position of a populated series. Omit a metric only when the entire series is missing/zero-only. Each chunk's hours, TSS, ctl_end, hard_days, hard_day_details, capability means/N and wellness are supplied. Zones use chunk.report_intensity for each independently selected sport and actual basis/mapping, with weeks/sessions coverage. The full 28-day block includes all observations for its selected sports, including chunks where they did not qualify. Missing new blocks are unavailable. Hard-day reasons use actual rung/basis. Put supported dates/reasons one per line under a label, rather than joining names with semicolons. No reclassification; unknown plan intensity stays unknown.
- Read each chunk's hard_days_coverage beside its count. Partial coverage shows the missing-day count, for example "Hard days: 2 (1 day without zone data)". Unknown or missing coverage displays unknown, never a bare 0. no_activities means no observed activities, not proven rest. Coverage is day-level power/HR source presence; it does not reclassify hard days or certify every activity's zones.
- Chunk Durability/EF/HRRc share a 7-day avg heading. Read every qualifying N to assess support; print dated per-week N only for partial weeks, never imply that eligible-session N equals all sessions. Complete coverage may be stated once in the heading. Wellness day coverage is metric-specific; one partial metric does not make every metric partial. HRRc only when present, numbers only, no trend words. All producer eligibility gates and per-session decoupling >=90 min/VI <=1.05 and EF cycling >=20 min/power+HR/VI <=1.05 gates remain. A per-session value with `decoupling_detail.comparability: plan_changes_power` stays in the series, marked "plan changes power", without a drift verdict or trend claim from that value; chunk Durability (cycling) retains these gates.
- Wellness uses latest.json.wellness_28d, not seven-day wellness_data or a mean of chunk means. Each metric's own observed-day count is authoritative. Weight uses weight_kg.avg/days/latest/latest_date with display conversion; keep the existing current_status.weight slope gate independently. Feel/RPE use available exact-window recent_activities with N; no missing values become zero.
- Intensity uses derived_metrics.report_intensity_28d.selected, tid and sports coverage columns, with sport/basis/mapping and coverage labels. Keep its four-chunk scope distinct from each chunk's own selection. See [Report intensity source](../../SECTION_11.md#report-intensity-source). Phase is current derived_metrics.phase_detection only, still based on configured calendar weeks.
- Highlights and key-session detail follow the shared layout and 7-day source rules: every supported warning/failure appears, only key sessions are named, and detailed sets appear only for deviations. Use exact identified target/actual windows, with set averages separate from atomic on-target counts and not-ridden reps separate from observed misses. Long-ride observations and a tempo whole-ride decoupling series remain clearly distinct from main-set measures. No invented target power from session average/NP.
- Best efforts repeats for each current 28-day selected sport using capability.curve_deltas_by_sport.sports[sport].power/hr and its declared windows. Show power only with observed power evidence and HR where available. Take dates only from each anchor's current_source; absent dates are omitted. Missing previous values remove only the bracket; partial maxima are observed lower bounds. Shift requires status=available and matched windows with at least three valid anchors on both sides; use words, no percentages or rotation scores. Missing new evidence is unavailable, never a legacy curve or fun-fact fallback.
- Flags follow the 7-day per-flag layout and Z3 intent/basis rules. No high-drift count flag.
- Fun facts sources: latest.json.fun_facts.rolling_28d for cycling and sport_fun_facts.rolling_28d.sports for the other four fact sports, gated by derived_metrics.report_intensity_28d.selected. Require compatible identity/selection markers and matching start/end as defined in [Descriptive Period Facts](../../SECTION_11.md#descriptive-period-facts). Most work in a week is the supplied rolling chunk and its dates, never a calendar week. Peaks are omitted here.

## DFA a1 eligibility

Use derived_metrics.capability.dfa_a1_profile_28d, alongside (not in place of) the existing latest-seven-sufficient profile. The 28-day field uses available retained compact summaries with the same eligibility and no backfill. State material incomplete coverage; do not imply 28 full days of recording. Require the cycling block and validated=true.

Show 28-day avg and sufficient n_sessions when supplied, regardless of whether a marker estimate exists. Drift uses drift_delta_mean and drift_sessions only; null is not zero, and numerical eligibility alone does not prove physiological drift or steady workload. Show an easy_guard_estimate whenever present, independent of the coarse confidence field. The easy-state guard at α1 1.0 is descriptive compliance context, NEVER threshold calibration. Include HR and only populated environment values with their own N.

Omit no-estimate LT1/LT2 lines. Existing estimate gates remain authoritative: crossing_sessions means dwell-qualified, eligible_sessions also passed stationarity/quality gates, and estimates require eligible depth. An emitted LT1/LT2 estimate can be shown descriptively; LT1 has no configured comparator. Any separately requested LT2 comparison still requires its estimate, matching depth >=4 (including lt2_estimate.n_sessions_indoor for indoor watts) and configured comparator. No automatic threshold update or progression decision follows. Diagnostic eligibility blockers may be explained when material; they never become pseudo-estimates.

## Source and display safeguards

Read current source JSON in this response and the current official dossier for stable context; never reuse prior report values. Use local dates, a bold dated header and local Data updated. Keep a separate History updated timestamp when relevant. Follow the shared layout for facts, paragraphs, headings and lists. Previous values go in brackets. Every mean says avg and its window, in its heading when shared; retain observation counts under the report-specific coverage rules. Only the 28-day Fitness section uses start -> now lines. Omit missing or zero-only lines and empty sections, preserving a meaningful zero inside an otherwise populated comparison. Explain missing indispensable source blocks once; never invent observations or print placeholders.

Use supplied display values and formatted durations. Seconds-only durations may round to whole minutes (30 seconds up); decimal hours may remain decimal h. Eligibility always uses exact values. Readiness, formal compliance and progression gates in SECTION_11 are unchanged. A report marker is not formal adherence evidence.

### Fun facts contract

Place **Fun facts ([sport], descriptive)** blocks immediately before **Interpretation**, in cycling, running, swimming, Nordic skiing, rowing order. Show only those sports selected by this report's own period selection. Read supplied period facts, never reconstruct from weekly compact caches. Missing or incompatible selection/facts are unavailable; an empty selection is authoritative. Observations are not tests, FTP/zone evidence or readiness evidence. Retain partial/stale coverage, date, activity name (ID if absent) and separate history freshness.

For cycling, use these blank-line groups, omitting unavailable components:
1. Max power (1 s), with date/name; Max HR, with date/name.
2. Longest ride, with date/name/duration and available distance; Distance ridden for each nonzero environment; Climbed for each nonzero environment.
3. Peaks: one line each for 5 s, 1 min, 5 min, 20 min and 60 min, with date/name. Include only in 7-day and Season fun facts; the 28-day report has its separate Best efforts section.
4. Time in the saddle.
5. Work and Carbs used, each with its equivalent in parentheses; break before the equivalent if needed. Most work in a day uses date, kJ and same-day carbs on separately labelled lines. Add Most work in a week only in 28-day and Season, retaining the supplied dates.

For running, swimming, Nordic skiing and rowing, use three blank-line groups: Max HR with date/name; longest run/swim/Nordic session/row with date/name/duration and available distance, then distance and supported outdoor climbing; Running time / Swimming moving time / Nordic skiing time / Rowing time. Longest sessions belong here only in 7-day/28-day reports; Season keeps them in Volume. No power, work, carbs or equivalents belong to these four sports.

Use Distance ridden / Distance run / Distance swum / Distance skied / Distance rowed, and Climbed. Typical lines fit 40 characters: `Distance ridden: 80 km (outdoor)`, `Distance run: 18 km (outdoor)`, `Distance swum: 2 km (pool/other)`, `Distance skied: 18 km (indoor)`, `Distance rowed: 24 km (indoor)`, `Climbed: 600 m (outdoor)`. Use only supplied settings: indoor, outdoor, open water, pool/other, snow, roller, unknown. Generic Swim is pool/other, never a verified pool; OpenWaterSwim is open water unless supplied as unknown. Settings come solely from the emitted fact environment. Never infer environment from names or pool-length fields. Keep indoor, snow, roller and outdoor distance separate. Label a longest session's distance with its setting too. Any indoor distance, speed or climbing outside the split must also carry (indoor). Unknown is never outdoor. Use metres with explicit m if display conversion is unavailable; omit zero-only climbing.

Put complete metric coverage in its heading when shared. Show observed partial values with a separately labelled metric coverage line, for example `HR coverage: 2 of 3 sessions` or `Indoor distance: 2 of 3 sessions`. Keep date/name and setting attached to the correct fact; a deliberate fact break is allowed, but never a continuation of a Highlights or session line. Duration/longest and HR counts use coverage against activity_count; distance/ascent counts use their own setting's activity_count. Zero coverage omits the metric; missing is never zero. Duplicate-conflicting metrics remain unavailable. Cycling retains its existing counts and partial/stale power coverage.

A clear current official dossier statement of positive grams carbohydrate per bottle is sufficient, whether in prose or the Tested training fuel table. For example, "My training bottle contains 90 g carbohydrate" establishes grams per bottle without needing a table. Never infer grams from bottle volume, a product name or a serving without a per-bottle statement. Ambiguous/conflicting statements do not establish a bottle.

Use the athlete's stated bottle; otherwise use the USDA medium-banana fallback: about 27 g carbohydrate and about 105 kcal per medium banana. Carbs equivalent = carbs_used / 27 or carbs_used / grams per bottle. Work equivalent = work_kj / 105 or work_kj / (4 * grams per bottle). Mechanical work of 1 kJ is approximately 1 kcal expended. This equivalence method note belongs only in the template, not in the report. Round counts to one decimal and say about: `Work: 3600 kJ (energy of about 10.0 of your 90 g bottles)`, `Carbs used: 900 g (about 10.0 of your 90 g bottles)`; fallback uses medium bananas. These are fun comparisons, not fueling advice or estimates of carbs eaten.
