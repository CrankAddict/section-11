# External API Reference

**Version:** 1.0  
**Purpose:** Operational setup and endpoint reference for external APIs used by the agentic platform. Section 11 protocol defines the reasoning rules for what to do with this data — this document covers how to get it.

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
5. Store the refresh token — access tokens expire every 6 hours. Refresh before they expire:
   ```
   POST https://www.strava.com/oauth/token
     client_id={CLIENT_ID}
     &client_secret={CLIENT_SECRET}
     &refresh_token={REFRESH_TOKEN}
     &grant_type=refresh_token
   ```
   Returns a new access token and may return a new refresh token — always store the latest refresh token.

### Rate Limits

200 requests per 15 minutes, 2,000 per day. Pre-ride planning uses 10–30 calls at most.

### Key Endpoints

| Endpoint | Purpose | Returns |
|---|---|---|
| `GET /segments/explore?bounds={sw_lat},{sw_lng},{ne_lat},{ne_lng}&activity_type=riding` | Find segments in bounding boxes along the route | Segment ID, name, distance, average grade, elevation difference, start/end coordinates, climb category |
| `GET /segments/{id}` | Full segment detail | Polyline, total elevation gain, effort count, athlete count, star count. Use polyline to confirm segment lies on the route |
| `GET /athlete/segments/starred` | Athlete's starred segments — automatic priority targets | All starred segments. Cross-reference with route to find today's priorities |
| `GET /segment_efforts?segment_id={id}` | Athlete's effort history on a segment | Times, dates, average power (if available). PR context |

Base URL: `https://www.strava.com/api/v3`

### Route Segment Discovery

Walk bounding boxes along the GPX track (e.g., 2 km wide boxes every 5 km of route) using `/segments/explore`. Deduplicate results. Filter by proximity to the GPS track (within 100m of any trackpoint) — not all results will be exactly on the route.

### Segment Data Compilation

For each segment on the route, compile for the coaching layer:

- **ID and name**
- **Distance** (km) and **elevation gain** (m)
- **Average gradient** (%)
- **Bearing** — direction of the segment (degrees), calculated from start to end coordinates. Critical for wind comparison (see Section 11 Wind Overlay)
- **Position in ride** (km from start) — fatigue context
- **Athlete's PR** — best time, date, average power if available
- **Expected duration** — estimate from distance and gradient, refined by the athlete's power curve
- **Priority** — starred on Strava or explicitly chosen by the athlete

---

## 2. yr.no (MET Norway)

The Norwegian Meteorological Institute provides free, high-quality weather forecasts with global coverage. Primary source for wind direction, speed, temperature, and precipitation in pre-ride weather assessment.

### Authentication

No API key required. Requires a `User-Agent` header identifying the application (e.g., `Section11/1.0 github.com/CrankAddict/section-11`). MET Norway terms of service require identification and encourage caching to reduce server load.

### Endpoint

```
GET https://api.met.no/weatherapi/locationforecast/2.0/compact
  ?lat={latitude}
  &lon={longitude}
```

Returns JSON forecast for the next ~9 days at the specified coordinates.

### Key Fields

From the `timeseries` array, each entry contains `data.instant.details`:

- **wind_from_direction** — degrees, meteorological convention (direction wind comes FROM, 0° = north, 90° = east). Feeds directly into Section 11 Wind Overlay headwind/tailwind calculation
- **wind_speed** — m/s
- **wind_speed_of_gust** — m/s
- **air_temperature** — °C. Cross-reference with Section 11 Environmental Conditions Protocol for heat stress tier
- **relative_humidity** — %

Precipitation probability is in `data.next_1_hours.summary.symbol_code` and `data.next_1_hours.details.precipitation_amount`.

### Usage Notes

- Fetch for the ride area at the planned ride time. For long routes, consider fetching for multiple points along the course
- Cache responses — MET Norway returns `Expires` and `Last-Modified` headers. Do not re-fetch until the cached response expires
- Creative Commons 4.0 BY license — attribution required: "Data from MET Norway"
