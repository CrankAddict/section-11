# Pre-Workout Report Template

> This template defines the standard output format for pre-workout reports.
>
> Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) before writing the report.
> Read `latest.json.data_overview` first for companion availability and route/map status. Resolve paths against that latest file's local folder or URL base; for Manual uploads without folders match by filename. Presence alone does not prove AI access. Weather times use local HH:MM from `display_time`; add a zone only when it differs from the athlete's timezone or is a UTC fallback. The Data updated header retains its date, time and zone. Maps and data fields keep their existing zone/offset labels. Use 16-point compass directions, never degrees. Read matching `route_weather_map.pages` before showing them in order, directly after the report text; identify any missing page. Do not offer maps as downloads or ask the user to download/upload them; use the text brief when unavailable.
> Fields in `[brackets]` are placeholders. Omit fields that don't apply.  
> **Data Freshness:** Take every number from a current read of the source that owns it: training metrics and planned sessions from the source JSON file, stable athlete facts (such as a tested bottle quantity) from the current official dossier, athlete-reported values from the athlete's explicit current statement, and external conditions such as weather from their current source (see SECTION_11.md §Output Format Guidelines). Never take a number from memory or an earlier chat. Do not carry forward values from earlier reports or earlier in the conversation. Re-read before quoting.  
> **Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON; they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. See SECTION_11.md §Display Unit Semantics.

---

```
**Pre-workout: [Weekday D Month]**
Data updated: [local date time + zone; label UTC fallback]

**[Go / Modify / Skip]**
Signals: [green/total; unavailable explicit]

Verdict: [Exactly two sentences: readiness against baselines and load context, then the supported proceed/modify/skip rationale and next action.]

**Today: [session name]**
[type, with outdoor/indoor status when known]
Distance: [route distance in supplied display units; if available]
Ascent: [route ascent in supplied display units; if available]
Terrain: [course_character; if available]
Duration: [formatted duration; if present]
Planned TSS: [session planned TSS; if present]
Main set: [condensed supported structure; if present]

Climbs
[position]: [length] at [avg]% (max [max]%)
[One line per supplied climb; omit unavailable values and the block if none]

Pacing: [one supported sentence connecting terrain to this session's effort]

**Weather on the route**
Start: [HH:MM; append (assumed) when applicable]
[Assumed only: No start time set. When are you leaving?]

Moving time: [formatted moving window]
Total time: [formatted elapsed window]
Wind: [compass] [speed range and supplied units]
Gusts: up to [maximum and supplied units]
Strongest gusts at: [bounds of the band holding the maximum gust; only if supported]
[Dominant wind effect]: [where it applies; only if supported]
Rain: [native-period amount], [probability]% [supported timing]
Temperature: [range]
Feels like: [available range, or unavailable]
[If map unavailable/partial: one short block per supplied forecast band, from bands[].display]

Prepare: [supported actionable advice; omit if none]

Note: [only material limits, including missing pages; omit routine diagnostics]

[For a non-indoor ride without a usable route, or a run, use the full home block:]
**Weather at home**
Place: [place] ([you said / from Intervals.icu / from dossier])
Time: [planned local window, or explicitly labelled daily window]
Temperature: [range]
Feels like: [available range, or unavailable]
Wind: [compass] [speed range and supplied units]
Gusts: up to [maximum and supplied units]
Rain: [native-period amount], [probability]% [supported timing]

Prepare: [supported actionable advice; omit if none]

[For a non-indoor Walk/Hike, use short home weather instead of the full block:]
**Home ([place], [source], [same forecast window])**
Weather: [dry], [temperature], [wind]
[Rain forecast: replace dry with native amount/probability; move wind to:]
Wind: [compass and speed], gusts [value]
[Attached route only: Route forecast: rides only]
[Every Weather, Wind and route-reason line stays within 40 characters]

[Repeat Today and its eligible weather for each planned session, in plan order]
[If rest day: Rest day: no sessions scheduled.]
[If rest day: Next session: [Day]: [workout preview]]

**Readiness**
RHR: [XX] bpm (baseline: [XX] bpm)
HRV: [XX] ms (7d avg: [XX] ms)
Sleep: [XhYm]
Sleep Quality: [X/4]
Sleep context: [conditional: observed run, dates, supplied durations, personal reference and coverage; or dated athlete-reported fragmentation; low confidence]

**Load**
Phase: [phase_detection.phase] Wk[phase_detection.phase_duration_weeks]
TSB: [X.XX]
CTL: [XX.XX]
ATL: [XX.XX]
ACWR: [X.XX] ([assessment]); start-of-day
Recovery Index: [X.XX] ([assessment])
Ramp Rate: [X.XX]
Load/Recovery: [X.X] (tolerance [X.X]); [context note if near edge]
Durability (cycling): [X.XX]% 7d mean([X]) ([trend])
EF: [X.XX] 7d mean([X]) ([trend])
Monotony ([supplied main sports]): [supplied combined value]; [material context]
Hard days this week: [count with missing-zone-day coverage, or unknown]

**Intensity ([sport], [basis/mapping], [complete coverage])**
Z1+Z2: [XX]%
Z3: [X]%
Z4+: [X]%
TID 7d: [Classification]
PI: [X.XX]
TID 28d: [Classification]
[Partial coverage: separate dated/period-labelled line]
[Drift: supported non-consistent comparison only]
[Repeat blocks in shared selected-sport order]

**Last 7 days**
Hours: [XhYm]
Activities: [XX]
TSS: [XXX]

Weather data by Open-Meteo, CC BY 4.0.
```

After the dated header and Data updated, put Go/Modify/Skip first, with the signal count and a labelled two-sentence Verdict paragraph. Count the supplied readiness_decision.signals statuses, never add a signal from sleep context or live ACWR; show unavailable signals explicitly. Preserve the deterministic recommendation and every override gate below. Follow with each Today session and its weather, then labelled Readiness, Load, selected-sport Intensity and Last 7 days blocks. Preserve every existing field and conditional below. Omit absent Duration and Main set lines entirely; never print "no structure" or a substitute missing-structure line.

When showing calendar context from planned_workouts, include multi-day entries whose inclusive date/end_date span covers today (or overlaps the displayed planned week), including entries starting earlier. Show each once as `Holiday - Off Season, 3–6 Nov`, with its full range. Missing end_date means a single-day entry. HOLIDAY is a planned break, not illness or a session needing workout/weather fields; retain any separately planned sessions and the independent health-context gates.

Use workout_summary as source. Condense to main set using SECTION_11's Main work rule: identify roles from prescription structure, durations and targets, using its name or description as context only; workout step text is optional. Omit a warm-up, cool-down or recovery step only when that role is clear from this evidence. A lower target alone is insufficient, and sustained endurance work or an active connector must not disappear from the main set. If the distinction is ambiguous, retain the relevant steps and state the uncertainty. Square-bracketed text in workout_summary (`[step not summarized]`, `[repeat not summarized]`, `[target not shown]`) marks a step, repeat or target the summary could not render. A summary without a marker lists every step with its duration and its power target (or HR target when no power target is set); it does not carry secondary targets such as cadence or an HR target set alongside power, and where it compresses repeated steps it shows them at the first step's value when each is within 2 W and 2 s of that first step. If workout_summary is null or carries a marker, take the plan from whichever of `description` (entries up to 7 days ahead) or `description_preview` (later entries; its first 3 lines only, so say the plan may continue) the entry carries; if that field is absent or empty, report a marked summary as given and say it is incomplete, or for a null summary give the workout name and duration when present, omitting Main set without a missing-structure line. Never invent targets or step roles.

Weather belongs directly beneath the session's details. Only a session explicitly marked indoor skips weather because of setting; a missing route never makes a session indoor. Rides and runs retain full weather blocks. Only outdoor rides have route forecasts: a usable ride route's unavailable brief gets its reason, never home substitution. Runs use full home weather, not a route forecast. Non-indoor walks and hikes use the short home-weather form below even with an attached route; attachment does not make them eligible for route forecasts. Unresolved setting is stated rather than treated as indoor. Home forecasts require actual fetch capability and the location gates below; do not print the old point-forecast disclaimer. No weather block on rest days.

**Walk/Hike home weather.** Use the same home-source order, permitted fetch, freshness, units and planned time window as the full home block. Keep place/source and the window once in a shared Home heading; this is point weather, never weather along the attached route. The only weather facts are one short Weather line, plus a short Wind line when rain is forecast. Each data/reason line is at most 40 characters. With supported dry weather, write for example `Weather: dry, 13.0 °C, W 3.0 m/s`; dry still requires supported zero amount and 0% probability. For forecast rain, replace dry with the native-period amount and probability, for example `Weather: 0.6 mm/h 55%, 8.0 °C`, and move supported wind/gusts to `Wind: NW 3.5 m/s, gusts 6.5 m/s`. Positive rain probability with an amount below 0.05 mm uses `<0.1 mm/h` for an hourly period, never dry. Retain one decimal and the actual rain period; omit absent components or give a short unavailable reason without inventing values. Do not expand this into a full home block to fill missing fields. With a walk/hike route attachment, also shorten the supplied not-outdoor-cycling reason to `Route forecast: rides only`. No route weather or map is implied. Indoor omission and the existing disabled rule take precedence. The single final linked weather attribution remains required for displayed forecast values.

No middle-dot separators or hyphen-prefixed continuation lines in report text. Reformat existing display labels into the labelled lines without altering values. Use the [weather template's supported wind/gust and rain rules](WEATHER_REPORT_TEMPLATE.md#supported-wind-gust-and-rain-lines). Dominant wind effect means estimated air resistance relative to calm air: Headwind adds it, Tailwind reduces it and Crosswind is roughly neutral (can slightly help or hinder); Calm is exclusive to 0 m/s. Consume the supplied bands under the producer's 80°/110° rule, preserving coverage, location and tie gates; do not reclassify them. For `start_passed`, print `Start: 10:30 (assumed)` then `Planned 10:00 has passed.` using the supplied times, then `When are you leaving?` on its own line and a blank line. Never retime a cached brief.

The attribution is one line, last in the report text, with linked provider/licence names: `Weather data by Open-Meteo, CC BY 4.0.` Follow the [single-line attribution rule](WEATHER_REPORT_TEMPLATE.md#attribution). Omit it if no forecast values are shown. Do not print a transformation note, safety tagline, GeoNames credit or fetched time in the report; the unchanged PNG footer retains its own notes. The displayed place comes from the athlete's source; GeoNames attribution remains in API documentation and other geocoding displays. Show matching PNG pages that were actually read directly after the report text, in session/page order.

---

## Conditional Fields

Repeat Intensity blocks in shared selected-sport order for each actual basis/mapping. Put complete covered/period weeks and covered/sport sessions in the heading; put partial coverage on its own line. Weeks mean rolling chunks in current reports and configured weeks in Season/months; a covered week is not necessarily fully measured. Decode the file-level report_intensity_schema; require matching rule_version in each block, otherwise unavailable. Display keys of selected; sports[sport] supplies totals, active-week and zone columns, while zones[mapping] supplies three raw seconds and session/week counts. Show active-week counts and partial coverage without inferring exact covered dates. Resolve explicit rolling refs using the consuming chunk's dates, and monthly blocks by first occurrence in monthly_1y, monthly_2y, monthly_3y. Distinct mappings of the same basis stay separately labelled. Selected sports without zones get a short zones-unavailable line; pace/GAP is deferred. Missing report_intensity blocks mean unavailable; a present empty block is authoritative. Never use legacy primary/all-sport fields as fallback. Use ready-block tid[sport][mapping] percentages; for compact rows divide each bucket's raw seconds by their sum, never average percentages. Keep observed coverage and unknown activity-fetch completeness explicit.

| Field | Rule |
|-------|------|
| Phase | Include only when `phase_detection.confidence` is "high" or "medium". Omit when "low" or phase is null |
| Weather | Skip explicitly indoor sessions. Rides/runs use full blocks; Walk/Hike uses short home lines as above, including with an attached route. Retain all source/capability gates. Use the shared [Point-weather location](../../SECTION_11.md#point-weather-location) rule: route data for an eligible outdoor ride takes precedence over any home location for that ride's weather. For a separate point forecast, use an explicit current-chat athlete statement `(you said)` first, then `athlete_profile.location` in the current `latest.json` `(from Intervals.icu)` as the default, then the current official dossier's Home region `(from dossier)` only when `athlete_profile.location` is null/empty. Always show the place and source. The chat override is valid only for that conversation, never from memory or earlier chats; heartbeat configuration is not a weather-location source. If something indicates the athlete is elsewhere and the location is unresolved, omit weather or ask. City-level text requires [Open-Meteo geocoding](../agentic/EXTERNAL_APIS.md#geocoding-for-point-weather); ambiguity or failure means unavailable with the reason, never a guess or a fallback to a lower-priority location. With no location in any source, say "A home forecast isn't available: no home location. Add your city/country to your Intervals.icu athlete profile, or a Home region in your dossier." Actual weather-fetch capability is still required |
| Prepare (weather) | Include only if actionable (e.g., dress warm, indoor day). When forecast triggers heat stress Tier 1+: Tier 1: note hydration emphasis. Tier 2: specify session modification per Environmental Conditions Protocol session-type rules (e.g., "Threshold intervals planned: keep power targets, consider reducing from 4×8min to 3×8min"). Tier 3: recommend reschedule or endurance-only. See **Environmental Conditions Protocol** in SECTION_11.md for tier definitions and session-type rules. |
| Monotony | Use derived_metrics.monotony_main_sports and its supplied sports/interpretation/context. Include the value **only** if > 2.3; omit when normal. If materially unavailable, give a short reason without substituting legacy total or primary values |
| Hard days | Use derived_metrics.hard_days_this_week with hard_days_coverage for the configured current week. Partial coverage: e.g. "Hard days: 2 (1 day without zone data)". Unknown or missing coverage: say unknown, never a bare 0. no_activities means no observed activities, not proven rest. Do not reclassify days |
| Durability (cycling) | Include if qualifying sessions exist. Omit if 0 qualifying sessions in 7d |
| EF | Include if qualifying sessions exist. Omit if 0 qualifying sessions in 7d |
| TID 28d + drift | Use derived_metrics.report_intensity_28d and capability.report_intensity_comparison, matched by sport/basis/mapping with coverage read from both ready blocks. Include only supported observed-session shifting/acute_depolarization; omit for consistent, partial or unavailable evidence. Retain unknown-fetch limits |
| Polarization | Use derived_metrics.report_intensity_7d.selected and tid[sport][mapping] percentages as Z1+Z2 / Z3 / Z4+. Label sport, actual basis/mapping and weeks/sessions coverage. See [Report intensity source](../../SECTION_11.md#report-intensity-source) |
| Load/Recovery context | Include tolerance note only when within 0.2 of threshold |
| Next session | Include only on rest days |
| Distance / Ascent / Terrain / Climbs / Pacing | Terrain and climb detail require `has_terrain: true`, `route_status: "ok"` and matching event ID and complete `route_ref` in `routes.json`. Quote supplied `display.position`, `display.distance` and elevation units; gradients use %. Include each supplied climb on its own line, followed by Pacing. `no_elevation` preserves distance/location in `route_geometry`, but never infer flatness, zero ascent, climbs or terrain-adjusted pacing. Omit unsupported fields. State other route limitations when route advice is requested. Full pre-ride briefing available on request |
| Route weather | Only for an eligible outdoor ride with an `ok` route with matching event, full route_ref, departure, cache_key and brief_id in the summary/detail. Check tier and expiry at report time even when not printed. Use one fact per labelled line with blank lines between identity, facts and maps; band detail only for a missing/unreadable map or partial brief, copied from forecast `bands` after Feels like, never aggregated from raw sections. Outlooks have no bands: show broad trends with uncertain wind direction/rain timing. Identify missing coverage and actual precipitation-period durations; maxima are not ride totals. For `stale`/`unavailable`, give the limitation without claiming current conditions. Omit when disabled. Do not infer safe roads or exposure, or manufacture a Go decision from missing weather. Avoid duplicating a point forecast when the route brief answers the same question. Required provider attribution overrides citation-free formatting; see SECTION_11 Weather Data Source |
| Sleep context | Include when fresh `sleep_context.repeat_context` is true, when the athlete explicitly reports fragmented sleep, or when the athlete asks about a pattern. The producer's rule requires the latest three dates each strictly below the disjoint 28-night median and their combined difference ≥3600 s; never add a per-night seven-hour floor or percentage. Quote supplied sleep displays, dates, reference and coverage, with low confidence. Label a seven-date run at least 7 and a partial window partial. For absent, stale or unassessable data, say unavailable when a pattern is requested; never reconstruct it from aggregate means or call it normal. With false/null and no relevant report or request, omit the line. Fragmentation requires explicit dated current-conversation statements; uncertain timing stays uncertain, and quality/score cannot establish it. Keep measured duration and reported fragmentation distinct when both exist. This context is not sleep debt, a medical inference, a readiness signal or an automatic recommendation change. Apply existing persistence/override rules separately and name the actual evidence. Keep day disruption distinct without double-counting. In Same-Day Continuation, place relevant context within Current state or Decision and retain that replacement block |
| Modify/Skip rationale | Required when recommendation is not "Go" |
| Same-day continuation | Include only when a session has already been completed today and a further session is in question. When triggered, output the **Same-Day Continuation Block** in place of the standard report body, not alongside it. Omit entirely on a first session of the day |

## Readiness Decision Logic

The `readiness_decision` object in `latest.json` provides a pre-computed go/modify/skip recommendation with priority level and individual signal statuses. Use this as the baseline.

**Signal statuses** are in `readiness_decision.signals` (hrv, rhr, sleep, tsb, acwr, ri, each with green/amber/red/unavailable and raw values).

**Phase-adjusted thresholds** are in `readiness_decision.phase_context` (shows which phase modifier shifted the amber threshold).

**Modification guidance** is in `readiness_decision.modification` when recommendation is "modify" (trigger categories + adjustment directions: intensity/volume/cap_zone).

> The `readiness_decision` is the deterministic baseline. The AI may adjust it only under the override rules in **Feel/RPE Override**: athlete-reported state escalates (Go → Modify → Skip) unconditionally; de-escalation is permitted at P2 only, with no more than 2 ambers and an attributed non-training cause; **P0 and P1 are not overridable**. Where contextual factors support a permitted adjustment, state them in the opening Verdict, with no separate Interpretation header.
>
> `signals.acwr` is the **start-of-day** value (the same windows with today's activities excluded), so it does not move when a session is completed today. `derived_metrics.acwr` is live and today-inclusive: retrospective load context only, never used to approve, modify or veto a later same-day session or tomorrow's.
>
> **Sourcing the ACWR status line:** value from `readiness_decision.signals.acwr.value`, label from `derived_metrics.acwr_start_of_day.interpretation`. Do not read `derived_metrics.acwr` for this line; that is the live figure and belongs in the post-workout report.

For the full priority ladder (P0–P3) and signal classification thresholds, see **Readiness Decision** in the protocol.

## Same-Day Continuation Block

Use when a session has already been completed today and a later session is in question. When this block applies it **replaces the standard report body**. Do not also emit the standard Verdict, Today or supporting blocks. See **Same-day Continuation** in SECTION_11.md for the decision rules.

```
Same-day continuation: [Go / Modify / Skip]

Morning readiness: [recommendation] P[priority]: [one-line reason]
Completed session: [type, duration]: [within/above/below intent; goal attained?]
Response: [RPE vs work performed; Feel at the time; power-to-HR evidence if the session passes the validity gate, otherwise "not eligible"]
Current state: [solicited: Feel now, soreness, any new pain or symptoms]
Remaining session: [planned/added; purpose and cost]
Decision: [one sentence]
ACWR: start-of-day [X.XX]; live post-session value excluded from this decision
```

- Current Feel must be solicited, not read from `recent_activities[].feel`
- Quote decoupling or EF only when the session passes its gate (`variability_index` ≤ 1.05 and > 0; `duration_formatted` ≥ 90 min for decoupling, ≥ 20 min for EF). Otherwise state that the evidence is not eligible rather than omitting the line silently. A passing session with `decoupling_detail.comparability: plan_changes_power` keeps its value as "plan changes power", without a drift verdict
- `effort_response: null` is expected on an easy session and is not a data gap. The classifier is calibrated only at IF ≥ 0.65; `intensity_factor` is emitted on a 0–100+ percentage scale, so the cut-off reads as 65 in the JSON and 0.65 as a decimal IF

Read `recent_activities[].interval_data`: `plan_match` supplies timeline labels only; `compliance` supplies scoped power/time counts with availability gates; `icu_detected` supplies descriptive detected-interval cross-checks. Use `intervals.json.session_structure` for rep power and formal evaluation, with authoritative roles and constraints. Never use device/app lap averages, whole-session average/NP or a set mean as rep power or compliance counts. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use). Expired detail leaves only last-captured plan-match context.

## Brevity Rule

- **Route weather:** Each eligible outdoor ride gets one labelled route-weather block; walks/hikes retain only short home weather, adding the supplied route-unavailable reason when a route is attached. Moving time and Total time are separate; keep the assumed-start question on its own line. Add a blank line before Prepare and before Note, omitting either when unsupported. Use `bands[].display` for necessary forecast fallback detail after Feels like, one short labelled fact per line under each band heading. Wind, gusts, temperature and rain use one decimal and collapse equal displayed endpoints; below 0.05 mm with positive probability use `<0.1 mm/h` (retain the actual native period). Render fully supported dry weather as `Rain: dry, 0%`. Reformat labels without changing values. No multi-day comparison here; use WEATHER_REPORT_TEMPLATE.md on request.
- **Weather basis:** Inspect the selected ETA method, calibration counts, stop model, extrapolation, model inputs and route-consistency transfer. Print only material limitations: thin history, generic defaults, aggregate-history proxy or transferred correction, partial coverage, fallback provider or near expiry. Personal windows are planning allowances, not guaranteed coverage or independently validated mountain timing. Main outdoor FTP only; mention a likely stale FTP/zones flag without changing settings or inferring corrected FTP.
- **Weather preparation and departure:** Apply Environmental Conditions Protocol to actionable clothing/fuelling/fluid advice without inventing thresholds or personal tolerances. For assumed reason `unset_time`, the configured default is normally 10:00 local because midnight/date-only is unset. For `start_passed`, put the rolling departure on Start, the original passed `planned_local` on a separate Planned sentence, and the question on its own line. With verified agentic capability, preview the exact push.py time update, execute only after confirmation and re-read the next sync's binding. Never silently retime weather. Outlooks use compact `display_wind_from`, not long sector lists.
- **Opening verdict:** Exactly two naturally wrapping sentences for Go, Modify or Skip. Put additional supported breach facts in the labelled supporting blocks, without changing the decision gates
- **Rest day:** Brief: confirm recovery status, preview next session

## Formatting Rule

- **Durations and sleep:** Always use `_formatted` fields from JSON (e.g., `sleep_formatted`, `duration_formatted`, `total_training_formatted`). Never convert decimal `_hours` fields to display format; the formatted values are pre-calculated from raw seconds and avoid rounding errors.
