# Weather Report Template

Read this template together with [Shared report layout](../../SECTION_11.md#shared-report-layout) before writing the report.

> On request only, for example "weather for my rides" or "which planned ride day looks better?" Cover all relevant planned outdoor rides in the next five days (120 hours), deduplicating event IDs shared by workouts and the race calendar. This is a conditions report, not readiness clearance, a safety assessment or permission to move a workout.
> **Freshness and binding:** Read current `latest.json.data_overview`, then the matching `routes.json`. Match event ID, complete route_ref, departure, cache_key and brief_id. Recheck departure and `expires_at` at report time, even when freshness is not printed. Never use conversation memory, example JSON or retained pre-departure snapshots as a current forecast. When disabled, say so and show no forecast blocks or maps.
> **Access:** Resolve relative locations against the latest file's local folder, raw URL base or attachments; match filenames for folderless Manual uploads. Presence does not prove AI access. Read matching PNG pages before showing them, in their listed order. Identify missing or unreadable pages; never describe an unseen image, offer a map download, add maps to the artifact ZIP or require an extra Manual upload step.
> **Display:** Use precomputed labels/values in athlete units from `summary.display` and `bands[].display`, reformatted into the lines below without changing numbers. Forecast `bands` are the single source for lettered detail; never aggregate raw `sections`. Copy their local arrival/end and wettest-period windows when needed. Wind, gusts, temperature and rain use one decimal, including `14.0`, `6.0–6.4 m/s` and `9.0 °C`; equal displayed endpoints collapse. Rain below 0.05 mm with positive probability displays `<0.1 mm/h` for an hourly period, never a dry claim. Fully supported dry weather renders as `Rain: dry, 0%`. Preserve units and native-period duration, including non-hourly amounts; maxima are not ride totals.
> **Time and direction:** Read `display_time.zone` and full offset-bearing brief timestamps, but display local HH:MM. Add a zone only when different from the athlete's timezone or a UTC fallback; map and data-field zone/offset labels stay unchanged. Retain the assumed label, rendered as `(assumed)`. For `departure.assumed_reason: "unset_time"`, use `Start: 10:00 (assumed)` with the supplied default time, then `No start time set. When are you leaving?` on its own line and a blank line. For `"start_passed"`, use the supplied rolling departure and `planned_local`: `Start: 10:30 (assumed)` then `Planned 10:00 has passed.`, then `When are you leaving?` on its own line and a blank line. Never calculate a newer departure in the report. With verified execution/write capability, preview a push.py time update and wait for confirmation before `--confirm`; read the next sync's newly bound brief. Use compass directions, never degrees; outlook uses compact `display_wind_from`, rendered on the Wind line as `variable` or the supplied compass range, never a long sector list.

## Output when maps are available

Use one fact per labelled line, with blank lines between header, route identity, facts, maps and rides. No middle-dot separators or hyphen-prefixed continuation lines anywhere in report text. Put the route name first, then date, distance and ascent on separate labelled lines. Add a blank line before Prepare and before Note; omit either when unsupported or unnecessary. The PNG carries the band detail; do not repeat rows beside readable maps. Attribution appears once, on the final report-text line.

```text
**Weather report: [weekday date HH:MM, zone only if required]**
Period: next 5 days

Summary: [One conditions-only sentence from comparable supported forecasts; state unavailable when no forecast supports it.]

**[Route name]**
Date: [Weekday D Month]
Distance: [supplied distance]
Ascent: [supplied ascent]

Start: [HH:MM; assumed and passed-planned-time wording if applicable]
[Assumed only: start-time question on its own line]

Moving time: [formatted moving window]
Total time: [formatted elapsed window]
Wind: [compass] [speed range and supplied units]
Gusts: up to [maximum and supplied units]
Strongest gusts at: [supported band bounds]
[Dominant wind effect]: [supported locations]
Rain: [maximum native-period amount], [probability]% [supported timing]
Temperature: [range]
Feels like: [range, or unavailable]

Prepare: [one actionable clothing/fuelling/fluid consequence, if supported]

Note: [material ETA/coverage/fallback/freshness limitation only; outlook uncertainty when applicable]

[Next ride in the same layout]

Coach note: [One naturally wrapping paragraph: practical implication or refresh reminder]

Rides without a route:
[Day and short ride name: supported reason]
[One ride per line]

Weather data by Open-Meteo, CC BY 4.0.
```

Summary sits immediately under Period and replaces Comparison; it describes conditions only, never readiness or permission to move a workout. Coach note wraps naturally as one labelled paragraph. Rides without a route has one short day/name/reason line per ride, including mixed-route reports. Read matching route_weather_map PNG pages before showing them directly after all report text, in session/page order; name each missing page and never offer downloads. If no planned ride has a usable route within 120 h, use the explicit case below instead. Do not silently drop a ride to meet a length target. Give unusable briefs one line each. The overview lists routed rides beyond the weather horizon for route discovery; this report still covers only the next 120 hours. `rides_total` counts rides eligible for that overview before its 64-ride cap, `rides_omitted` counts cap overflow, and `rides_without_route_beyond_horizon` separately counts later unrouted rides excluded before the cap. A home point forecast must never substitute for route weather inside a ride block; only the separately labelled Home block below is allowed in the no-route case. Completed-activity `weather_summary` cannot fill forecast gaps. No alternate departure, reversed route or unscheduled day is bound by the existing brief, and this report never reschedules training.

## Supported wind, gust and rain lines

Keep Wind direction/speed separate from Gusts and the estimated route-relative effect. Relative to calm air, Headwind adds air resistance, Tailwind reduces it and Crosswind is roughly neutral (can slightly help or hinder); Calm is exclusive to 0 m/s. Using the absolute wind-FROM angle relative to travel, the producer assigns Headwind below 80°, Crosswind from 80° to below 110° and Tailwind at least 110°, with unchanged 10 m forecast wind. These are estimates without shelter or gust-effect modelling. Use supported summary/band compass directions, or explicitly say direction unavailable; never invent a dominant FROM direction from conflicting bands. Outlook uses its compact direction label and has no route-relative effect line.

`Strongest gusts at:` names the km bounds of the forecast band holding the maximum gust. Compare compatible band `gust_max` values with the headline maximum; include all tied maximum bands, joining adjacent bounds only when contiguous. Omit the line when bands, bounds or gust coverage cannot support the maximum's location. Missing gusts elsewhere cannot establish the strongest gust on the whole ride.

For `[Dominant wind effect]: [where]`, use the supplied forecast bands' wind classes and distances, never raw sections or a new classification threshold. Sum the covered distance for each known class; show the unique distance-dominant class only when valid bounds and coverage support it. List its band ranges, combining adjacent ranges; use "first" or "last" only when they reach the route start/end. For example, `Headwind: first 27 km and last 9 km` requires those supplied bounds and a headwind distance exceeding every other class. Omit ties, unknown/incomplete support, and all point-forecast/outlook cases. A band class describes its distance-dominant estimated effect, not constant wind throughout the band. The resulting summary is weighted by supplied-band distance, not exact whole-route class distance or energy.

The Rain line contains the native-period amount and probability. Put long supported timing on its own short line, for example `Rain: 0.1 mm/h, 25%` then `Wettest: 13:00–14:00`. A band's maximum and wettest window do not establish onset or cessation: say "dry until 12:00" or "rain last hour" only when coverage supports it. Otherwise name the wettest window without inventing an onset. Amount and probability maxima can occur in different intervals; do not imply they coincide. Wind samples approximate conditions across an ETA envelope, not guaranteed arrival conditions.

## No planned ride has a usable route within 120 h

Check the current planned calendar and route validity before claiming there are no usable routes; an omitted or capped overview is not enough. A routed ride beyond 120 h does not prevent this case. A usable route with a stale, expired, missing or unavailable brief, or an unreadable map, is still a routed ride: use its existing handling, not a home replacement. The disabled rule takes precedence.

When rides are planned but all lack usable routes, use this layout. Include each ride's day/name and any known invalid-route reason, without inferring flatness:

```text
**Weather report: [weekday date HH:MM, zone only if required]**
Period: next 5 days

Summary: [One conditions-only sentence from comparable supported forecasts; state unavailable when no forecast supports it.]

No planned rides with a route.
Rides without a route:
[Day and short ride name]
[Next day and short ride name]

Attach a GPX/TCX to the planned workout.
The next sync makes its forecast/map.

[Optional Home block, only under the gates below; otherwise the applicable unavailable line]
```

Include the Home block only with actual, permitted weather-fetch capability and a location resolved by the shared [Point-weather location](../../SECTION_11.md#point-weather-location) rule:

1. An explicit current-chat athlete statement, valid only for this conversation, labelled `(you said)`.
2. `athlete_profile.location` in the current `latest.json`, the default Intervals.icu city/region/country, labelled `(from Intervals.icu)`.
3. The current official dossier's Home region, only when `athlete_profile.location` is null/empty, labelled `(from dossier)`.

Route data for the session takes precedence over any home location for that session's weather. Show the selected place and source; never infer home from route geometry, memory or earlier chats, and never use heartbeat configuration as a weather-location source. If something indicates the athlete is elsewhere and the location is unresolved, omit weather or ask. Do not replace an ambiguous nonempty profile location with the dossier.

If the AI cannot fetch weather, print exactly: "A home forecast isn't available in this setup." If all three sources lack a home/base, omit the block and say: "A home forecast isn't available: no home location. Add your city/country to your Intervals.icu athlete profile, or a Home region in your dossier." City-level text needs [Open-Meteo geocoding](../agentic/EXTERNAL_APIS.md#geocoding-for-point-weather). If that lookup is ambiguous or fails, or the weather fetch fails, supply no forecast values and state the specific unavailability reason.

Use [External API Reference](../agentic/EXTERNAL_APIS.md): Open-Meteo first, MET Norway fallback. Use actual current provider data and the single final linked attribution below, without a transformation note whether or not a map is shown. Never use completed-activity `weather_summary` or old snapshots as a forecast.

```text
**Weather at home**
Place: [place] ([you said / from Intervals.icu / from dossier])
Date: [planned ride day]
Time: [planned local window, or explicitly labelled daily window]
Wind: [compass] [speed range and supplied units]
Gusts: up to [maximum and supplied units]
Rain: [native-period amount], [probability]% [supported timing]
Temperature: [range]
Feels like: [available range, or unavailable]

[Repeat Date/Time and weather facts for each other day with a planned ride]

Weather data by Open-Meteo, CC BY 4.0.
```

Use a separate labelled set of facts for each day with a planned ride, at its planned time where known. If time is unknown, identify the daily window being summarized; never invent a departure. Preserve athlete units, display decimals, native rain periods and unknown fields. No wind classes, strongest-gust km locations, sections, bands, maps, ETA or route claims belong in the Home block. It remains a separate point forecast, never a substitute inside a ride block; do not print the old point-forecast disclaimer. The place/source identifies the forecast location.

When there are no planned rides at all within 120 h, replace the no-route message/list and attachment hint with one line: "No planned rides in the next 5 days." The Home block remains optional under the same gates; omit it when there are no planned ride days to summarize. Do not invent unscheduled days or imply that weather authorizes adding a ride. In a setup without fetch capability, retain "A home forecast isn't available in this setup."

## No-map and partial paths

Only when a map is unavailable, partial, missing or unreadable, add short band blocks from `route_weather.bands` after Feels like and before optional Prepare/Note. For a missing continuation page, show its affected bands in text and identify which page is missing; do not repeat rows already visible. If no page is usable, cover every supplied band, without merging away changing conditions.

```text
Temperature: [range]
Feels like: [range, or unavailable]
**Band [Letter] ([display.distance])**
Time: [local arrival-to-end envelope]
Effect: [display.wind_class]
Wind: [display.wind]
Gusts: [display.gust_max; unavailable when absent]
Temperature: [display.temperature]
Feels like: [display.feels_like]
Rain: [native-period amount], [probability]%
Wettest: [rain.wettest_window_local]
Coverage: [material gap only]

Note: [map unavailable or missing page and reason; other material limits]
```

Keep each fallback band in its own short block, one labelled fact per line. Retain every supplied band and every material gap. `wind_speed`, `gust_max`, `temperature` and `feels_like` retain rounded values plus units; `display` supplies matching text. The band's estimated effect class is distance-dominant, with the existing head/cross/tail/calm/unknown tie order. Its from-direction follows the existing distance-weighted compass rule. Neither is a promise of constant wind. Rain amount and probability maxima may occur in different intervals. `coverage` must qualify missing fields/time: unknown rain is never dry. Empty bands have no assigned section; do not invent values. If an older brief lacks `bands`, say band detail is unavailable and retain only supported summary values; do not rebuild bands from raw sections.

| Situation | Handling |
|---|---|
| Fresh `ok` forecast | Compact block plus matching pages; no band transcript beside a complete map |
| Fresh `partial` forecast | Supported headline plus material gaps and producer bands; no PNG is generated |
| Stale, expired, missing or unavailable | Ride and reason only; no current forecast, old PNG, ranking advantage or replacement fetch |
| Disabled | "Route weather is disabled." No weather blocks, maps or cached snapshots; do not enable it |
| No planned ride with a usable route within 120 h | No-route message, ride list and GPX/TCX hint; separate labelled Home point forecast only with actual fetch capability and a known home/base; otherwise the applicable unavailable line |
| No planned rides within 120 h | "No planned rides in the next 5 days." Optional Home block follows the same gates and planned-day rule; no invented ride days |
| Outlook | Broad trend and window, direction and rain timing uncertain; no bands, headwind sections or precise rain arrival |
| Budget/route/horizon limitation | State it; unavailable data do not establish a better day |

Outlooks have empty `sections` and no `bands` array. Use `outlook.window_utc`, compact wind label/range, native precipitation periods and summary extrema. Feels-like remains unavailable when absent; never reconstruct it from air temperature. Compare only shared supported measures with comparable tiers/coverage, never a precise rain hour against a broad trend as equally certain.

## Material limits and preparation

Inspect ETA method/status, sample counts, stop model, extrapolation, transferred route-consistency correction, coverage, provider/fallback and fetch/expiry. Print short labelled limits lines when thin history, generic assumptions, terrain extrapolation, partial coverage, near expiry, fallback provider or a likely stale main-FTP/zones flag affects the decision. Otherwise these checks need not become separate lines. Moving and elapsed windows remain distinct; they are planning ranges, not guaranteed timing or safe speeds. Do not infer corrected FTP or change settings.

Use [Environmental Conditions Protocol](../../SECTION_11.md#environmental-conditions-protocol) for heat/cold and clothing, and the existing route nutrition/hydration guidance for fuelling and fluid. Read the current official dossier when tested tolerance, clothing, carrying capacity or preferences matter. No new weather thresholds, carbohydrate multipliers, universal fluid volume or invented personalization. Retain the protocol's fallbacks for missing thermal baseline/humidity; disclose a material missing input. A schematic map supplies no basemap, road-surface, shelter or safety evidence.

## Attribution

Use exactly one final report-text line for Open-Meteo, identical for route and home forecasts:

Weather data by [Open-Meteo](https://open-meteo.com/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Omit the line when no forecast values were shown. Do not append a transformation note to report text.

Use the actual provider name for fallback: Weather data by [MET Norway](https://api.met.no/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If separate blocks use both providers, name and link both on that same final line, with the licence once. Never credit Open-Meteo for MET-only data.

This line remains required with a map, without a map and for partial route briefs. Do not print "Not a safety assessment", a GeoNames credit or fetched time in report text. Inspect freshness internally; describe a material expiry/fallback limitation without adding fetch timestamps. The unchanged PNG footer keeps its safety note, provider, fetch time and transformation note.

The report's place comes from the athlete's source, not GeoNames, so it omits a location credit. Keep the GeoNames attribution requirement in EXTERNAL_APIS/SECTION_11 for documentation and other displays of geocoding results. Provider attribution, place/source labels and the protocol cross-reference remain exceptions to citation-free styling. See [Weather Data Source](../../SECTION_11.md#weather-data-source) for binding, statuses, provider terms and ETA limits.
