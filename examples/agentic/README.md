# Agentic Tools

Read and write tools for AI platforms that can execute code or trigger GitHub Actions (OpenClaw, Claude Code, Cowork, ChatGPT Codex, etc.). Chat-only users cannot use these.

| Tool | Purpose |
|------|---------|
| `push.py` | **Write** to Intervals.icu — manage planned workouts (push, list, move, delete), update sport-specific thresholds, annotate activities |
| `pull.py` | **Read** raw Intervals.icu data on demand — per-second activity streams (latlng, altitude, watts, HR, …) and athlete unit preferences. Used when `terrain_summary`/`weather_summary` in `latest.json` aren't enough and the AI needs the underlying GPS/sensor track |
| `EXTERNAL_APIS.md` | Endpoint reference for the external APIs used by the agentic platform: Strava, MET Norway (yr.no), Open-Meteo, Intervals.icu streams + weather |

`push.py` requires safety preview/confirm. `pull.py` is read-only and has no confirm gate.

---

## push.py — Workouts & Thresholds

Write, read, move, delete, and annotate planned workouts on an athlete's Intervals.icu calendar. Update sport-specific thresholds.

### Safety: Preview by Default

All write operations (push, move, delete, set-threshold, annotate) default to **preview mode**. Nothing is written unless you add `--confirm`.

**Agent rule:** Always run without `--confirm` first. Show the preview to the athlete. Add `--confirm` only after the athlete approves.

```bash
# Step 1: Agent runs preview
python push.py push --json week.json
# → Returns preview JSON showing what WOULD be pushed

# Step 2: Agent shows athlete the summary

# Step 3: Athlete says "looks good" / "go" / "yes" / etc.

# Step 4: Agent runs with --confirm
python push.py push --json week.json --confirm
# → Actually writes to calendar
```

Read operations (`list`) have no safety gate — they never modify anything.

**Scope:** All write operations (push, move, delete) operate on planned events only — future calendar items. Completed activities and training history cannot be modified or deleted through push.py.

### Setup

#### Path 1: GitHub Actions dispatch (recommended)

For anyone already running auto-sync. Uses the same `ATHLETE_ID` and `INTERVALS_KEY` secrets — zero new credential setup.

1. Copy `push.py` to your data repo root (next to `sync.py`)
2. Copy `push-workout.yml` to `.github/workflows/push-workout.yml`
3. Done. Your agent triggers the workflow via GitHub API dispatch.

**How the agent triggers it (Python):**

```python
import requests, json

workouts = [
    {
        "name": "Sweet Spot 3x15",
        "date": "2026-03-10",
        "type": "Ride",
        "description": "- 15m 55%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%",
        "duration_minutes": 85,
        "tss": 75,
        "target": "POWER"
    }
]

requests.post(
    f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/push-workout.yml/dispatches",
    headers={
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    },
    json={
        "ref": "main",
        "inputs": {
            "command": "push",
            "workouts": json.dumps(workouts),
            "confirm": "true"
        }
    }
)
```

The agent needs a `GITHUB_TOKEN` with `actions:write` scope on the data repo.

#### Path 2: Local execution (Claude Code, Cowork, ChatGPT Codex App, json-manual users)

For agents running locally with direct filesystem access.

`push.py` depends on `requests`. Install it into the same Python environment you use for `sync.py`: `pip install requests`.

```bash
# Single workout (preview)
python push.py push --name "Sweet Spot 3x15" --date 2026-03-10 --type Ride \
  --description "- 15m 55%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%" \
  --duration 85 --tss 75

# Batch from JSON file (execute)
python push.py push --json week.json --confirm
```

Credentials loaded from (first match wins):
1. CLI args: `--athlete-id`, `--api-key`
2. `.sync_config.json` in working directory (same file sync.py uses)
3. Environment: `ATHLETE_ID`, `INTERVALS_KEY`

`ATHLETE_ID` must include the leading `i` — e.g. `i113739`, not `113739`. `INTERVALS_KEY` is the raw API key string from Intervals.icu → Settings → Developer.

```bash
# CLI flags
python push.py list --athlete-id i123456 --api-key abc123...

# Env vars
export ATHLETE_ID=i123456
export INTERVALS_KEY=abc123...
python push.py list

# .sync_config.json (next to push.py)
# {"athlete_id": "i123456", "intervals_key": "abc123..."}
python push.py list
```

To keep your local JSON data fresh automatically (so push.py and your agent always have current data), see [json-local-sync](../json-local-sync/SETUP.md).

Python import also works:

```python
from push import IntervalsPush
pusher = IntervalsPush(athlete_id, api_key)
result = pusher.push_workout({
    "name": "Sweet Spot 3x15",
    "date": "2026-03-10",
    "type": "Ride",
    "description": "- 15m 55%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%",
    "duration_minutes": 85,
    "tss": 75,
    "target": "POWER"
})
```

### Commands

#### push — Add workouts to calendar

```bash
python push.py push --json week.json                    # preview
python push.py push --json week.json --confirm           # execute
python push.py push --name "Endurance" --date 2026-03-10 --type Ride --confirm
```

Output (preview):
```json
{"success": true, "mode": "preview", "count": 2, "summary": [...], "message": "Preview only - add --confirm to write to calendar"}
```

Output (execute):
```json
{"success": true, "count": 2, "events": [{"id": 33375903, "name": "Sweet Spot 3x15", "date": "2026-03-10", "type": "Ride", "category": "WORKOUT"}]}
```

#### list — Show planned workouts

```bash
python push.py list                          # this week (today → +6 days)
python push.py list --newest +13             # next two weeks
python push.py list --oldest 2026-03-01 --newest 2026-03-31  # March
python push.py list --category RACE_A        # races only
```

Read-only — no `--confirm` needed. Supports `+N` syntax for relative dates.

#### move — Move a workout to a different date

```bash
python push.py move --event-id 33375903 --date 2026-03-06          # preview
python push.py move --event-id 33375903 --date 2026-03-06 --confirm # execute
```

Preview shows old date → new date.

#### delete — Remove a workout

```bash
python push.py delete --event-id 33375903              # preview (shows what would be deleted)
python push.py delete --event-id 33375903 --confirm    # execute
```

#### set-threshold — Update sport-specific thresholds

```bash
# Preview (shows current → new values)
python push.py set-threshold --sport cycling --ftp 295

# Execute after athlete confirms
python push.py set-threshold --sport cycling --ftp 295 --indoor-ftp 283 --confirm

# Other sports
python push.py set-threshold --sport run --lthr 172 --max-hr 192 --confirm
python push.py set-threshold --sport swim --threshold-pace 0.82 --confirm
```

Accepts sport families (`cycling`, `run`, `swim`, `walk`, `ski`, `rowing`) or Intervals.icu activity types (`Ride`, `Run`, `Swim`, etc.). Only sends fields you provide — omitted fields stay unchanged.

**Agent safety:** Only update thresholds after a validated test result (FTP test, LTHR test, max HR test). Never update from a single ride estimate or eFTP. Always preview first to show the athlete the old → new diff.

#### annotate — Add notes to activities or planned workouts

**Completed activities** — prepends `NOTE:` line to activity description (default):

```bash
python push.py annotate --activity-id i12345:abc123 --message "Cut short - knee pain" --confirm
```

To post to the activity's chat/messages panel instead, add `--chat`:

```bash
python push.py annotate --activity-id i12345:abc123 --message "Cut short - knee pain" --chat --confirm
```

**Planned workouts** — prepends a `NOTE:` line to the workout description:

```bash
python push.py annotate --event-id 33375903 --message "Focus on cadence >90rpm" --confirm
```

This shows up in Intervals.icu as:
```
NOTE: Focus on cadence >90rpm

- 15m 55%

3x
- 15m 88-92%
- 5m 55%

- 10m 50%
```

Provide `--activity-id` OR `--event-id`, not both.

### Workout Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Workout name |
| `date` | Yes | string | YYYY-MM-DD, must be today or future |
| `type` | No | string | Activity type (default: Ride) |
| `description` | No | string | Intervals.icu workout syntax (see below) |
| `duration_minutes` | No | number | Planned duration (max 720) |
| `tss` | No | number | Planned TSS (max 500) |
| `target` | No | string | POWER, HR, or PACE |
| `category` | No | string | WORKOUT (default), RACE_A, RACE_B, RACE_C, NOTE |
| `indoor` | No | boolean | Mark as indoor |
| `external_id` | No | string | For upsert deduplication |

**Valid activity types:** Ride, VirtualRide, MountainBikeRide, GravelRide, EBikeRide, Run, VirtualRun, TrailRun, Swim, NordicSki, VirtualSki, Rowing, WeightTraining, Walk, Hike, Workout, Other

### Intervals.icu Workout Syntax

The `description` field uses Intervals.icu's native workout builder syntax. When provided, Intervals.icu parses the description into structured workout steps server-side.

#### Targets

**Power:** `75%`, `220w`, `Z2`, `95-105%`, `MMP30s`, `MMP5m`
**HR:** `70% HR`, `95% LTHR`, `Z2 HR`
**Pace:** `60% Pace`, `Z2 Pace`, `5:00/km Pace`
**Cadence:** append `90rpm` to any step
**Ramps:** `ramp 50%-75%`
**Freeride:** step with no target (ERG off)

#### Duration

`5m` = 5 minutes, `30s` = 30 seconds, `1h2m30s` = 1 hour 2 min 30 sec

**CRITICAL:** `m` means **minutes**, not meters. For distance use `km`, `mi`, or `mtr` (e.g., `500mtr`, `2km`, `1mi`).

#### Structure

- Steps start with `-`
- Blank lines required around repeat blocks
- Text before duration becomes step cue
- Case-insensitive keywords
- Nested repeats NOT supported

#### Example

```
- 15m ramp 50%-75%

3x
- 15m 88-92%
- 5m 55%

- 10m 50%
```

### Template Mappings

Maps Section 11 Workout Reference template IDs to Intervals.icu description syntax. **Use these as inspiration and adapt to the athlete** — don't copy-paste templates without considering current fitness, goals, and constraints. **Always use %FTP ranges, not absolute watts** — Intervals.icu resolves % to the athlete's current FTP.

| Template ID | Name | Description Syntax |
|-------------|------|--------------------|
| AE-1 | Recovery Spin | `- 5m ramp 40%-50%\n- 30m 50-55%\n- 5m ramp 50%-40%` |
| AE-2 | Medium Endurance | `- 10m ramp 50%-65%\n- 90m 65-75%\n- 10m ramp 65%-50%` |
| AE-3 | Long Endurance | `- 15m ramp 50%-65%\n- 150m 65-75%\n- 15m ramp 65%-50%` |
| SS-1 | Sweet Spot 3x15 | `- 15m ramp 50%-75%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%` |
| SS-2 | Sweet Spot 2x20 | `- 15m ramp 50%-75%\n\n2x\n- 20m 88-92%\n- 5m 55%\n\n- 10m 50%` |
| SS-3 | Sweet Spot 2x30 | `- 15m ramp 50%-75%\n\n2x\n- 30m 88-92%\n- 5m 55%\n\n- 10m 50%` |
| TH-1 | Threshold 3x10 | `- 15m ramp 50%-75%\n\n3x\n- 10m 95-105%\n- 5m 55%\n\n- 10m 50%` |
| TH-2 | Threshold 2x15 | `- 15m ramp 50%-75%\n\n2x\n- 15m 95-105%\n- 5m 55%\n\n- 10m 50%` |
| TH-3 | Threshold 2x20 | `- 15m ramp 50%-75%\n\n2x\n- 20m 95-105%\n- 5m 55%\n\n- 10m 50%` |
| VO2-1 | VO2max 5x4 | `- 15m ramp 50%-75%\n\n5x\n- 4m 106-120%\n- 3m Z1\n\n- 10m 50%` |
| VO2-2 | VO2max 4x5 | `- 15m ramp 50%-75%\n\n4x\n- 5m 106-120%\n- 4m Z1\n\n- 10m 50%` |
| VO2-3 | VO2max 6x3 | `- 15m ramp 50%-75%\n\n6x\n- 3m 106-120%\n- 3m Z1\n\n- 10m 50%` |
| AN-1 | Anaerobic 8x30s | `- 15m ramp 50%-75%\n\n8x\n- 30s 150%\n- 4m30s Z1\n\n- 10m 50%` |
| AN-2 | Anaerobic 10x1m | `- 15m ramp 50%-75%\n\n10x\n- 1m 130-150%\n- 3m Z1\n\n- 10m 50%` |

### What NOT To Do

- **Don't use absolute watts** — use `%FTP` ranges so workouts stay correct if FTP changes
- **Don't use `m` for meters** — `m` means minutes. Use `km`, `mi`, or `mtr` for distance
- **Don't nest repeats** — Intervals.icu doesn't support it
- **Don't push past dates** — validation rejects them. Planned workouts are future events
- **Don't skip blank lines around repeat blocks** — parsing breaks without them
- **Don't update thresholds from estimates** — only from validated test results

### Troubleshooting

- **`403 Access denied`** — `ATHLETE_ID` is missing the leading `i` (e.g. `113739` instead of `i113739`), the API key is wrong, or the key doesn't belong to that athlete
- **Error saying `requests` is not installed** — push.py is running under a Python interpreter that doesn't have `requests` installed; run `pip install requests` in the same env as `sync.py`, or invoke that env's Python explicitly (same applies to `pull.py`)
- **Command appears to have done nothing** — preview is the default for all write operations. Add `--confirm` to actually write

---

## pull.py — Activity Stream Reads

Read-only fetcher for Intervals.icu activity streams and athlete unit preferences. Useful when the AI needs the raw GPS / per-second sensor track behind a `terrain_summary` (e.g. "where on the ride was the headwind worst?", "what was the gradient at km 18?") — `latest.json` only carries the precomputed summary.

No `--confirm` gate — `pull.py` never modifies anything on the Intervals.icu side.

### Setup

Same credential model as `push.py`:

1. CLI args: `--athlete-id`, `--api-key`
2. `.sync_config.json` (the same file `sync.py` and `push.py` use)
3. Environment: `ATHLETE_ID`, `INTERVALS_KEY`

No GitHub Actions workflow — `pull.py` is local-execution only. The streams responses can be ~1-3 MB per activity (1Hz over a multi-hour ride), which is fine to handle locally but unsuitable for committing back to a data repo.

### Commands

#### trace — Fetch per-second streams for an activity

```bash
# All available streams (1Hz: time, distance, latlng, altitude, watts, HR, cadence, …)
python pull.py trace --activity-id i142557875

# Just GPS + altitude — smaller payload, common subset for terrain analysis
python pull.py trace --activity-id i142557875 --types latlng,altitude

# Save to disk for downstream analysis (e.g. feeding into custom scripts)
python pull.py trace --activity-id i142557875 --out /tmp/ride.json
```

The streams response is a JSON list of stream objects. **Important shape gotcha:** the `latlng` stream uses two parallel arrays — `data` holds latitudes, `data2` holds longitudes. This is **not** Strava's paired-array convention. See `EXTERNAL_APIS.md` for full details and the list of available stream types.

#### units — Show the athlete's unit preferences

```bash
python pull.py units
```

Returns the athlete's wind/temp/rain/distance/weight unit settings from Intervals. `sync.py` already reads this on every run to label `weather_summary.units` correctly — `pull.py units` is for ad-hoc inspection (debugging unit mismatches, confirming what `latest.json` will show).

---

## EXTERNAL_APIS.md — External Reference

Operational reference for the external APIs used by the agentic platform:

- **Strava** — segment data, athlete effort history, starred segments (pre-ride enrichment)
- **MET Norway (yr.no)** — multi-day weather forecasts (pre-ride briefings)
- **Open-Meteo** — high-resolution weather forecasts (pre-ride briefings)
- **Intervals.icu** — activity streams (per-second GPS/sensor data) and pre-computed weather summaries on the activity list endpoint

Section 11 protocol defines the reasoning rules for what to do with this data. `EXTERNAL_APIS.md` covers how to get it: endpoints, auth, response shapes, gotchas. Read it when implementing a new agentic flow that touches any of these APIs.

---

## Files

| File | Goes to | Description |
|------|---------|-------------|
| `push.py` | Data repo root (next to sync.py) | Validates and manages workouts + thresholds |
| `pull.py` | Repo tool (`section-11/examples/agentic/pull.py`) — run from your data repo root, or copy alongside sync.py for convenience | Read-only fetcher for activity streams + athlete units |
| `push-workout.yml` | `.github/workflows/push-workout.yml` | GitHub Actions workflow for dispatch |
| `EXTERNAL_APIS.md` | Reference only (stays in section-11) | External API reference (Strava, yr.no, Open-Meteo, Intervals streams/weather) |
| `README.md` | Reference only (stays in section-11) | This file |
