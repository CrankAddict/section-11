# Agentic Workout Push

Write planned workouts to an athlete's Intervals.icu calendar. For AI platforms that can execute code or trigger GitHub Actions (OpenClaw, Claude Code, Cowork, etc.). Chat-only users cannot use this.

## Setup

### Path 1: GitHub Actions dispatch (recommended)

For anyone already running auto-sync. Uses the same `ATHLETE_ID` and `INTERVALS_KEY` secrets -- zero new credential setup.

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
    json={"ref": "main", "inputs": {"workouts": json.dumps(workouts)}}
)
```

The agent needs a `GITHUB_TOKEN` with `actions:write` scope on the data repo. For OpenClaw, this is already available if the skill uses GitHub Actions for sync.

### Path 2: Local execution (Claude Code, Cowork, json-manual users)

For agents running locally with direct filesystem access.

```bash
# Single workout
python push.py --name "Sweet Spot 3x15" --date 2026-03-10 --type Ride \
  --description "- 15m 55%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%" \
  --duration 85 --tss 75

# Batch from JSON file
python push.py --json week.json
```

Credentials loaded from (first match wins):
1. CLI args: `--athlete-id`, `--api-key`
2. `.sync_config.json` in working directory (same file sync.py uses)
3. Environment: `ATHLETE_ID`, `INTERVALS_KEY`

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

## Output

JSON to stdout for agent parsing:

```json
{"success": true, "count": 1, "events": [{"id": 33375903, "name": "Sweet Spot 3x15", "date": "2026-03-10", "type": "Ride", "category": "WORKOUT"}]}
```

On failure:

```json
{"success": false, "error": "date 2026-02-01 is in the past - planned workouts must be today or future"}
```

## Workout Fields

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

## Intervals.icu Workout Syntax

The `description` field uses Intervals.icu's native workout builder syntax. When provided, push.py sends `workout_doc: {}` which tells Intervals.icu to parse the description into structured workout steps.

### Targets

**Power:** `75%`, `220w`, `Z2`, `95-105%`, `MMP30s`, `MMP5m`
**HR:** `70% HR`, `95% LTHR`, `Z2 HR`
**Pace:** `60% Pace`, `Z2 Pace`, `5:00/km Pace`
**Cadence:** append `90rpm` to any step
**Ramps:** `ramp 50%-75%`
**Freeride:** step with no target (ERG off)

### Duration

`5m` = 5 minutes, `30s` = 30 seconds, `1h2m30s` = 1 hour 2 min 30 sec

**CRITICAL:** `m` means **minutes**, not meters. For distance use `km`, `mi`, or `mtr` (e.g., `500mtr`, `2km`, `1mi`).

### Structure

- Steps start with `-`
- Blank lines required around repeat blocks
- Text before duration becomes step cue
- Case-insensitive keywords
- Nested repeats NOT supported

### Example

```
- 15m ramp 50%-75%

3x
- 15m 88-92%
- 5m 55%

- 10m 50%
```

## Template Mappings

Maps Section 11 Workout Reference template IDs to Intervals.icu description syntax. **Always use %FTP ranges, not absolute watts** -- Intervals.icu resolves % to the athlete's current FTP.

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

## What NOT To Do

- **Don't use absolute watts** -- use `%FTP` ranges so workouts stay correct if FTP changes
- **Don't use `m` for meters** -- `m` means minutes. Use `km`, `mi`, or `mtr` for distance
- **Don't nest repeats** -- Intervals.icu doesn't support it
- **Don't push past dates** -- validation rejects them. Planned workouts are future events
- **Don't skip blank lines around repeat blocks** -- parsing breaks without them
- **Don't send workout_doc with no description** -- push.py handles this automatically

## Files

| File | Goes to | Description |
|------|---------|-------------|
| `push.py` | Data repo root (next to sync.py) | Validates and POSTs workouts |
| `push-workout.yml` | `.github/workflows/push-workout.yml` | GitHub Actions workflow for dispatch |
| `README.md` | Reference only (stays in section-11) | This file |
