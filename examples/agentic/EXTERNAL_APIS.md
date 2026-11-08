# External API Reference

**Version:** 1.0  
**Purpose:** Operational setup and endpoint reference for external APIs used by the agentic platform. Planned-route forecasts come from sync.py: agents read the matching brief and maps, discovered through `latest.json.data_overview`. Call weather providers directly only for locations or times sync does not cover (no route, beyond 120 h, or an ad-hoc place). Section 11 protocol defines how to reason about the data; this document retains the endpoint details for those uses.

---

## 1. Strava

Strava provides segment data, athlete effort history, and starred segments. The agentic platform calls these endpoints during pre-ride planning to enrich route intelligence with segment opportunities.

### Authentication

Strava API uses OAuth 2.0.

1. Register an app at `strava.com/settings/api`
2. Set Authorization Callback Domain (can be `localhost` for personal use)
3. Authorize via browser:
   ```
   https://www.strava.com/oauth/authorize
     ?client_id={CLIENT_ID}
     &response_type=code
     &redirect_uri={REDIRECT_URI}
     &scope=read,read_all,activity:read_all
     &approval_prompt=force
   ```
4. Exchange the authorization code for access + refresh tokens:
   ```
   POST https://www.strava.com/oauth/token
     client_id={CLIENT_ID}
     &client_secret={CLIENT_SECRET}
     &code={AUTHORIZATION_CODE}
     &grant_type=authorization_code
   ```
5. Store the refresh token. Access tokens expire every 6 hours. Refresh before they expire:
   ```
   POST https://www.strava.com/oauth/token
     client_id={CLIENT_ID}
     &client_secret={CLIENT_SECRET}
     &refresh_token={REFRESH_TOKEN}
     &grant_type=refresh_token
   ```
   Returns a new access token and may return a new refresh token. Always store the latest refresh token.

### Rate Limits

200 requests per 15 minutes, 2,000 per day. Pre-ride planning uses 10–30 calls at most.

### Key Endpoints

| Endpoint | Purpose | Returns |
|---|---|---|
| `GET /segments/explore?bounds={sw_lat},{sw_lng},{ne_lat},{ne_lng}&activity_type=riding` | Find segments in bounding boxes along the route | Segment ID, name, distance, average grade, elevation difference, start/end coordinates, climb category |
| `GET /segments/{id}` | Full segment detail | Polyline, total elevation gain, effort count, athlete count, star count. Use polyline to confirm segment lies on the route |
| `GET /athlete/segments/starred` | Athlete's starred segments (automatic priority targets) | All starred segments. Cross-reference with route to find today's priorities |
| `GET /segment_efforts?segment_id={id}` | Athlete's effort history on a segment | Times, dates, average power (if available). PR context |

Base URL: `https://www.strava.com/api/v3`

### Route Segment Discovery

Walk bounding boxes along the GPX track (e.g., 2 km wide boxes every 5 km of route) using `/segments/explore`. Deduplicate results. Filter by proximity to the GPS track (within 100m of any trackpoint); not all results will be exactly on the route.

### Segment Data Compilation

For each segment on the route, compile for the coaching layer:

- **ID and name**
- **Distance** (km) and **elevation gain** (m)
- **Average gradient** (%)
- **Bearing**: direction of the segment (degrees), calculated from start to end coordinates. Critical for wind comparison (see Section 11 Wind Overlay)
- **Position in ride** (km from start): fatigue context
- **Athlete's PR**: best time, date, average power if available
- **Expected duration**: estimate from distance and gradient, refined by the athlete's power curve
- **Priority**: starred on Strava or explicitly chosen by the athlete

---

## 2. yr.no (MET Norway)

The Norwegian Meteorological Institute provides global forecasts. For sync.py's default-on route weather this is the explicitly labelled fallback to Open-Meteo, used only when no fresh primary point forecast is available. Agents read that brief and its maps; direct MET calls are only for no-route, beyond-120-hour or ad-hoc location forecasts outside sync coverage. See README for off switches/privacy and SECTION_11 Weather Data Source for lead-time tiers and request limits.

### Authentication

No API key required. Requires a `User-Agent` header identifying the application (e.g., `Section11/1.0 github.com/CrankAddict/section-11`). MET Norway terms of service require identification and encourage caching to reduce server load.

### Endpoint

```
GET https://api.met.no/weatherapi/locationforecast/2.0/complete
  ?lat={latitude}
  &lon={longitude}
```

Returns GeoJSON with `properties.meta` and `properties.timeseries`. The `complete` endpoint can include `probability_of_precipitation`; availability, gusts and hourly periods vary by region and horizon. Missing fields stay unknown. sync.py also sends integer `altitude` and coordinates rounded to four decimals.

### Key Fields

From the `timeseries` array, each entry contains `data.instant.details`:

- **wind_from_direction**: degrees, meteorological convention (direction wind comes FROM, 0° = north, 90° = east). Feeds directly into Section 11 Wind Overlay headwind/tailwind calculation
- **wind_speed**: m/s
- **wind_speed_of_gust**: m/s
- **air_temperature**: °C. Cross-reference with Section 11 Environmental Conditions Protocol for heat stress tier
- **relative_humidity**: %

From `data.next_1_hours`:

- **details.precipitation_amount**: mm
- **details.probability_of_precipitation**: % (only available on the `complete` endpoint)
- **summary.symbol_code**: weather descriptor (e.g., `rain`, `cloudy`, `partlycloudy_day`), not a probability

### Usage Notes

- Fetch for the ride area at the planned ride time. For long routes, consider fetching for multiple points along the course
- Cache responses; MET Norway returns `Expires` and `Last-Modified` headers. Do not re-fetch until the cached response expires
- Retain a validated `Last-Modified` value for `If-Modified-Since`; 304 reuses cached content. sync.py accepts at most two redirect hops on the same HTTPS host within Locationforecast 2.0, each counted in its eight-request budget
- For MET-only fallback, end report text with "Weather data by [MET Norway](https://api.met.no/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)." If separate blocks use both providers, name and link both on the same final line, with the licence once. No transformation note in report text; PNG footers remain unchanged

---

## 3. Open-Meteo

Open-Meteo is the primary provider for sync.py's default-on route weather. Agents read the matching brief and maps instead of fetching again; direct calls are only for no-route, beyond-120-hour or ad-hoc location forecasts outside sync coverage. It selects available models for the location; `best_match` identifies that selection, not a known underlying model run. MET Norway is a labelled fallback. Provider choice is not a claim that one forecast is always more accurate.

### Authentication

No API key required. Free for non-commercial use, with a limit of 10,000 API calls per day. See [open-meteo.com/en/terms](https://open-meteo.com/en/terms) for full terms. For commercial use, see [open-meteo.com/en/pricing](https://open-meteo.com/en/pricing).

### Endpoint

```
GET https://api.open-meteo.com/v1/forecast
  ?latitude={lat}
  &longitude={lon}
  &elevation={metres}
  &hourly=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation_probability,precipitation
  &timezone=GMT&timeformat=unixtime
  &start_hour={YYYY-MM-DDTHH:00}&end_hour={YYYY-MM-DDTHH:00}
  &wind_speed_unit=ms&temperature_unit=celsius&precipitation_unit=mm
```

sync.py requests only each event's required UTC hours, from departure rounded down to the hour through the ETA upper bound rounded up. Outlooks first round outward to their six-hour envelope. These inclusive endpoints supply the surrounding instants and preceding-hour precipitation periods; `forecast_days=8` is no longer sent. Comma-separated latitude/longitude/elevation lists initially batch the route in one call. Multiple locations return a list of hourly forecast objects. A timeout can split the batch into halves, recursively if needed, within the unchanged eight-call cap and 20-second admission cutoff. HTTP rejections and malformed data are not split. MET retains its existing endpoint and parameters.

All forecast GETs use `stream=True`, a 2-second connect timeout and a 5-second read timeout. A 25-second route-weather pass deadline is checked after headers, between byte-sized decoded chunks and after the body; timed-out responses are closed. This limits slow trickles without a signal, subprocess or platform exclusion, but is not preemptive during DNS, a blocked read or decompression. Use the existing `--lockfile` for automated timers. Responses are capped at 2 MiB decoded. Cache/brief diagnostics retain timeout, connection, HTTP status, invalid-response and backoff causes without raw exception text or request URLs.

It validates coordinate association, time arrays and explicit units; unknown extra fields are ignored. Covering cached time windows are reusable; disjoint windows at the same location remain separate. Beyond 72 hours, output is a trend outlook with no section predictions. MET outlooks retain native six/twelve-hour periods when hourly data is absent; never interpret those amounts as hourly rain.

### Key Fields

From the `hourly` array:

- **wind_direction_10m**: degrees, meteorological convention (direction wind comes FROM, 0° = north, 90° = east). Feeds directly into Section 11 Wind Overlay headwind/tailwind calculation
- **wind_speed_10m**: m/s
- **wind_gusts_10m**: m/s
- **temperature_2m**: °C. Cross-reference with Section 11 Environmental Conditions Protocol for heat stress tier
- **precipitation_probability**: %
- **precipitation**: mm
- **apparent_temperature**: °C, optional feels-like

### Usage Notes

- No `User-Agent` header required, but caching responses is recommended
- `precipitation_probability` is provided directly as a percentage: no need to derive it from symbol codes
- Combines multiple weather models; the default selection is the best available for the queried location
- Amount/probability and maximum gust apply to the preceding hour; temperature and mean wind are instantaneous. Do not sum precipitation across repeated route samples
- End report text with "Weather data by [Open-Meteo](https://open-meteo.com/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)." Use one line for route and home weather, whether or not maps are shown, without a transformation note. PNG footers remain unchanged. The free endpoint is non-commercial; sync.py does not implement a paid endpoint

### Geocoding for point weather

Resolve city-level text to coordinates before fetching a point forecast. First select the location using [Point-weather location](../../SECTION_11.md#point-weather-location): explicit current-chat statement, then `athlete_profile.location` in current `latest.json`, then the current official dossier's Home region only when the profile location is null/empty. A session's route data still takes precedence. This lookup is for the consuming AI with actual, permitted fetch capability; sync.py does not geocode home locations.

The [official Geocoding API documentation](https://open-meteo.com/en/docs/geocoding-api) describes this GET endpoint:

```text
https://geocoding-api.open-meteo.com/v1/search?name=Aalborg&count=10&language=en&countryCode=DK&format=json
```

| Parameter | Use |
|---|---|
| `name` | Required city/place name or postal code. URL-encode it. A single comma followed by country or first-level administrative area narrows the search, for example `Aalborg, North Denmark`. |
| `countryCode` | Optional ISO-3166-1 alpha-2 filter, such as `DK`. Use it when the selected source supplies an unambiguous country; do not carry a home country into a different current-chat travel location. |
| `count` | Default 10, maximum 100. Country/admin filters are applied before this result limit. |
| `language` | Lower-case language code, default `en`; returned names may be translated. |
| `format` | Default `json`; use JSON here. |

The response's `results[]` entries supply `name`, `latitude`, `longitude`, `country_code`, `admin1`, `population` and `timezone` when available; empty fields are omitted. Check the returned country/region against the selected source before using its coordinates.

The profile location may contain city, region and country. Separate those supplied parts: use the city and optional region in `name`, and the country in `countryCode`. Do not blindly pass a three-part string: only the text between the first and second comma is treated as the qualifier. The qualifier must match exactly; country-code filtering avoids ambiguous country/admin abbreviations. Two-character place queries use exact matching; three or more use normalized prefix matching, so multiple results are normal.

**Deterministic selection:** Filter by `countryCode` when the selected source has a country, and reject candidates that contradict a supplied region. Prefer an exact name match (case- and diacritic-insensitive) over prefix matches. Among remaining candidates, select the sole match, or the uniquely highest population when every remaining candidate has a comparable population. If there is a tie, missing population prevents comparison, the result limit could hide an equally eligible match, or no candidate matches the supplied constraints, report the location as ambiguous/unavailable and ask for clarification. Never choose the first result merely because it is first, invent coordinates or silently try a lower-priority location. Empty results, malformed responses and failed requests also mean unavailable with the actual reason.

The supplied Aalborg example illustrates the distinction: the search returns `Aalborg`, `Aalborg SØ` and `Aalborg SV`. With country `DK` and exact name `Aalborg`, select the city at latitude `57.048`, longitude `9.9187` (population `142937`, admin1 `North Denmark`, timezone `Europe/Copenhagen`), not either district. These are documentation example coordinates, never a default athlete location. Use the selected result's `latitude` and `longitude` in the forecast request; keep the athlete-location source label, for example `(from Intervals.icu)`, distinct from geocoding attribution.

The free endpoint is for non-commercial use under Open-Meteo's [terms](https://open-meteo.com/en/terms); commercial reserved resources require the customer endpoint/API key described in the documentation and [pricing](https://open-meteo.com/en/pricing). This guidance does not configure a subscription or grant network access. Geocoding attribution remains **Location data based on [GeoNames](https://www.geonames.org/)** in this documentation and other geocoding displays. Pre-workout and weather reports omit a separate GeoNames line; their Place line names the athlete's location source and their final line credits weather data. Do not add flag attribution unless flags are actually used.

---

## 4. Intervals.icu Activity Streams

Intervals.icu exposes per-second sensor data ("streams") and pre-computed weather summaries for completed activities. sync.py reads these to populate `terrain_summary` and `weather_summary` on each outdoor activity in `latest.json`. AIs and humans can fetch the raw streams directly via `pull.py` for deeper analysis (e.g. "where on the ride was the headwind worst?", "what was the gradient at km 18?").

### Authentication

HTTP Basic auth with username `API_KEY` (literal string) and password = the athlete's Intervals API key. Same credentials as sync.py. See the project README for setup. The shared `.sync_config` file is read by sync.py, push.py, and pull.py.

### Streams Endpoint

```
GET https://intervals.icu/api/v1/activity/{activity_id}/streams.json
GET https://intervals.icu/api/v1/activity/{activity_id}/streams.json?types=latlng,altitude
```

Returns a JSON list of stream objects. Each object:

```json
{
  "type":   "latlng",
  "name":   null,
  "data":   [57.012573, 57.012566, ...],
  "data2":  [9.970168, 9.970170, ...],
  "valueType": "java.lang.Float",
  ...
}
```

**Important shape gotcha: `latlng` uses dual parallel arrays.**

- `data` holds latitudes
- `data2` holds longitudes
- Indices are aligned: point N is `(data[N], data2[N])`
- This is NOT the Strava convention (which uses paired `[lat, lng]` entries inside `data`). A naive parser that reads only `data` will silently produce a list of latitudes with no longitudes.

GPS dropouts (tunnels, bad sky view, brief signal loss) appear as `None` entries at matching indices in both `data` and `data2`. Altitude is independent of GPS (barometric on most Garmin devices) and may have fewer Nones than latlng.

### Available Stream Types

Verified from a real outdoor cycling activity. Specific streams may vary by activity (sport, device, recording fields installed):

| Type | Notes |
|------|-------|
| `time` | Seconds from start (1Hz) |
| `distance` | Cumulative meters |
| `latlng` | Dual array (see gotcha above) |
| `altitude` | Meters, smoothed barometric |
| `velocity_smooth` | m/s |
| `watts` | Power, when paired with a meter |
| `heartrate` | bpm |
| `cadence` | rpm/spm |
| `temp` | Device sensor (often higher than ambient in sun) |
| `dfa_a1` | Per-second DFA a1, only when AlphaHRV Connect IQ field recorded |
| `artifacts` | Artifact percentage paired with dfa_a1 |
| `respiration` | Breaths/min (some devices) |
| `torque`, `left_pedal_smoothness`, `left_torque_effectiveness` | Power-meter dependent |

**Pro/supporter accounts also see** (computed from Open-Meteo, outdoor activities post-April 2021): `wind_speed`, `wind_direction`, `gusts`, `Bearing` (athlete's direction of travel), `A Wind` (apparent wind), `yaw_angle`.

### Original File Endpoint (alternative, full fidelity)

```
GET https://intervals.icu/api/v1/activity/{activity_id}/file
```

Returns the original uploaded activity file (FIT, TCX, or GPX), gzipped. Full device fidelity (no resampling). Useful if the streams downsampling is ever a concern. Section 11 sync.py uses streams; this endpoint is documented for completeness.

### Weather Fields on the Activity List Endpoint

For Pro/supporter accounts, weather data is pre-computed and attached to each outdoor activity record on the standard list endpoint:

```
GET https://intervals.icu/api/v1/athlete/0/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
```

No extra streams call needed. These fields appear directly on each activity in the response. sync.py reads them to populate `weather_summary` in latest.json.

| Field | Meaning |
|-------|---------|
| `has_weather` | bool: whether weather has been computed for this activity (re-evaluated each sync; may flip false→true if Intervals catches up later) |
| `average_wind_speed` | In account's wind unit (see units endpoint) |
| `average_wind_gust` | Same unit as wind_speed |
| `prevailing_wind_deg` | 0-359, meteorological convention (direction wind comes FROM) |
| `headwind_percent` | % of moving time with relative headwind |
| `tailwind_percent` | % of moving time with relative tailwind |
| `average_weather_temp` | Ambient air temp from Open-Meteo (°C or °F per account) |
| `average_temp` | Device sensor temp (typically higher in direct sun) |
| `average_feels_like`, `min_feels_like`, `max_feels_like` | Apparent temp |
| `min_weather_temp`, `max_weather_temp` | Ambient range over the ride |
| `average_clouds` | % cloud cover |
| `max_rain`, `max_snow` | Precipitation in account's rain unit (mm or in) |

### Athlete Settings Endpoint (unit preferences)

```
GET https://intervals.icu/api/v1/athlete/0
```

Returns an object with the athlete's unit preferences. Relevant fields:

| Field | Values |
|-------|--------|
| `wind_speed` | `"MPS"` / `"KPH"` / `"MPH"` |
| `fahrenheit` | `true` / `false` (false = Celsius) |
| `rain` | `"MM"` / `"IN"` |
| `measurement_preference` | `"meters"` (metric) / other (imperial) |
| `weight_pref_lb` | `true` / `false` |
| `height_units` | `"CM"` / `"IN"` |

sync.py reads these once per run and populates the `units` block on `weather_summary` so coach can resolve the actual unit of each value (e.g. `weather_summary.units.wind = "m/s"`). Field names themselves are stable (`avg_wind_speed`, not `avg_wind_speed_mps`).

### Quick CLI Reference (pull.py)

Run from the data folder with the managed tool. Local installation removes the old root copy.

```bash
# Full streams for an activity (writes to stdout or a file)
python3 section11/examples/agentic/pull.py trace --activity-id i142557875

# Just GPS + altitude
python3 section11/examples/agentic/pull.py trace --activity-id i142557875 --types latlng,altitude

# Save to disk for further analysis
python3 section11/examples/agentic/pull.py trace --activity-id i142557875 --out /tmp/ride.json

# Show the athlete's unit preferences
python3 section11/examples/agentic/pull.py units
```

### Caveats

- **Strava-sourced activities don't fire Intervals webhooks.** sync.py polling discovers them anyway; only matters if you ever build webhook-triggered processing.
- **Weather is a Pro/supporter feature.** If the subscription lapses, `has_weather` may stop populating on new activities. Existing summaries already in `latest.json` are unaffected.
- **`has_weather` is re-evaluated every sync.** sync.py never copies forward `weather_status: "unavailable"` from the previous latest.json, because Intervals sometimes computes weather data minutes-to-hours after upload. Letting it re-check ensures a delayed weather computation gets picked up on the next sync.
- **Pre-April-2021 activities have no weather data**: outside Open-Meteo coverage on Intervals' side. Outside any reasonable display window for sync.py anyway.

