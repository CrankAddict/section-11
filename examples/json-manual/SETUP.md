# Manual JSON Export

Export Intervals.icu data locally for different time ranges.

## Prerequisites

- Python 3.8+
- `requests` library: `pip install requests`

## First-Time Setup

Download sync.py from the [Section 11 repository](https://github.com/CrankAddict/section-11/tree/main/examples):

```bash
curl -O https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/sync.py
```

Then configure your credentials:

```bash
python3 sync.py --setup
```

Enter your Intervals.icu credentials when prompted. Config saves to `.sync_config.json`.

**Finding your credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

## Usage

### Export to local file

```bash
# Last 7 days (default)
python3 sync.py --output latest.json

# Last 14 days
python3 sync.py --days 14 --output 14days.json

# Last 90 days
python3 sync.py --days 90 --output 90days.json
```

### Common time ranges

| Days | Use case |
|------|----------|
| 7 | Weekly review |
| 14 | Two-week block |
| 42 | 6-week training block |
| 90 | Quarterly / build cycle |
| 180 | Season review |

### Push to GitHub (optional)

If you configured GitHub credentials during setup:

```bash
python3 sync.py --days 14
```

Pushes to your configured GitHub repo.

## Generated Files

The script creates/maintains these files:

| File | Purpose | When created |
|------|---------|--------------|
| `latest.json` | Training data export | Every run with `--output` |
| `history.json` | Longitudinal data — daily (90d), weekly (180d), monthly (3y) | First run, regenerates when outdated |
| `intervals.json` | Per-interval data for structured sessions | Every run (incremental, 14-day retention) |
| `routes.json` | Route/terrain data for events with GPX/TCX attachments | When attachments exist |
| `ftp_history.json` | FTP progression tracking | Automatically on first run |
| `.sync_config.json` | Your credentials + preferences (local only) | After `--setup` |

### FTP History

`ftp_history.json` tracks indoor and outdoor FTP changes over time. Updated automatically when FTP changes. Used to calculate **Benchmark Index** (8-week FTP progression). Keep this file if you want continuous tracking. See [auto-sync SETUP](../json-auto-sync/SETUP.md#ftp-history-tracking) for details on the Benchmark Index.

### History Data

`history.json` provides longitudinal context with tiered granularity:

| Tier | Granularity | Range |
|------|-------------|-------|
| `daily_90d` | Day-by-day | Last 90 days |
| `weekly_180d` | Week-by-week | Last 180 days |
| `monthly_1y/2y/3y` | Month-by-month | Up to 3 years |

Also includes period summaries, FTP timeline, and data gap detection. Generated automatically on first run and regenerated when outdated.

## What's Included

The export includes pre-calculated **derived metrics** for Section 11 compliance — AI should use these, not calculate its own. Key metrics: ACWR, Recovery Index, Monotony/Strain, Grey Zone %, Quality Intensity %, Easy Time Ratio, Benchmark Index, Phase Detection, Seiler TID, Aggregate Durability, and TID Drift.

See [examples/README.md](../README.md#derived-metrics) for the full derived metrics table.

## Use with AI

**Option 1: Upload files** — Upload `latest.json` and `history.json` to your AI platform for a complete analysis with longitudinal context. Upload `intervals.json` when you want detailed post-workout analysis of structured sessions. Upload `routes.json` (if present) when you want terrain-aware coaching for planned events.

**Option 2: Push to GitHub + configure AI** — Push to a GitHub repo (private recommended), then follow the [main README setup guide](../../README.md#web-chat-setup). Most AI platforms now have GitHub connectors that can access private repos directly.

**Option 3: Use with agentic platforms** — Claude Code, Claude Cowork, OpenAI Codex CLI, Gemini CLI, and OpenClaw can read files directly from your filesystem — no GitHub needed. Point the agent at the folder containing your exported JSON files. See the [agentic setup guide](../../README.md#agentic-setup).

### Automate it

Want sync.py to run automatically on a timer? See [json-local-sync](../json-local-sync/SETUP.md).

---

## Options Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--setup` | Run setup wizard | - |
| `--days N` | Days of data to export | 7 |
| `--output FILE` | Save to local file | - |
| `--week-start DAY` | Training week start day (mon/tue/wed/thu/fri/sat/sun) | mon |
| `--debug` | Show API field debug info | off |
| `--anonymize` | Remove identifying info | on |

**Note:** `--week-start` can also be set in `.sync_config.json` (`"week_start": "sun"`) or via `WEEK_START` environment variable. Config file setting persists across runs — no need to pass the flag every time.

**Note:** Anonymization is enabled by default. Activity names, athlete ID, and location data are redacted in the output.

---

## Troubleshooting

### "Config not found" error
Run `python3 sync.py --setup` first.

### Empty or missing data
- Check your API key is valid
- Verify you have activities in the requested date range
- Run with `--debug` to see API responses

### FTP history not updating
FTP history only adds entries when FTP **changes**. If your FTP is the same, no new entry is added.

For general AI platform issues (data not fetching, AI fabricating metrics, connector problems), see the [main README troubleshooting guide](../../README.md#troubleshooting).
