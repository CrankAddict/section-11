# Pre-Workout Report Examples

> Fictional examples showing standard pre-workout report format, not current athlete data.  
> See `PRE_WORKOUT_REPORT_TEMPLATE.md` for field reference.

The fictional Polarization/TID lines use period-local report_intensity blocks selecting cycling. Each seven-day example has four observed cycling sessions with compatible power zones in one rolling week; the 28-day shifting example has sixteen across four chunks. These new intensity values and coverage counts are synthetic, independently supplied for this illustration; they do not reanalyse other example metrics. Fetch completeness remains unknown. These illustrations decode the file-level report_intensity_schema; counts do not imply exact covered dates.

The point-weather blocks use the shared [Point-weather location](../../SECTION_11.md#point-weather-location) rule. Example 2 uses `athlete_profile.location` from current `latest.json`; example 4 uses a current-chat statement; example 5 uses the current official dossier's Home region because the profile location is null/empty. Eligible outdoor-ride route data takes precedence; unresolved travel means omit weather or ask. Rest days and explicitly indoor sessions have no weather. Missing routes never establish indoor status. Examples 1-3 have six supplied green signals. Example 4 has HRV red, RHR/sleep amber, TSB/ACWR/RI green (no persistent low RI), with the supplied Modify decision. All dates, metrics, source assignments and weather values below are fictional, independent of the approved live-data layout references.

Assume permitted geocoding and weather fetches succeeded where a home forecast is shown. The athlete timezone is Europe/Copenhagen. Weather times omit its zone label; Data updated keeps the local timestamp and zone. Link [Open-Meteo](https://open-meteo.com/) and [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) in the one final attribution line. GeoNames credit remains in API documentation and other geocoding displays; report places are labelled with the athlete's source. Missing values stay unavailable.

## Assumed departure clarification (fictional route-weather excerpt)

```text
**Today: Fictional mountain ride**
Outdoor ride
Distance: 96.5 km
Ascent: 1,657 m
Terrain: hilly

Climbs
4.0 km: 0.8 km at 3.2% (max 5.4%)

Pacing: keep the early climb controlled.

**Weather on the route**
Start: 10:00 (assumed)
No start time set. When are you leaving?

Moving time: 3h20m–6h50m
Total time: 3h20m–8h30m
Wind: W 4.0–9.0 m/s
Gusts: up to 12.0 m/s
Strongest gusts at: 24–42 km
Headwind: first 42 km and last 18.5 km
Rain: 0.6 mm/h, 65% wettest 13:00–14:00
Temperature: 9.0–16.0 °C
Feels like: 7.0–14.0 °C

Prepare: bring a rain layer

ETA: generic, default stops
History: no personal timing

Weather data by Open-Meteo, CC BY 4.0.
```

This fictional session excerpt omits the surrounding status/recommendation, not required fields in a full report. No duration or structure was supplied, so neither line appears. Its invented complete bands assign headwind to 0–24, 24–42 and 78–96.5 km (60.5 km), crosswind to 42–60 km (18 km) and tailwind to 60–78 km (18 km); only the 24–42 km band has the 12.0 m/s maximum gust. These support both location lines without copying the approved live reference's numbers. Rain coverage supports the stated wettest window, not an onset claim. Matching PNG pages are posted directly after the complete report text, only after being read.

Midnight is unset, so the default is assumed. Check binding and expiry before using the brief. A capable agent may preview the exact push.py time update, apply it only after confirmation and then re-read the next sync's brief. Missing/unreadable pages require the applicable `bands[].display` fallback, never raw-section aggregation. Preparation follows Environmental Conditions Protocol; readiness rules are unchanged.

If sync supplied `assumed_reason: "start_passed"` and a 10:30 departure after planned 10:00, use `Start: 10:30 (assumed)` then `Planned 10:00 has passed.`, then `When are you leaving?` on its own line and a blank line. Use the newly bound brief's weather/map, never retime it in the report. See the [passed-start example](WEATHER_REPORT_EXAMPLES.md#5-passed-start-not-completed). The same final attribution is required with or without a map.

---

## Example 1: Rest Day: No Sessions Scheduled

```
**Pre-workout: Sunday 18 January**
Data updated: 18 Jan 09:15 CET

**Go**
Signals: 6/6 green

Verdict: Readiness is good, with HRV above its average, RHR below baseline and solid sleep. Keep today's scheduled rest and review readiness before tomorrow's threshold session.

Rest day: no sessions scheduled.

**Next session (Monday)**
Threshold: 3×10m @260W
Planned TSS: 88

**Readiness**
RHR: 44 bpm (baseline: 46 bpm)
HRV: 58 ms (7d avg: 54 ms)
Sleep: 8h30m
Sleep Quality: 3/4

**Load**
TSB: +1.85
CTL: 72.40
ATL: 70.55
ACWR: 0.84 (optimal); start-of-day
Recovery Index: 0.93 (good)
Ramp Rate: -1.30
Load/Recovery: 5.8
**Capability (cycling, 7d)**
Durability: 2.14% avg(4)
Trend: stable
EF: 1.44 avg(4)
Trend: stable

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Last 7 days**
Hours: 14h12m
Activities: 11
TSS: 468
```

---

## Example 2: Endurance Day: Normal Readiness

```
**Pre-workout: Monday 19 January**
Data updated: 19 Jan 08:45 CET

**Go**
Signals: 6/6 green

Verdict: HRV and RHR are near baseline, with 7h48m sleep and balanced load. Proceed as planned, keeping the ride steady and dressing for the cold.

**Today: Ski erg**
Indoor Ski erg
Duration: 10m
Main set: Zone 2

**Today: Endurance**
Outdoor ride
Duration: 2h00m
Planned TSS: 71
Main set
15m @153W
1h30m @162W
15m @150W

**Weather at home**
Place: Klampenborg (from Intervals.icu)
Time: 10:00–12:00
Temperature: 2.0 °C
Feels like: unavailable
Wind: S 5.1 m/s
Gusts: unavailable
Rain: unavailable

Prepare: warm layers and gloves.

**Readiness**
RHR: 46 bpm (baseline: 46 bpm)
HRV: 53 ms (7d avg: 54 ms)
Sleep: 7h48m
Sleep Quality: 3/4

**Load**
TSB: -3.20
CTL: 73.50
ATL: 76.70
ACWR: 1.04 (optimal); start-of-day
Recovery Index: 0.88 (good)
Ramp Rate: 0.45
Load/Recovery: 6.0
**Capability (cycling, 7d)**
Durability: 1.85% avg(3)
Trend: stable
EF: 1.45 avg(3)
Trend: stable

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Last 7 days**
Hours: 15h18m
Activities: 12
TSS: 502

Weather data by Open-Meteo, CC BY 4.0.
```

---

## Example 3: Interval Day: Fresh and Ready

```
**Pre-workout: Wednesday 21 January**
Data updated: 21 Jan 09:30 CET

**Go**
Signals: 6/6 green

Verdict: HRV is above its average, RHR is below baseline and sleep was 8h54m. Proceed with the planned intervals using the supplied readiness decision.

**Today: VO2 MAX**
Indoor ride
Duration: 1h30m
Planned TSS: 84
Main set: 3×10×30s @320W / 15s rest

**Readiness**
RHR: 44 bpm (baseline: 46 bpm)
HRV: 61 ms (7d avg: 55 ms)
Sleep: 8h54m
Sleep Quality: 1/4

**Load**
TSB: +0.50
CTL: 74.20
ATL: 73.70
ACWR: 0.99 (optimal); start-of-day
Recovery Index: 0.91 (good)
Ramp Rate: 0.30
Load/Recovery: 5.9
**Capability (cycling, 7d)**
Durability: 2.40% avg(3)
Trend: improving
EF: 1.47 avg(3)
Trend: improving

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Last 7 days**
Hours: 16h6m
Activities: 13
TSS: 530
```

---

## Example 4: Compromised Readiness: Modify Recommended

```
**Pre-workout: Friday 23 January**
Data updated: 23 Jan 08:55 CET

**Modify**
Signals: 3 green, 2 amber, 1 red

Verdict: HRV is red, RHR and sleep are amber, and load/recovery is above tolerance. Replace threshold work with 1h30m easy endurance under the supplied Modify guidance, then reassess readiness before intensity.

**Today: Threshold**
Outdoor ride
Duration: 1h30m
Planned TSS: 90
Main set: 3×12min @260W

**Weather at home**
Place: Klampenborg (you said)
Time: 10:00–11:30
Temperature: 1.0 °C
Feels like: unavailable
Wind: E 2.1 m/s
Gusts: unavailable
Rain: unavailable

Prepare: warm layers and gloves.

**Readiness**
RHR: 50 bpm (baseline: 46 bpm)
HRV: 42 ms (7d avg: 54 ms)
Sleep: 5h12m
Sleep Quality: 4/4

**Load**
TSB: -12.80
CTL: 74.90
ATL: 87.70
ACWR: 1.17 (optimal); start-of-day
Recovery Index: 0.68 (moderate)
Ramp Rate: 1.10
Load/Recovery: 7.1 (tolerance 6.4)
**Capability (cycling, 7d)**
Durability: 5.80% avg(3)
Trend: declining ⚠️
EF: 1.38 avg(3)
Trend: declining ⚠️
Monotony: 2.5 (elevated)

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Pyramidal
Drift: shifting

**Last 7 days**
Hours: 18h24m
Activities: 14
TSS: 612

Weather data by Open-Meteo, CC BY 4.0.
```

## Synthetic multi-main-sport intensity excerpt

A triathlon period with 60/28/12% eligible TSS selects cycling, running and swimming independently of zone availability. Cycling has two power sessions and running three five-band HR sessions in the rolling week; two swims have pace only. No other status or readiness rule changes.

~~~text
**Intensity (cycling, power, 1/1 week, 2/2 rides)**
Z1+Z2: 80%
Z3: 15%
Z4+: 5%
TID: Pyramidal

**Intensity (running, HR, 1/1 week, 3/3 runs)**
Z1+Z2: 75%
Z3: 15%
Z4+: 10%
TID: Pyramidal

**Intensity (swimming, 1 active week)**
Coverage: 0/2 swims with zones
Zones: unavailable
Pace mapping: deferred
~~~

Observed-session distributions are not proof of complete activity retrieval. A missing new block yields unavailable intensity rather than an all-sports fallback.

---

## Sleep context excerpts (fictional)

These optional lines belong within the existing readiness status group, not replacement reports. All values and dates are invented. The reference is 8h across 28/28 dates, 12 May–8 June 2026; the recent review is 9–15 June. Each of the latest three nights has 27600 raw seconds (7h40m), giving exactly 3600 seconds combined difference. All three are above seven hours and still meet the context rule. No extra readiness signal or automatic recommendation change follows.

```text
**Sleep context (low confidence)**
Below reference: 3 consecutive nights
13 Jun: 7h40m
14 Jun: 7h40m
15 Jun: 7h40m
Reference: 8h (28/28 nights)
Recent: 7/7 nights
```

With 12 June missing and the other six recent dates observed, the same latest three qualify. Do not give a full-week mean or imply a known episode start across the gap:

```text
**Sleep context (low confidence)**
Below reference: 3 observed nights
13 Jun: 7h40m
14 Jun: 7h40m
15 Jun: 7h40m
Reference: 8h (28/28 nights)
Recent: partial 6/7 nights
Missing: 12 Jun
```

When a pattern is requested but 14 June is missing, the latest three are incomplete:

```text
**Sleep context (low confidence)**
Repeat comparison: unavailable
Missing: 14 Jun
Recent: 6/7 nights
Reference: 8h (28/28 nights)
```

With an absent or stale block, say the requested context is unavailable and name that cause. With false/null and no relevant request or athlete report, omit the line. A full-window run reads “at least 7”, never an exact episode length.

Explicit athlete reports of fragmentation on 13 and 15 June remain separate even with above-reference measured durations:

```text
**Sleep context (low confidence)**
Fragmentation: athlete-reported
Dates: 13 Jun and 15 Jun

Watch: Measured duration cannot establish awakenings.
```

“Recently” without dates does not become two nights. Repeated messages about one date count once; no statement is unknown, and a denial or correction applies only to its stated dates. Keep day disruption and current fatigue separate without double-counting. For a later same-day session, put relevant context within Current state or Decision of the continuation block and retain its current-state and start-of-day ACWR rules.

## Example 5: Outdoor run and walk (session excerpt)

The fictional run has no supplied duration, TSS or structure; those lines are omitted. Profile location is null/empty and the current official dossier supplies Klampenborg. A permitted point forecast covers the known planned hour. The following walk is explicitly indoor and gets no weather. This excerpt omits the surrounding status and recommendation.

```text
**Today: Easy run**
Outdoor run

**Weather at home**
Place: Klampenborg (from dossier)
Time: 10:00–11:00
Temperature: -2.0 °C
Feels like: unavailable
Wind: N 3.8 m/s
Gusts: unavailable
Rain: unavailable

Prepare: warm layers and gloves.

**Today: Evening walk**
Indoor walk
Duration: 20m

Weather data by Open-Meteo, CC BY 4.0.
```

## Example 6: Dry outdoor walk (session excerpt)

Synthetic scenario: the current-chat home location is Lund, the permitted point forecast is fresh, and the planned walk window is 14:10–14:50. Its amount and probability are both zero, so dry is supported. Place/source/window context stays in the Home heading; the single weather line is a home forecast, not a route forecast. Link the final provider/licence attribution when rendering, as above.

```text
**Today: Canal walk**
Outdoor walk
Start: 14:10
Duration: 40m

**Home (Lund, you said, 14:10–14:50)**
Weather: dry, 13.0 °C, W 3.0 m/s

Weather data by Open-Meteo, CC BY 4.0.
```

## Example 7: Rainy hike with an attached route (session excerpt)

Synthetic scenario: a planned 08:20–10:20 hike has a GPX attachment. The supplied route-weather status is unavailable because the type is not outdoor cycling. The same current-chat Lund home source and a fresh, permitted point forecast for that planned window supply the short weather lines. These values describe home, never conditions along the hiking route; no route map is shown. Missing source/fetch evidence would stay unavailable.

```text
**Today: Woodland hike**
Outdoor hike
Start: 08:20
Duration: 2h

**Home (Lund, you said, 08:20–10:20)**
Weather: 0.6 mm/h 55%, 8.0 °C
Wind: NW 3.5 m/s, gusts 6.5 m/s
Route forecast: rides only

Weather data by Open-Meteo, CC BY 4.0.
```
