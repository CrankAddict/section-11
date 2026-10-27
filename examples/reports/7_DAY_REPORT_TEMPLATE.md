# 7-day Report Template

**Window:** today and the preceding 6 local dates. Previous 7 days is the immediately preceding disjoint window. Use rolling_7d_chunks[0] and [1], never calendar-week rows. The configured week start still controls history, Season, phase detection and planned-week features.

Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) in SECTION_11.md before writing the report. That section owns the common layout and content rules; this template owns this report's field order, sources and gates.

## Template Structure

```text
**7-day report: [start] to [today]**
Data updated: [local timestamp]

Summary: [one short paragraph, 1-2 sentences]

Phase now: [current detected phase and supplied duration; state material uncertainty]
Sessions: [count]
[Sport]: [duration, sessions, TSS; one line per sport]
Hours: [current] (prev [previous])
TSS: [current] (prev [previous])
Plan: [nonzero readable counts; break between categories if needed]

**Highlights**
[Marker first when assessed] [date, short name, supported result]

**Key session: [status emoji] [date, name]**
Window: [identified step/set and bounds]
Set 1 ([target]): [on-target count, set avg]
Set 2 ([target]): [on-target count, set avg]
Reason: [one short supported miss reason]
Not ridden: [known omitted reps]
Below target: [observed off-target reps]
[For an ordinary step use Target and Actual for the same window]

**Intensity ([sport], [basis], [complete coverage])**
Z1+Z2: [percentage] (prev [percentage])
Z3: [percentage] (prev [percentage])
Z4+: [percentage] (prev [percentage])
TID 7d: [supplied classification]
PI: [supplied value]
[Partial coverage line only when needed]

**TID 28d ([sport], [basis], [complete coverage])**
TID: [supplied classification]
[Independent selection and partial coverage]

**Capability (cycling, 7-day avg, 28-day avg)**
Durability: [7-day value and N] ([28-day value and N])
EF: [7-day value and N] ([28-day value and N])
HRRc: [7-day value and N] ([28-day value and N; numbers only])

**Fitness**
CTL: [current] (prev [previous])
ATL: [current]
TSB: [current]
Ramp rate: [supplied 7-day value]
ACWR: [supplied ratio and label]
Recovery Index: [value]
Monotony ([supplied main sports]): [supplied combined value, only when above 2.3]
Strain (all sports): [only with monotony flag]
Hard days: [count with missing-zone-day coverage, or unknown]

**Wellness (7-day avg, prev)**
HRV: [7-day avg, range, N days] (previous 7 days [avg])
RHR: [7-day avg, range, N days] (previous 7 days [avg])
Sleep: [7-day avg, range, N days] (previous 7 days [avg])
Sleep quality: [7-day avg, N days] (previous 7 days [avg])
Weight: [7-day avg, range, N weigh-ins] (previous 7 days [avg])
Feel: [7-day avg, N sessions] (previous 7 days [avg, N])
RPE: [7-day avg, N sessions] (previous 7 days [avg, N])

**Section 11 flags**
⚠️ [Title]
[Fact label]: [one fact per line]
Analysis: [one short supported analysis]

⚠️ [Next title]
[Fact label]: [one fact per line]

**Fun facts ([sport], descriptive)**
[Groups below, with Peaks, without Most work in a week]

**Interpretation**
Load: [1-2 sentences]

Quality: [1-2 sentences when relevant]

Watch: [1-2 sentences on supported concerns]

Next: [1-2 sentences ending at the next decision]

**Next 7 days**
[Day date]: [sport duration, name; one planned item per line, no clock times]
```

## Sources and gates

Repeat Intensity blocks for every selected sport and actual basis/mapping in the shared sport order. Put complete covered/period weeks and covered/sport sessions in the heading; partial coverage gets a labelled line. Keep separate headings for distinct mappings. Weeks mean rolling chunks in current reports and configured weeks in Season/months; a covered week is not necessarily fully measured. Decode the file-level report_intensity_schema; require matching rule_version in each block, otherwise unavailable. Display keys of selected; sports[sport] supplies totals, active-week and zone columns, while zones[mapping] supplies three raw seconds and session/week counts. Show active-week counts and partial coverage without inferring exact covered dates. Resolve explicit rolling refs using the consuming chunk's dates, and monthly blocks by first occurrence in monthly_1y, monthly_2y, monthly_3y. Distinct mappings of the same basis stay separately labelled. Selected sports without zones get a short zones-unavailable line; pace/GAP is deferred. Missing report_intensity blocks mean unavailable; a present empty block is authoritative. Never use legacy primary/all-sport fields as fallback. Use ready-block tid[sport][mapping] percentages; for compact rows divide each bucket's raw seconds by their sum, never average percentages. Keep observed coverage and unknown activity-fetch completeness explicit.

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).
For compliance, read the compact per-step rows with their evaluator, completion and availability; select main work from the authoritative prescription. Unlabelled lower-target rows are not automatic exclusions, and compressed-set totals are never an all-steps aggregate.

- Filter recent_activities to the exact local dates, count each ID once and sum moving_time_s and achieved TSS by sport. No planned TSS. Mark incomplete duration/TSS coverage. Phase is derived_metrics.phase_detection, still based on configured calendar weeks.
- Plan followed uses readable labels only: followed, partly followed, not followed, planned without steps, no plan, unknown. Omit zero categories. Never show not_assessed as a category and never conflate a known pairing with no plan. Pairing and duration come from plan_pairing for every sport; interval_data.plan_match supplies assessed step results. A no-step plan belongs in planned without steps even when its duration matches. Walk/Hike step assessment remains out of scope. Their plan participation stays in the Plan line, with no duration verdict or Highlights entry. Count a planned walk not done only with explicit matching historical calendar evidence; activity absence alone is insufficient. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).
- Anywhere a session line appears, use marker only, never status words: ✅ for followed; ⚠️ for partly followed; ❌ for not followed. A warning/failure gets a short supported reason, e.g. `(+1h10m)`, `(-20m)` or `(steps off)`. Paired no-step sessions other than Walk/Hike use ✅ when plan_pairing.duration.within_tolerance is true, ⚠️ with delta when false; null gets no success/failure marker. Walk/Hike never get duration markers. There is no marker without a plan or for unassessed steps. Do not classify a step plan by duration alone.
- Keep available plan identity and relevant planned/done duration when a deviation needs explanation. Use plan_pairing.plan.name and duration.planned_s, with interval_data.plan_match.plan.name and interval_data.plan_match.plan.duration_s as compatible captured detail. Use a date and short name; omit unavailable or duplicate names and never infer duration from a name. Use ridden for rides, done for non-rides. A Highlights line remains one line; put necessary identified-window detail in Key session. Paired unassessed steps have no verdict. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).
- Highlights replaces the full session list. Include every ⚠️ or ❌ plan-marked session without a count cap; a Section 11 flag alone does not add a Highlight. Expand at most 2-3 key sessions where execution deviates, prioritising notable sessions if four or more hard days occurred. Put the status emoji in the header. Matched window identifies exact steps/sets and bounds only, without raw method/status keys or "plan matched, followed". Read intervals.json by exact ID when has_structure and detail is needed. Never substitute whole-session average/NP for step Actual. Omit unavailable key-session rows. Each set has its own target, evaluable count and supplied set average; the set mean never determines the count. Keep not-ridden reps separate from ridden reps below target. Unknown recording/completion is not proof a rep was skipped. An ordinary step retains its exact Target and Actual. Give one short reason for each miss, with detailed per-rep evidence only where it deviates.
- Retain producer gates and N: decoupling interpretation requires >=90 min and 0 < VI <=1.05, and no `decoupling_detail.comparability: plan_changes_power`; a flagged session keeps its value with "plan changes power" and no drift verdict. Name rising or falling power when detail says so; falling power with rising HR stays adverse coupling; EF requires cycling >=20 min, power+HR and the same VI gate. HRRc is numbers only, never trend words; 7-day avg needs N>=1 and 28-day avg N>=3. Interpretation mentions HRRc only if several sessions agree; harder output itself can lower HRRc.
- Zones and TID use derived_metrics.report_intensity_7d / report_intensity_28d, each period's selected map, tid percentages and sports coverage columns. Labels include sport, actual zone_basis/mapping and coverage; render the first three tid percentages as Z1+Z2/Z3/Z4+. Previous seven days uses rolling_7d_chunks[1].report_intensity, independently selected. Drift uses capability.report_intensity_comparison and its observed-session limits, never an unmatched or partial comparison. See [Report intensity source](../../SECTION_11.md#report-intensity-source). Capability uses durability, efficiency_factor and hrrc. No Best efforts or power/HR-curve block in this report; Peaks remain descriptive fun facts.
- Current fitness uses current_status.fitness and supplied load/recovery metrics. Previous endpoints need exact dated history, never invented CTL/ATL/TSB. Keep the coupled ACWR and readiness gates. Wellness uses each chunk.wellness for avg/range/day counts. Weight 7-day avg retains the four-observation gate. Feel/RPE use populated exact-window recent_activities with N (Feel 1 Strong to 5 Weak, RPE 1-10).
- Monotony uses derived_metrics.monotony_main_sports with its supplied sports, value and same-set chronic context. A material unavailable value gets a short reason, never a primary/all-sport fallback. Strain stays all-sport context; the strain alarm uses available strain_main_sports for the same seven-day selected set, never legacy strain. Hard days uses rolling_7d_chunks[0].hard_days with hard_days_coverage for these rolling dates, not the configured current week. For partial coverage show, for example, "Hard days: 2 (1 day without zone data)". Unknown or missing coverage displays unknown instead of a bare 0; no_activities means no observed activities, not proven rest. Preserve the producer's count and reasons.
- Each Section 11 flag has its own ⚠️ title and fact lines, separated by a blank line. Z3 creep concerns sessions not planned as intensity: use plan_pairing.targets_intensity and z3_time.power_s / hr_s, not all Z3 in the week. Keep unknown intent unknown. When power and HR disagree strongly show both. With zone_reference, state its basis and supported threshold/environment, e.g. `Zones: power, from indoor FTP 260 W`; missing FTP/environment stays explicit. Do not apply one session's reference to others. Add one short analysis line when the facts support it, whether or not provenance is present. A power/HR discrepancy may suggest checking zones, not establish a cause. Expand the supported interpretation in Watch. Provenance does not establish the cause or validate zones. hard_day_details distinguishes days hard only via power Z3. No high-drift count flag.
- Next 7 days is tomorrow through today+7 from planned_workouts, in chronological order, one item per line: `Thu 16: Ride 3h, Endurance`. This rolling preview is not the next configured training week and does not establish a phase transition. Keep proposed transitions conditional on the supplied plan and its coverage; never treat them as completed work or use them to relabel the reported period. No clock times. Include a multi-day calendar entry when its inclusive date/end_date span overlaps that window, even if it started earlier; show it once with its full range, for example `Holiday - Off Season, 3–6 Nov`. HOLIDAY is a planned break, not illness or a training session; do not invent sport/duration for it. Missing end_date means a single-day entry.
- Fun facts sources: latest.json.fun_facts.rolling_7d for cycling and sport_fun_facts.rolling_7d.sports for the other four fact sports, gated by derived_metrics.report_intensity_7d.selected. Require compatible identity/selection markers and matching start/end as defined in [Descriptive Period Facts](../../SECTION_11.md#descriptive-period-facts).

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
