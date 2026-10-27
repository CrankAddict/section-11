# Weather Report Examples

The [route-weather map example](example-route-weather-map.png) is a real-route example render using an archived Open-Meteo forecast (Historical Forecast API) and the v11.82 renderer.

Fictional worked examples, not live forecasts or athlete data. Times use athlete timezone Europe/Copenhagen, so report weather times omit the zone; a different zone or UTC fallback must be labelled. No example embeds a map inside report text. For examples 1, 2 and 5, read the matching route_weather_map pages first, then show them directly after the final attribution in session/page order. No image is attached to those examples; a missing page must be named and maps are never downloads. Current binding and expiry are checked internally. Numeric ranges use consistent decimal places, and equal endpoints collapse. Fenced examples show the plain attribution label; link its provider and licence as the template requires when rendering. Each report has one final attribution line; explanatory paragraphs outside the report are not extra athlete-facing text.

## 1. Two rides with readable maps

```text
**Weather report: Mon 15 Jun 10:00**
Period: next 5 days

Summary: Wednesday has lower gusts and hourly rain maxima than Tuesday at comparable forecast tier and coverage.

**River loop**
Date: Tue 16 Jun
Distance: 60 km
Ascent: 220 m

Start: 11:00
Moving time: 2h00m–2h30m
Total time: 2h05m–2h45m
Wind: E 6.0–6.4 m/s
Gusts: up to 11.0 m/s
Strongest gusts at: 20–35 km
Headwind: first 35 km
Rain: 0.8 mm/h, 65% wettest 12:00–13:00
Temperature: 8.6–9.0 °C
Feels like: 5.0 °C

Coach note: Bring a rain layer for cool, wet stops and keep the existing fuelling plan.

**Lake loop**
Date: Wed 17 Jun
Distance: 60 km
Ascent: 180 m

Start: 11:00
Moving time: 2h00m–2h30m
Total time: 2h05m–2h45m
Wind: W 2.0–3.0 m/s
Gusts: up to 5.0 m/s
Rain: <0.1 mm/h, 10%
Temperature: 12.0–15.0 °C
Feels like: 11.0–14.0 °C

Coach note: Use adjustable layers for the warmer forecast and retain the existing fuel/fluid plan.

Coach note: Follow the Environmental Conditions Protocol and recheck before departure.

Rides without a route:
Thu: Recovery, no attachment
Sat: Loop, invalid attachment

Weather data by Open-Meteo, CC BY 4.0.
```

Both fictional briefs were fetched at 09:30 and expire at 10:35 CEST, so the internal 10:00 report-time check passes. Complete coverage and well-supported personal ETA need no Note line. River bands assign headwind to 0–20 and 20–35 km, crosswind to 35–50 km and tailwind to 50–60 km; only 20–35 km holds the 11.0 m/s gust maximum. Rain periods support its wettest hour, not a claim about onset. Lake's bands do not establish a unique dominant class or gust-maximum location, so those two lines are omitted. Its numeric rain amount is zero with positive probability, hence the trace label. These are explanatory notes, not report text.

## 2. Assumed start and outlook uncertainty

```text
**Weather report: Mon 15 Jun 10:00**
Period: next 5 days

Summary: Friday's outlook has gusts up to 13.0 m/s and a six-hour rain maximum of 4.0 mm, with uncertain timing.

**Mountain course**
Date: Fri 19 Jun
Distance: 96 km
Ascent: 1,650 m

Start: 10:00 (assumed)
No start time set. When are you leaving?

Moving time: 3h15m–5h10m
Total time: 3h20m–5h25m
Wind: SW/W 4.0–8.0 m/s
Gusts: up to 13.0 m/s
Rain: 4.0 mm/6h, 70% timing uncertain
Temperature: 6.0–12.0 °C
Feels like: unavailable

Coach note: Use adjustable warmth and rain protection, and check refills against the broad total window.

Outlook: Fri 08:00–20:00
Direction and rain timing: uncertain
ETA: extrapolated/transferred timing
Provider: fallback

Coach note: refresh when forecast-tier data arrive; preparation follows Environmental Conditions Protocol.

Weather data by MET Norway, CC BY 4.0.
```

The fictional report time is 10:00 CEST on 15 Jun. The compact `MOSTLY SW-W` label supplies direction, not a headwind segment or exact rain onset. No bands support gust locations or a dominant route-relative class in an outlook, so those lines are absent. A capable agent may preview a same-date push.py `--time` update, wait for confirmation before `--confirm`, then read the next sync's new binding. The six-hour rain maximum is not an hourly rate or a ride total. These are handling notes, not extra athlete-facing lines.

## 3. Partial forecast without a map

All fallback windows below are local on 15 Jun. Rows come directly from fictional `bands`, never raw sections. Gusts, feels-like and probability are unavailable in every band.

```text
**Weather report: Mon 15 Jun 11:00**
Period: next 5 days

Summary: Monday's partial forecast has wind at 4.0–6.0 m/s and hourly rain up to 0.4 mm; gusts and rain probability are unavailable.

**Flat loop**
Date: Mon 15 Jun
Distance: 40 km
Ascent: 0 m

Start: 12:00
Moving time: 1h15m–1h50m
Total time: 1h15m–2h20m
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Crosswind: 4–20 km and last 4 km
Rain: 0.4 mm/h
Probability: unavailable
Wettest: 13:00–14:00
Temperature: 8.0–10.0 °C
Feels like: unavailable

**Band A (0–4 km)**
Time: 12:00–12:20
Effect: Headwind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 8.0–9.0 °C
Feels like: unavailable
Rain: 0.2 mm/h
Probability: unavailable
Wettest: 12:00–13:00

**Band B (4–12 km)**
Time: 12:10–12:55
Effect: Crosswind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 8.0–9.0 °C
Feels like: unavailable
Rain: 0.2 mm/h
Probability: unavailable
Wettest: 12:00–13:00

**Band C (12–20 km)**
Time: 12:30–13:20
Effect: Crosswind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 8.0–10.0 °C
Feels like: unavailable
Rain: 0.4 mm/h
Probability: unavailable
Wettest: 13:00–14:00

**Band D (20–28 km)**
Time: 12:45–13:45
Effect: Tailwind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 9.0–10.0 °C
Feels like: unavailable
Rain: 0.4 mm/h
Probability: unavailable
Wettest: 13:00–14:00

**Band E (28–36 km)**
Time: 13:00–14:10
Effect: Tailwind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 9.0–10.0 °C
Feels like: unavailable
Rain: 0.4 mm/h
Probability: unavailable
Wettest: 13:00–14:00

**Band F (36–40 km)**
Time: 13:10–14:20
Effect: Crosswind
Wind: E 4.0–6.0 m/s
Gusts: unavailable
Temperature: 9.0–10.0 °C
Feels like: unavailable
Rain: 0.4 mm/h
Probability: unavailable
Wettest: 13:00–14:00

Map: unavailable, partial brief
ETA: generic, default stops
Provider: fallback
Coverage: gaps identified in each band

**Tue 16 Jun: Ridge loop**
Weather: unavailable, brief expired
Map: omitted, expired
Coach note: prepare adjustable warmth/rain protection per Environmental Conditions Protocol, retain the existing fuelling plan and recheck.

Weather data by MET Norway, CC BY 4.0.
```

For a readable page 1 and missing page 2, show page 1 and transcribe only page 2's bands (for example I–J). If an older brief has no `bands`, state that band detail is unavailable and use only the supported summary. Do not reconstruct it from sections or infer dry intervals from the wettest period.

## 4. Disabled or mixed route availability

Disabled: "Route weather is disabled." No report weather values, maps, historical snapshots or alternate provider fetch.

In a report that also has routed rides, use a Rides without a route label and one short day/name/reason line per ride. Do not infer flatness or substitute home weather inside a ride block. Other unusable briefs receive one-line reasons; neither case clears conditions for riding. If every planned ride lacks a usable route within 120 h, use example 6 instead.

## 5. Passed start, not completed

Fictional report at 10:17 on 16 Jun. Sync supplied a fresh, matching 10:30 departure with `source: "assumed"`, `assumed_reason: "start_passed"` and `planned_local: "2026-06-16T10:00:00+02:00"`. No matching completed activity was found. The report does not retime the forecast itself.

```text
**Weather report: Tue 16 Jun 10:17**
Period: next 5 days

Summary: The route forecast spans 9.0–16.0 °C with gusts up to 12.0 m/s.

**Ridge trail**
Date: Tue 16 Jun
Distance: 96.5 km
Ascent: 1,657 m

Start: 10:30 (assumed)
Planned 10:00 has passed.
When are you leaving?

Moving time: 3h20m–6h50m
Total time: 3h20m–8h30m
Wind: 4.0–9.0 m/s
Direction: unavailable
Gusts: up to 12.0 m/s
Rain: 0.6 mm/h, 65%
Temperature: 9.0–16.0 °C
Feels like: 7.0–14.0 °C

Prepare: bring a rain layer

ETA: generic, default stops
History: no personal timing

Weather data by Open-Meteo, CC BY 4.0.
```

This excerpt does not supply bands supporting a gust location or dominant wind class, so those lines are omitted. The attribution remains identical without a shown map; use supported band fallback where available. A completed ride instead receives "weather unavailable: completed"; after its local date ends, "weather unavailable: missed". Neither is a reason to reuse an old PNG.

## 6. No planned ride has a usable route within 120 h

### Fetch-capable setup with known home

Fictional handling example: the AI has actual, permitted weather-fetch capability, no explicit current-chat location override, and `athlete_profile.location` in current `latest.json` is "Roskilde, Denmark". This is the default source; the current official dossier's Home region is used only when that profile location is null/empty. Following the shared [Point-weather location](../../SECTION_11.md#point-weather-location) rule, an explicit current-chat athlete statement would take priority for that conversation only, never from memory or earlier chats. The current calendar has only the three unrouted rides below within 120 h; any routed ride beyond that horizon is irrelevant to this case. Geocoding resolved the exact Roskilde city in DK, and Open-Meteo returned current data for the known planned times/windows. These example values are not data to reuse.

```text
**Weather report: Tue 16 Jun 12:45**
Period: next 5 days

Summary: Home forecasts show rising gust and hourly rain maxima across the three planned ride days.

No planned rides with a route.
Rides without a route:
Wed: Recovery spin
Thu: Steady endurance
Fri: Long ride

Attach a GPX/TCX to the planned workout.
The next sync makes its forecast/map.

**Weather at home**
Place: Roskilde (from Intervals.icu)
Date: Wed 17 Jun
Time: 10:00–11:00
Wind: W 3.0–4.0 m/s
Gusts: up to 7.0 m/s
Rain: 0.2 mm/h, 20%
Temperature: 10.0–11.0 °C
Feels like: unavailable

Date: Thu 18 Jun
Time: 17:00–18:00
Wind: NW 4.0–5.0 m/s
Gusts: up to 8.0 m/s
Rain: 0.4 mm/h, 40%
Temperature: 9.0–10.0 °C
Feels like: unavailable

Date: Fri 19 Jun
Time: 09:00–13:00
Wind: W/NW 3.0–5.0 m/s
Gusts: up to 9.0 m/s
Rain: 1.0 mm/h, 50%
Temperature: 8.0–12.0 °C
Feels like: unavailable

Weather data by Open-Meteo, CC BY 4.0.
```

Use [External API Reference](../agentic/EXTERNAL_APIS.md): Open-Meteo first, MET Norway fallback. Use the template's single final attribution line without a transformation note. Report text omits GeoNames credit because the displayed place is from the athlete's source; API documentation and other geocoding displays retain it. Preserve native rain periods; hourly maxima are not ride totals. Use one labelled set of facts per planned ride day, without adding Saturday/Sunday or inferring timing from ETA. Unknown starts use an explicitly labelled daily window. No wind classes, strongest-gust km locations, sections, bands, maps, ETA or route claims are supported.

### Setup without weather-fetch capability

For the same three rides and known home, a web chat without weather tools prints:

```text
**Weather report: Tue 16 Jun 12:45**
Period: next 5 days

Summary: Forecast conditions are unavailable in this setup.

No planned rides with a route.
Rides without a route:
Wed: Recovery spin
Thu: Steady endurance
Fri: Long ride

Attach a GPX/TCX to the planned workout.
The next sync makes its forecast/map.

Coach note: A home forecast isn't available in this setup.
```

No Home block, invented values or provider attribution for an unperformed fetch. Never use completed-activity `weather_summary` or old snapshots as a forecast.

### Unknown home or failed fetch

With fetch capability but no explicit current-chat location, a null/empty `athlete_profile.location` in current `latest.json` and no Home region in the current official dossier, keep the no-route message/list and attachment hint, then print: "A home forecast isn't available: no home location. Add your city/country to your Intervals.icu athlete profile, or a Home region in your dossier." Omit the Home block. If geocoding is ambiguous or fails, or the permitted weather fetch fails, report the actual unavailability reason without values. Location memory, an earlier chat, heartbeat configuration or a past activity cannot fill either gap.

### Location source and ambiguity examples

These are selection examples, not additional forecasts. Route data for the session takes precedence over any home location for that session's weather.

| Current inputs | Point-weather result |
|---|---|
| Current-chat statement "I'm in Bergen, Norway today"; Intervals profile Roskilde; dossier Klampenborg | `Place: Bergen (you said)`, only in this conversation after successful geocoding |
| No current-chat override; current Intervals profile Roskilde; dossier Klampenborg | `Place: Roskilde (from Intervals.icu)` |
| No current-chat override; Intervals location null/empty; current official dossier Home region Klampenborg | `Place: Klampenborg (from dossier)` |
| No current-chat override; nonempty Intervals location cannot be resolved; dossier Klampenborg | Home forecast unavailable: geocoding ambiguous. Do not switch to the dossier |
| Earlier chat said Bergen; current Intervals profile Roskilde; no current travel indication | Use Roskilde `(from Intervals.icu)`; the old chat override has expired |
| Athlete says they are away but gives no current place | Omit weather or ask where; do not silently use home |

An exact city/country match must be uniquely resolved under the shared rule. Multiple equally exact candidates need the uniquely highest population only when comparable; a tie or missing population means ambiguous. A failed lookup keeps its actual reason, without a lower-priority-source fallback.

### No planned rides at all

The current calendar is empty within 120 h. This example omits the optional Home block because there are no planned ride days to summarize:

```text
**Weather report: Tue 16 Jun 12:45**
Period: next 5 days

Summary: No planned ride-day conditions to report.

No planned rides in the next 5 days.
```

In a setup without fetch capability, also say: "A home forecast isn't available in this setup." The optional Home block remains subject to the same capability, location and planned-day gates; never invent an unscheduled day or add a workout.

### Nearby cases that do not use this branch

A usable route within 120 h with an expired brief gets its ride/reason line, not the no-route message or a home replacement. A missing map uses supported band text from its current brief. A report with at least one usable route retains the normal ride blocks and one unrouted-ride line for each other ride. Disabled weather still prints only "Route weather is disabled." with no forecast blocks or alternate provider fetch.

## Missing continuation page (synthetic excerpt)

A separate current River loop brief has two map pages: page 1 was read, page 2 could not be read. Its supplied band C covers 35–50 km with the following facts; the other missing-page band remains separately reported when supplied. Insert this fallback after the route's Feels like line. Name the missing page in the text, retain the single final attribution, then show only the page actually read. A second session's readable pages follow it in session/page order. Do not describe unseen map content or offer downloads.

```text
**Band C (35–50 km)**
Time: 12:20–13:10
Effect: Crosswind
Wind: E 6.0–6.4 m/s
Gusts: up to 9.0 m/s
Temperature: 8.6–9.0 °C
Feels like: 5.0 °C
Rain: dry, 0%
Missing map: River loop, page 2
```
