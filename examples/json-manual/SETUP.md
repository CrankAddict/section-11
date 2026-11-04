# Manual JSON Export

Manual export saves your Intervals.icu training data as files on your computer. Run it when you need fresh data, then give the files to your AI. You do not need GitHub.

## Get help from your AI

You choose the folder and enter credentials. An AI with command access can help; otherwise, you run the commands. Copy this prompt:

> Help me set up Manual export. Before acting, read the full guide at https://github.com/CrankAddict/section-11/blob/main/examples/json-manual/SETUP.md. If you can access my installed section11/ folder, read the same file at section11/examples/json-manual/SETUP.md. Check Python and your command access. Keep my existing data folder and dossier. Explain replacements and ask before changing my automatic-refresh preference. Help me export and share the correct files with my AI.

## Install and export

1. Use Python 3.11 or newer with Requests installed: `python3 -m pip install requests`. On Windows, use `py -3` instead of `python3`. If Python is missing or installation fails, follow [Prerequisites](#prerequisites).
2. In Intervals.icu **Settings**, find your Athlete ID near the bottom and your API key under **Developer Settings**.
3. Choose your data folder and open a terminal there (Terminal on Mac, PowerShell on Windows). Download `section11-YYYY.MM.DD.zip` from the [latest official release](https://github.com/CrankAddict/section-11/releases/latest), then extract it into `Downloads/section11-bootstrap`, outside the data folder.
4. For manual-only use, run `python3 "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init --no-timer`. Existing setups use `--update` instead of `--init`. Omit `--no-timer` if you want to keep automatic refresh. Before accepting, move your own files from `section11/` to `custom/`: the whole `section11/` folder is replaced. Unprotected same-name files elsewhere can also be removed; see the [removal rules](../maintenance/UPDATING.md#local-updates-and-automatic-toggle).
5. Run `python3 section11/examples/sync.py --setup` and enter your credentials.
6. On Mac or Linux, run `SECTION11_EXPORT_MODE=manual python3 section11/examples/sync.py --output latest.json`. In Windows PowerShell, first run `$env:SECTION11_EXPORT_MODE = 'manual'`, then `py -3 section11/examples/sync.py --output latest.json`, then `Remove-Item Env:SECTION11_EXPORT_MODE`. Check that `latest.json` contains your current data. The default export covers seven days; add `--days 14` for fourteen days. See [export options](#usage).

## Give the files to your AI

Upload `latest.json` and `history.json`, plus `intervals.json` for detailed session analysis. Include your dossier if used and a ZIP of **only `section11/`** for the protocol and templates. Never zip the whole data folder: it contains credentials. An AI on the same computer can read the files directly; verify its access. See [Use with AI](#use-with-ai) for other companion files.

Set up your AI with [Section 11's project instructions](../../README.md#3-configure-your-ai-platform).

Keep the data folder between exports. Run another export and replace uploaded copies when data changes; refresh the Section 11 upload after updates too.

[Full technical guide on GitHub](#technical-guide)

# Technical guide

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).

Export Intervals.icu data locally for different time ranges.

## Prerequisites

- Python 3.11 or newer
- `requests` library in that interpreter: `python3 -m pip install requests` (Windows: `py -3 -m pip install requests`)
- [Intervals.icu](https://intervals.icu) account with training data

Check `python3 --version` and `python3 -c "import requests"` first (PowerShell: `py -3 --version` and `py -3 -c "import requests"`). macOS `/usr/bin/python3` is too old (3.9); select Python 3.11 or newer.

If pip reports `externally-managed-environment` (Homebrew Python or recent Debian/Ubuntu), create a venv **outside the data folder**, which is often cloud-synced: `python3 -m venv "$HOME/.venvs/section11"`, then `"$HOME/.venvs/section11/bin/python" -m pip install requests`. Run the bootstrap `--init` with `"$HOME/.venvs/section11/bin/python"` and use it for later commands so the standard timer uses it too. Windows equivalent: `py -3 -m venv "$env:LOCALAPPDATA\Section11\venv"`, then `& "$env:LOCALAPPDATA\Section11\venv\Scripts\python.exe" -m pip install requests`; use `& "$env:LOCALAPPDATA\Section11\venv\Scripts\python.exe"` instead of `py -3` below.

## First-Time Setup

Use the same [verified release bootstrap and data-folder setup](../json-local-sync/SETUP.md#initial-setup)
as every local user. Download the canonical ZIP from the official date release,
extract it outside the data folder, then run from your data folder:

```bash
mkdir -p "$HOME/training-data" && cd "$HOME/training-data"
python3 "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init
```

Then configure your credentials:

```bash
python3 section11/examples/sync.py --setup
```

Enter your Intervals.icu credentials when prompted. Config saves to `.sync_config.json`.

Create a new dossier only if you have none already, then run the first export:

```bash
[ -e DOSSIER.md ] || [ -L DOSSIER.md ] || cp section11/DOSSIER_TEMPLATE.md DOSSIER.md
SECTION11_EXPORT_MODE=manual python3 section11/examples/sync.py --output latest.json
```

**Windows PowerShell:** extract the same release ZIP outside the data folder, then:

```powershell
$DataFolder = Join-Path $HOME "Training data" # e.g. C:\Users\René Martin\Training data
New-Item -ItemType Directory -Path $DataFolder -Force | Out-Null
Set-Location -LiteralPath $DataFolder
py -3 "$HOME\Downloads\section11-bootstrap\section11\examples\sync.py" --init
py -3 ".\section11\examples\sync.py" --setup
if (-not (Get-ChildItem -LiteralPath . -Force -ErrorAction Stop | Where-Object Name -eq "DOSSIER.md")) {
    Copy-Item -LiteralPath ".\section11\DOSSIER_TEMPLATE.md" -Destination ".\DOSSIER.md" -ErrorAction Stop
}
$env:SECTION11_EXPORT_MODE = "manual"
py -3 ".\section11\examples\sync.py" --output ".\latest.json"
Remove-Item Env:SECTION11_EXPORT_MODE
```

Root `DOSSIER.md` is the authoritative dossier; uploads are delivery copies. If a dossier already lives elsewhere, use that copy until you move it to the data-folder root yourself; the AI asks once and never moves or copies it. Do not create a competing dossier. Keep a repository containing it private; Git keeps old versions.

Auto sync is installed by default, including through this guide. To choose running
only by hand, add `--no-timer` to `--init` or a later `--update`; this persists
`"auto_sync": false` so updates never re-add a timer. `--timer` re-enables it.
The installer uses one acceptance, removes unprotected copies by the [shared name rule](../maintenance/UPDATING.md#local-updates-and-automatic-toggle), and creates
missing custom guidance. Existing root/manual or copy-only folders use that same
bootstrap with `--update`, preserving data, credentials and export choices.
Outside `section11/`, any file in any folder named exactly like a release or
historical Section 11 file is removed, except the keep list in the update guide.
Protection ignores case; removal requires exact spelling. Keep your own files in
`custom/` or outside the data folder. Every removal is listed before acceptance
and logged in full mode. The rollback ZIP is short-term recovery until the next
changing install, not a backup; only unprotected parents emptied by removal are pruned.

Normal exports keep private request accounting and cached responses in `<data folder>/state/`, beside the selected output file, between runs. It contains `request-budget/<identity>/`, `sources/<identity>/` and a `README.md` written by sync.py. `SECTION11_STATE_DIR` replaces this whole state folder, with all three inside it. Deleting state makes the next run larger and resets the local count; never delete it to force requests. Inactive hash-named subfolders from an earlier API key or data-folder location can be deleted; the active one changes on every check. See [Private sync state](../json-local-sync/SETUP.md#private-sync-state).

Upload the exported data with the installed files as described in [Use with AI](#use-with-ai).
State is not part of those JSON files or the supplied publication paths. If you cloud-sync the whole data folder, state is uploaded too, and a whole-folder connector can technically read it. `data_overview.state_note` and `READ_THIS_FIRST.state_note` in latest.json explicitly tell AI tools to ignore `state/`; use the exported `source_freshness` summary for status.

We recommend one setup per user. Before changing the sync path or moving machines, stop any old timer or workflow first to protect Intervals.icu. The count is per data folder, API key and athlete; separate folders do not coordinate.

**Finding your credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

## Usage

### Export to local file

Declare the invocation as Manual before exporting: `export SECTION11_EXPORT_MODE=manual` in a POSIX shell, or `$env:SECTION11_EXPORT_MODE = 'manual'` in PowerShell. The export then has `export_freshness.mode: "manual"`, `reason: "manual"` and a null delivery deadline. Its snapshot age still follows the 12/24-hour rule. If you omit the declaration, exports still work with mode `unknown` and the same age fallback; no scheduled refresh is assumed. Set this only for manual invocations, not for a local timer.

```bash
# Last 7 days (default)
python3 section11/examples/sync.py --output latest.json

# Last 14 days
python3 section11/examples/sync.py --days 14 --output 14days.json

# Last 90 days
python3 section11/examples/sync.py --days 90 --output 90days.json
```

### Common time ranges

| Days | Use case |
|------|----------|
| 7 | Weekly review |
| 14 | Two-week block |
| 42 | 6-week training block |
| 90 | Quarterly / build cycle |
| 180 | Season review |

### Repository delivery

Use [GitHub sync](../json-auto-sync/SETUP.md#github-sync-setup-guide) or [On-demand sync](../json-on-demand/SETUP.md) for repository delivery through the shared workflow. The legacy direct API publisher is not one of the four supported setup paths. Existing local API publishers keep their destination and private configuration and run `python3 section11/examples/sync.py` without `--output`. Release maintenance follows data work, including definitive failure or defer, using the same half/full policy as file exports. An unknown data publication holds maintenance for reconciliation and is never retried.

### Request allowance

Manual exports share the local count with other sync.py and push.py runs using the same data folder, API key, athlete and state location. Other folders, tools and machines are not counted. Intervals.icu allows 8,000 requests per API key per UTC day and 2,500 per 15 minutes; sync keeps 1,000 for other tools, leaving at most 7,000 daily, and respects a lower reported limit.

A normal warm local run makes 4 requests. The first export after updating, a different date range or a due refresh can need more. An earlier live check made 69 requests in about 47 s on the first run, then 4 per run in about 2 s; it predates the state-location and interval-choice changes. An immediate repeat may wait for the next eligible check or a provider hold; it does not necessarily rewrite the export. See [request counts and scheduling](../json-local-sync/SETUP.md#automate-the-refresh).

## Generated Files

The script creates/maintains these files:

| File | Purpose | When created |
|------|---------|--------------|
| `latest.json` | Training data export | Successful admitted refresh with `--output`; may be retained while waiting |
| `history.json` | Longitudinal data: daily (90d), weekly (180d), monthly (3y) | First run, regenerates when outdated |
| `intervals.json` | Per-interval data for structured sessions | Every run (incremental, 14-day retention) |
| `routes.json` | Route/terrain data for events with GPX/TCX attachments | When attachments exist |
| `saved_workouts.json` | Read-only mirror of the athlete's Intervals.icu saved workouts | First run, then on its own 6-hour refresh throttle |
| `ftp_history.json` | FTP progression tracking | Automatically on first run |
| `route_eta_history.json` | Retained 180-day outdoor ETA calibration | Normal sync/history updates |
| `maps/weather/` | Up to four ordered PNG pages per ride, six rides (24 pages), for chat | Fresh eligible route-weather briefs |
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

Each successful export with updated sync.py includes `sleep_context` in latest.json (or your selected output filename), using a 35-date wellness window (D−34..D) regardless of `--days`. Existing baselines and reports retain their original 28-date slice. There is no separate sleep file or history-refresh requirement. Retained wellness keeps its acquisition time in `source_updated_at`; `source_freshness` describes its refresh status. Upload the current export as usual; the AI discovers sleep context through `READ_THIS_FIRST.sleep_context_note`. It is low-confidence context only, never readiness. Missing dates, unknown athlete timezone or current-date mismatch remain explicit unavailable states; an old upload does not become fresh without another export.

`source_freshness` also records each source's status (`fresh`, `stale`, `deferred`, `unavailable`), acquisition age and coverage, plus the budget, schedule and warnings. Null age means unknown. Rewriting the export does not reset cached source ages. See the [field reference](../json-examples/README.md#source-freshness).

The export includes pre-calculated **derived metrics** for Section 11 compliance. AI should use these, not calculate its own. Key metrics: ACWR, Recovery Index, Monotony/Strain, Grey Zone %, Quality Intensity %, Easy Time Ratio, Benchmark Index, Phase Detection, Seiler TID, Aggregate Durability, and TID Drift.

See [examples/README.md](../README.md#derived-metrics) for the full derived metrics table.

## Use with AI

**Calendar naming:** To let the calendar support a deload week, name its sessions with "Deload" or "Recovery week", for example "Recovery week - easy ride". Single recovery rides inside normal weeks are not read as a deload week. Names support the phase assessment; they do not establish it on their own.

Date-only/exact-midnight workouts use labelled 10:00 local by default. Optional `route_weather_default_start` in the existing config or `SECTION11_ROUTE_WEATHER_DEFAULT_START` in the export environment changes it. The AI asks for the actual start or asks you to set it in Intervals.icu; the next normal export picks it up. See [departure handling](../../README.md#route-weather-departure). The overview sits directly after READ_THIS_FIRST, or first when absent.

No extra Manual export steps are needed for 11.80. Sync writes companions next to the latest export, including when `--output` names another directory; retain that folder between exports. The AI reads `latest.json.data_overview` first for presence, file-write times, relative locations and per-ride route/weather/map status. Resolve paths against that export's source; if uploads lose folders, match filenames and verify brief binding. The AI reads and shows matching PNG pages in their listed order only if it can already access them; missing pages remain explicit. Otherwise use the text brief, never describe an unseen map or ask the user to download/upload one. Maps are not part of the download artifact ZIP. Weather times use local zone labels and compass directions.

**Option 1: Upload files**: Upload `latest.json` and `history.json` to your AI platform for a complete analysis with longitudinal context. Upload `intervals.json` when you want detailed post-workout analysis of structured sessions. Upload `routes.json` (if present) when you want terrain-aware coaching for planned events. Upload `saved_workouts.json` on demand, when you want to select, reuse, or discuss one of your saved workouts.

Include `DOSSIER.md` if used and a ZIP of the `section11/` folder only, so the chat has the installed
protocol and templates. Never zip the whole data folder: credentials and rollback
state stay private. An uploaded ZIP is a snapshot; re-upload for fresh data and
after updates, replacing the previous upload.

**Option 2: Repository delivery**: Follow the GitHub or On-demand setup above, then the [main README setup guide](../../README.md#web-chat-setup) for configured AI access.

**Option 3: Use with agentic platforms**: Claude Code, Claude Cowork, OpenAI Codex CLI, Gemini CLI, OpenClaw, and Hermes read files directly from whatever filesystem their runtime can reach; where that runtime is the machine holding your exported files, no GitHub is needed. Point the agent at the folder containing your exported JSON files. Grok Bot is **experimental** and its filesystem is provider-hosted, so the data reaches it by connector or authenticated repository rather than from your disk; capability class is not a support promise. See the [agentic setup guide](../../README.md#agentic-setup).

### Automate it

Automatic maintenance follows the same daily rule as Local; see
[Updating Section 11](../maintenance/UPDATING.md#local-updates-and-automatic-toggle).
Manual-only setups check only when you run them. Half mode exports a fixed
`update_notice` for an outstanding verified update or repair.

Auto sync is already the installation default. For timer status and the persistent
manual-only opt-out, see [json-local-sync](../json-local-sync/SETUP.md#automate-the-refresh).

---

## Options Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--setup` | Run setup wizard | - |
| `--init` / `--update` | Install the latest verified release and auto sync with one acceptance | half release-update policy |
| `--no-timer` / `--timer` | Persist auto sync off/on during init or update | on |
| `--days N` | Days of data to export | 7 |
| `--output FILE` | Save to local file | - |
| `--week-start DAY` | Training week start day (mon/tue/wed/thu/fri/sat/sun) | mon |
| `--debug` | Show API field debug info | off |

**Note:** `--week-start` can also be set in `.sync_config.json` (`"week_start": "sun"`) or via `WEEK_START` environment variable. Config file setting persists across runs: no need to pass the flag every time.

**Note:** Only `metadata.athlete_id` is redacted. The output is not anonymized. See [Privacy & Security](../../README.md#privacy--security).

---

## Troubleshooting

### "Config not found" error
Run `python3 section11/examples/sync.py --setup` first.

### Empty or missing data
- Check your API key is valid
- Verify you have activities in the requested date range
- Run with `--debug` to see API responses

### FTP history not updating
FTP history only adds entries when FTP **changes**. If your FTP is the same, no new entry is added.

### Export unchanged or request allowance warning
Check the console and `source_freshness` for a deferred check, pause or provider hold. Wait until eligible, and check competing syncs/tools using the key. Do not delete private state to force a new allowance. See [Request allowance and pauses](../json-local-sync/SETUP.md#request-allowance-and-pauses) for the exact pause message and private-state recovery steps.

For general AI platform issues (data not fetching, AI fabricating metrics, connector problems), see the [main README troubleshooting guide](../../README.md#troubleshooting).
