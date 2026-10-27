# Season Report Template

**Window:** completed configured calendar weeks in history.json.weekly_180d[:-1], at most about 180 days. Exclude the final current partial row from all Season aggregates and fun facts. Use the actual first start and last end in the header; never assume Monday. Current snapshot and longer-history year comparisons are separately labelled.

Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) in SECTION_11.md before writing the report. That section owns the common layout and content rules; this template owns this report's field order, sources and gates.

## Template Structure

```text
**Season report: [first completed week start] to [last completed week end]**
Data updated: [local latest timestamp]
History updated: [local history timestamp when different]

Summary: [one short paragraph, 1-2 sentences]

**Position**
Season: [current seasonal context]
Phase: [current phase and duration]
Previous phase: [only when supplied and different]

**Phases**
[Start-end]: [phase and N weeks, next phase and N weeks, ending at Deload]
[Start-end]: [next cycle]
[Start-end]: [no detected phase, own line]

**Volume ([N] completed weeks)**
Hours: [total] (avg. [X] h/week over [N] completed weeks)
TSS: [total] (avg. [X]/week over [N] completed weeks)
Longest [ride/run/swim/row or sport session]: [duration, date; repeat for Season-selected sports]
[For cycling add the same ride's supported distance and environment here only]
Longest week: [hours, week of date]

**Fitness**
CTL peak: [value, week of date]
CTL now: [value, snapshot date]
ACWR below 0.8: [weeks]
ACWR 0.8 through 1.3: [weeks]
ACWR above 1.3 through 1.5: [weeks]
ACWR above 1.5: [weeks]
ACWR known: [K] of [N] weeks

**Intensity ([sport], [basis], [complete coverage])**
Z1+Z2: [percentage]
Z3: [percentage]
Z4+: [percentage]
[Partial coverage line only when needed]

**TID 28d (now, [sport], [basis], [coverage])**
TID: [supplied observed classification]

**Hard days ([N] completed weeks, avg/week)**
Hard days: [avg. per week over N completed weeks]
First half ([dates]): [avg. hard days/week]
Second half ([dates]): [avg. hard days/week]
Weeks with a hard day: [K] of [N]

**[Month year] ([same month prior year] in brackets)**
Hours: [current] ([prior])
[Three-month label] monthly avg. hours: [current] ([prior])
TSS: [current] ([prior])
[Three-month label] monthly avg. TSS: [current] ([prior])
CTL peak: [current] ([prior])
CTL end: [current] ([prior])
Hard days: [month avg. per week] ([prior])
Longest [sport session]: [current] ([prior or unavailable; repeat for matched-month selected union])
HRV: [month avg.] ([prior])
RHR: [month avg.] ([prior])
[Material 2y/3y comparison, one fact per line]

**Month intensity ([sport], [basis], [complete coverage on both sides])**
Z1+Z2: [current] ([prior or unavailable])
Z3: [current] ([prior or unavailable])
Z4+: [current] ([prior or unavailable])
[Each side's partial coverage is labelled separately]

**Notable**
[Only non-empty supported lines: FTP changes, data gaps, A-races, next A-race, deviation]

**Fun facts ([sport], descriptive)**
[Groups below, with Peaks and Most work in a day/week]

**Interpretation**
Load: [1-2 sentences on the completed weeks]

Quality: [1-2 sentences when supported]

Year on year: [1-2 sentences when matched]

Watch: [1-2 sentences on material uncertainty]

Next: [1-2 sentences ending at the next decision]
```

## Sources and gates

Repeat Intensity blocks for every selected sport and actual basis/mapping in the shared sport order. Put complete covered/period weeks and covered/sport sessions in the heading; partial coverage gets a labelled line. Keep separate headings for distinct mappings. Weeks mean rolling chunks in current reports and configured weeks in Season/months; a covered week is not necessarily fully measured. Decode the file-level report_intensity_schema; require matching rule_version in each block, otherwise unavailable. Display keys of selected; sports[sport] supplies totals, active-week and zone columns, while zones[mapping] supplies three raw seconds and session/week counts. Show active-week counts and partial coverage without inferring exact covered dates. Resolve explicit rolling refs using the consuming chunk's dates, and monthly blocks by first occurrence in monthly_1y, monthly_2y, monthly_3y. Distinct mappings of the same basis stay separately labelled. Selected sports without zones get a short zones-unavailable line; pace/GAP is deferred. Missing report_intensity blocks mean unavailable; a present empty block is authoritative. Never use legacy primary/all-sport fields as fallback. Use ready-block tid[sport][mapping] percentages; for compact rows divide each bucket's raw seconds by their sum, never average percentages. Keep observed coverage and unknown activity-fetch completeness explicit.

- Read latest.json and history.json separately. All Season numbers/facts share the completed-week scope and history freshness. Current phase, CTL and TID explicitly refer to latest. No completed weeks means no fabricated Season view.
- Position uses derived_metrics.seasonal_context and phase_detection.{phase,previous_phase,phase_duration_weeks}. Omit Previous phase when absent or equal to Phase. Phases use completed weekly phase_detected values, coalescing consecutive equal phases inside each cycle. Each cycle ends at a Deload (include consecutive Deload weeks in that ending); show an unfinished final cycle through its actual end. Every null-phase week gets its own dated line and breaks the cycle. Never bridge gaps or rename a supplied phase to Deload. Example: `26 Apr-30 May: Build 4 weeks, Deload 1`.
- Volume sums total_hours/total_tss over the same N rows and labels weekly averages. Longest sessions use each Season-selected sport's maximum longest_session_by_sport across weekly_180d[:-1], including locally unselected weeks, decoded using the columns declared in history.longest_session_schema. Keep partial/no_valid_duration status and exact ties by duration descending, date/ID/type ascending; missing or incompatible rows/schema are unavailable. Longest week uses total_hours. Legacy longest_ride_hours is longest activity of any type and is not this source. For cycling, enrich that winner only from compatible history.fun_facts.season.longest_ride with the same activity_id, date and moving_time_s; it supplies that ride's distance_m, environment and name. Keep any partial status. Missing or mismatched detail leaves distance/name unavailable, never borrow another ride's distance. Display the longest ride once here, not again in cycling Fun facts. The matched-month longest comparison remains a separate dated fact.
- CTL peak is a known completed ctl_end and its week; CTL now is current_status.fitness.ctl with snapshot date.
- ACWR uses supplied coupled weekly 7:28 ratios, never ATL/CTL or a new calculation. Bins are <0.8, 0.8<=x<=1.3, 1.3<x<=1.5, x>1.5. Unknown ratios are not low-load weeks. Omit zero bins; if both above-1.3 bins are zero and at least one ratio is known, replace them with `ACWR above 1.3: none`. Always show `ACWR known: K of N weeks`; unknown initial weeks stay unknown.
- Zones use history.json.report_intensity_season, whose start/end and weeks must match weekly_180d[:-1]. Consume the producer's selected map, tid percentages and sports coverage columns. They sum all that sport's observed zone seconds, including nonqualifying weeks; no current-primary filter, mixed basis or new Season classifier. TID 28d (now) uses latest derived_metrics.report_intensity_28d, independently selected and separately dated. Missing new history is unavailable until ordinary refresh. See [Report intensity source](../../SECTION_11.md#report-intensity-source).
- Hard days use completed-week hard_days. Split the chronological rows into first floor(N/2) and remaining rows; label each half with its actual dates and avg. Omit empty halves; missing days are not zero. Weeks with a hard day counts rows with hard_days>=1.
- Year comparison anchor is the last fully completed calendar month before metadata.last_updated. Match month keys across monthly_1y/monthly_2y/monthly_3y, never positions. Current values followed by prior values in brackets, one metric per line, no difference or percentage-change lines. A three-month monthly avg requires all three matched months per side and its date label (e.g. Jul-Sep monthly avg.). No invented prior-year phase claims. If no matched month, omit the block and mention the limitation once.
- Additional 2y/3y rows need material context: hours/TSS >=15%, CTL >=3 points or zone share >=5 percentage points. These are selection gates, not extra difference/% display lines. A missing/zero prior denominator does not create a percentage.
- Year-comparison intensity and longest sessions use each matched month's report_intensity selection independently and show the union of qualifying sports. Longest values come from that month's longest_session_by_sport under compatible longest_session_schema; pair identical sports only, retain missing/not-selected sides as unavailable, and never sum duplicate monthly tiers. Pair only identical sport, actual basis and mapping_version under compatible file-level rule_version/selection_config, with coverage read from both ready blocks. An absent sport/block or incompatible mapping is unavailable, never zero or a cross-sport match. Preserve a supported zero zone share. Resolve the first report_intensity block for that month in monthly_1y, monthly_2y, monthly_3y; overlapping later rows omit it. An unresolved month is unavailable; never sum tiers. Weekly legacy primary_sport does not select Season intensity.
- Notable includes only non-empty in-window ftp_timeline, data_gaps, completed A-races, supplied next A-race and a supported deviation pattern. Omit "none" placeholders. Goal auditing stays deferred.
- Fun facts sources: history.json.fun_facts.season for cycling and sport_fun_facts.season.sports for the other four fact sports, gated by history.report_intensity_season.selected. Require compatible identity/selection markers and start/end/completed_weeks matching chosen weeks as defined in [Descriptive Period Facts](../../SECTION_11.md#descriptive-period-facts); otherwise unavailable. Keep history freshness and partial/stale power coverage. Most work in a week is a completed configured calendar week. Peaks belong here; there is no Best efforts block in Season.

## Source and display safeguards

Read current source JSON in this response and the current official dossier for stable context; never reuse prior report values. Use local dates, a bold dated header and local Data updated. Keep a separate History updated timestamp when relevant. Follow the shared layout for facts, paragraphs, headings and lists. Previous values go in brackets. Every mean says avg and its window, in its heading when shared; retain observation counts under the report-specific coverage rules. Only the 28-day Fitness section uses start -> now lines. Omit missing or zero-only lines and empty sections, preserving a meaningful zero inside an otherwise populated comparison. Explain missing indispensable source blocks once; never invent observations or print placeholders.

Use supplied display values and formatted durations. Seconds-only durations may round to whole minutes (30 seconds up); decimal hours may remain decimal h. Eligibility always uses exact values. Readiness, formal compliance and progression gates in SECTION_11 are unchanged. A report marker is not formal adherence evidence.

### Fun facts contract

Place **Fun facts ([sport], descriptive)** blocks immediately before **Interpretation**, in cycling, running, swimming, Nordic skiing, rowing order. Show only those sports selected by this report's own period selection. Read supplied period facts, never reconstruct from weekly compact caches. Missing or incompatible selection/facts are unavailable; an empty selection is authoritative. Observations are not tests, FTP/zone evidence or readiness evidence. Retain partial/stale coverage, date, activity name (ID if absent) and separate history freshness.

For cycling, use these blank-line groups, omitting unavailable components:
1. Max power (1 s), with date/name; Max HR, with date/name.
2. Distance ridden for each nonzero environment; Climbed for each nonzero environment. The longest ride is already in Volume and never repeats here.
3. Peaks: one line each for 5 s, 1 min, 5 min, 20 min and 60 min, with date/name. Include only in 7-day and Season fun facts; the 28-day report has its separate Best efforts section.
4. Time in the saddle.
5. Work and Carbs used, each with its equivalent in parentheses; break before the equivalent if needed. Most work in a day uses date, kJ and same-day carbs on separately labelled lines. Add Most work in a week only in 28-day and Season, retaining the supplied dates.

For running, swimming, Nordic skiing and rowing, use three blank-line groups: Max HR with date/name; longest run/swim/Nordic session/row with date/name/duration and available distance, then distance and supported outdoor climbing; Running time / Swimming moving time / Nordic skiing time / Rowing time. Longest sessions belong here only in 7-day/28-day reports; Season keeps them in Volume. No power, work, carbs or equivalents belong to these four sports.

Use Distance ridden / Distance run / Distance swum / Distance skied / Distance rowed, and Climbed. Typical lines fit 40 characters: `Distance ridden: 80 km (outdoor)`, `Distance run: 18 km (outdoor)`, `Distance swum: 2 km (pool/other)`, `Distance skied: 18 km (indoor)`, `Distance rowed: 24 km (indoor)`, `Climbed: 600 m (outdoor)`. Use only supplied settings: indoor, outdoor, open water, pool/other, snow, roller, unknown. Generic Swim is pool/other, never a verified pool; OpenWaterSwim is open water unless supplied as unknown. Settings come solely from the emitted fact environment. Never infer environment from names or pool-length fields. Keep indoor, snow, roller and outdoor distance separate. Label a longest session's distance with its setting too. Any indoor distance, speed or climbing outside the split must also carry (indoor). Unknown is never outdoor. Use metres with explicit m if display conversion is unavailable; omit zero-only climbing.

Put complete metric coverage in its heading when shared. Show observed partial values with a separately labelled metric coverage line, for example `HR coverage: 2 of 3 sessions` or `Indoor distance: 2 of 3 sessions`. Keep date/name and setting attached to the correct fact; a deliberate fact break is allowed, but never a continuation of a Highlights or session line. Duration/longest and HR counts use coverage against activity_count; distance/ascent counts use their own setting's activity_count. Zero coverage omits the metric; missing is never zero. Duplicate-conflicting metrics remain unavailable. Cycling retains its existing counts and partial/stale power coverage.

A clear current official dossier statement of positive grams carbohydrate per bottle is sufficient, whether in prose or the Tested training fuel table. For example, "My training bottle contains 90 g carbohydrate" establishes grams per bottle without needing a table. Never infer grams from bottle volume, a product name or a serving without a per-bottle statement. Ambiguous/conflicting statements do not establish a bottle.

Use the athlete's stated bottle; otherwise use the USDA medium-banana fallback: about 27 g carbohydrate and about 105 kcal per medium banana. Carbs equivalent = carbs_used / 27 or carbs_used / grams per bottle. Work equivalent = work_kj / 105 or work_kj / (4 * grams per bottle). Mechanical work of 1 kJ is approximately 1 kcal expended. This equivalence method note belongs only in the template, not in the report. Round counts to one decimal and say about: `Work: 3600 kJ (energy of about 10.0 of your 90 g bottles)`, `Carbs used: 900 g (about 10.0 of your 90 g bottles)`; fallback uses medium bananas. These are fun comparisons, not fueling advice or estimates of carbs eaten.
