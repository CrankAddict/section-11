# Manual JSON Export

Manual export saves your Intervals.icu training data as files on your computer. Run it when you need fresh data, then give the files to your AI. You do not need GitHub.

## Get help from your AI

You choose the folder and enter credentials. Check whether your AI can run commands on this computer; otherwise, you run them. Copy this prompt:

```text
Help me set up Section 11 Manual export, one step at a time.
Read this guide first: https://github.com/CrankAddict/section-11/blob/main/examples/json-manual/SETUP.md (if you can open my installed section11/ folder, use its copy instead).
Keep my existing data folder, dossier, settings and automatic-refresh preference; explain replacements and ask before changing anything.
```

For full guided setup, including your dossier and AI connection, give your AI this link: <https://github.com/CrankAddict/section-11/blob/main/SETUP_ASSISTANT.md>.

## Install and export

On Windows, use `py -3` instead of `python3` throughout.

1. In Terminal (Mac) or PowerShell (Windows), check for Python 3.11 or newer:

   ```sh
   python3 --version
   ```

   If missing or older, install from [python.org](https://www.python.org/downloads/), reopen the terminal and check again.
2. Install Requests; for help, see [Prerequisites](#prerequisites):

   ```sh
   python3 -m pip install requests
   ```

3. In Intervals.icu **Settings**, find your Athlete ID near the bottom and API key under **Developer Settings**.
4. Choose your data folder.
5. Open a terminal in that folder.  
   Mac: type `cd ` (with a space), drag the folder into Terminal and press Return.  
   Windows: open it in File Explorer, enter `powershell` in the address bar and press Enter.
6. Download `section11-YYYY.MM.DD.zip` from the [latest official release](https://github.com/CrankAddict/section-11/releases/latest) and extract it into an empty `Downloads/section11-bootstrap` folder, outside your data folder.  
   Mac: create that folder, double-click the ZIP (Safari may already have unzipped it) and move `section11` inside.  
   Windows: right-click the ZIP, choose **Extract All**, destination `Downloads\section11-bootstrap`.
7. Move your own files from `section11/` to `custom/` first ([removal rules](../maintenance/UPDATING.md#local-updates-and-automatic-toggle)). From your data folder, install for manual-only use:

   ```text
   python3 "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init --no-timer
   ```

   Leave out `--no-timer` if you want automatic refresh. Existing setups: use `--update` instead of `--init`.
8. Set up your credentials:

   ```sh
   python3 section11/examples/sync.py --setup
   ```

9. Export seven days by default; add `--days 14` for fourteen days ([export options](#usage)).  
   Mac or Linux:

   ```sh
   SECTION11_EXPORT_MODE=manual python3 section11/examples/sync.py --output latest.json
   ```

   Windows PowerShell (run all three lines in order):

   ```powershell
   $env:SECTION11_EXPORT_MODE = 'manual'
   py -3 section11/examples/sync.py --output latest.json
   Remove-Item Env:SECTION11_EXPORT_MODE
   ```

10. Check that `latest.json` contains your current data.

## Give the files to your AI

Set up your AI with [Section 11's project instructions](../../README.md#3-configure-your-ai-platform).

Then upload from your data folder:

- all `.json` files
- `DOSSIER.md`, if you have one
- a ZIP of only the `section11/` folder

Never upload `.sync_config` or an old `.sync_config.json`: they hold your credentials.

After each new export, upload the `.json` files again. After a Section 11 update, upload a new `section11/` ZIP.

[Full technical guide on GitHub](#technical-guide)

# Technical guide

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).

Export Intervals.icu data locally for different time ranges.

## Prerequisites

- Python 3.11 or newer
- `requests` library in that interpreter: `python3 -m pip install requests` (Windows: `py -3 -m pip install requests`)
- [Intervals.icu](https://intervals.icu) account with training data

Check `python3 --version` and `python3 -c "import requests"` first (PowerShell: `py -3 --version` and `py -3 -c "import requests"`). If Python is missing or older, install Python 3.11 or newer from [python.org](https://www.python.org/downloads/), then reopen the terminal and repeat the check. macOS `/usr/bin/python3` is too old (3.9); select Python 3.11 or newer.

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

Enter your Intervals.icu credentials when prompted. Config saves to `.sync_config`.

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
| `.sync_config` | Your credentials + preferences (local only) | After `--setup` |

Sync automatically keeps `archive/carry-forward.state` in the data folder between exports. It protects previously exported summaries if a later export is damaged, and update/rollback preserve it. Its `.state` extension keeps it outside the JSON upload set; it is also outside the `section11/` ZIP. AI tools must ignore it and use only `latest.json.carry_forward` for recovery notices. Whole-folder cloud sync can still copy it.

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

Automatic maintenance follows the same ten-minute allowance as Local; see
[Updating Section 11](../maintenance/UPDATING.md#local-updates-and-automatic-toggle).
Manual-only setups check only when you run them, after data work; failed checks
count. Automatic installation is opt-in, and half mode uses the same allowance
to report an outstanding verified update or repair in `update_notice`.
After a successful verification, unchanged release and installation inputs need
no release-file download. A clock moved back behind the saved attempt time
defers once for ten minutes.

Auto sync is already the installation default. For timer status and the persistent
manual-only opt-out, see [json-local-sync](../json-local-sync/SETUP.md#automate-the-refresh).
If `latest.json` stopped updating after an automatic update, see the
[recovery guide](../maintenance/UPDATING.md#rollback-and-interruption-recovery).

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

**Note:** `--week-start` can also be set in `.sync_config` (`"week_start": "sun"`) or via `WEEK_START` environment variable. Config file setting persists across runs: no need to pass the flag every time.

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
