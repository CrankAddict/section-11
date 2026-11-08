# Local Sync Setup Guide

Local sync copies your Intervals.icu training data into a folder on your computer. Your computer refreshes it; your AI reads it. No GitHub account is needed.

## Get help from your AI

You choose the folder and enter credentials. Check whether your AI can run commands on this computer; otherwise, you run them. Copy this prompt:

```text
Help me set up Section 11 Local sync, one step at a time.
Read this guide first: https://github.com/CrankAddict/section-11/blob/main/examples/json-local-sync/SETUP.md (if you can open my installed section11/ folder, use its copy instead).
Keep my existing data folder, dossier and settings; explain changes and ask before changing anything.
```

For full guided setup, including your dossier and AI connection, give your AI this link: <https://github.com/CrankAddict/section-11/blob/main/SETUP_ASSISTANT.md>.

## Set it up yourself

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
4. Choose your final data folder: keep your existing one, or use a cloud-synced folder for cloud AI access.
5. Open a terminal in that folder.  
   Mac: type `cd ` (with a space), drag the folder into Terminal and press Return.  
   Windows: open it in File Explorer, enter `powershell` in the address bar and press Enter.
6. Download `section11-YYYY.MM.DD.zip` from the [latest official release](https://github.com/CrankAddict/section-11/releases/latest) and extract it into an empty `Downloads/section11-bootstrap` folder, outside your data folder.  
   Mac: create that folder, double-click the ZIP (Safari may already have unzipped it) and move `section11` inside.  
   Windows: right-click the ZIP, choose **Extract All**, destination `Downloads\section11-bootstrap`.
7. Move your own files from `section11/` to `custom/` first ([removal rules](../maintenance/UPDATING.md#local-updates-and-automatic-toggle)). Install from your data folder:

   ```sh
   python3 "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init
   ```

   Existing users: use `--update` instead of `--init`.
8. Set up your credentials when prompted, then run your first sync:

   ```sh
   python3 section11/examples/sync.py --setup
   python3 section11/examples/sync.py --output latest.json
   ```

   Check that `latest.json` contains your current data.
9. Give your AI access to `latest.json` and `section11/` using [Section 11's project instructions](../../README.md#3-configure-your-ai-platform). Ask it to confirm it can read the data, protocol and templates.

## After setup

Keep the data folder private: it contains your credentials and personal data. Your dossier goes next to `latest.json`.

Your data refreshes automatically while your computer is on. You can [change or turn off the refresh](#automate-the-refresh).

Updates still need your confirmation by default, but you can [turn on automatic updates](../maintenance/UPDATING.md#automatic-updates-and-undo). Keep your own files in `custom/`: updates replace everything in `section11/`.

Is your AI not on this computer? Use a cloud connector or the [web-chat upload steps](#using-with-web-chat-platforms).

Need help? See [updating](../maintenance/UPDATING.md#updating-section-11) or [troubleshooting](#verification-and-troubleshooting).

[Full technical guide on GitHub](#technical-guide)

# Technical guide

Run Section 11 from a machine you control: no GitHub needed. A script syncs your training data from Intervals.icu on a timer, and your AI coach reads the output, either directly from a filesystem its runtime can reach (agentic platforms) or via a cloud connector (AI chats with no runtime filesystem; [platform support varies](../../README.md#platform-setup)).

> **Already using Section 11 locally?** Keep your data folder. Obtain the release bootstrap in [Initial Setup](#initial-setup), run it with `--update` from that folder, and accept once. Guide, root/manual, copy-only and clone installations use this same route. See [Staying Up to Date](#staying-up-to-date): installation replaces all of `section11/`, removes copies selected by the [shared name rule](../maintenance/UPDATING.md#local-updates-and-automatic-toggle) and manages auto sync.

> **Other setup paths:** If you prefer GitHub-based sync, see [json-auto-sync](../json-auto-sync/SETUP.md). For one-off manual exports, see [json-manual](../json-manual/SETUP.md).

---

## What is "Local Sync"

sync.py runs on a machine or service you control, pulling your data from Intervals.icu on a timer. The output reaches your AI coach either directly (agentic platforms whose runtime can reach the data directory) or via a connector (Google Drive, OneDrive, etc.). "Local" doesn't mean the machine has to be next to you; it just means you control it:

- Your Mac, PC, or laptop
- A Linux VPS (Hetzner, DigitalOcean, etc.)
- A Raspberry Pi or home server
- A Mac Mini under your desk

The machine doesn't need to be on 24/7. sync.py runs when the machine is on, and the timer picks up automatically after a restart or wake. Refreshes resume when the request allowance and any provider hold permit.

For regular data refresh (agentic coaches, heartbeat checks), a machine that stays on is ideal, but not required.

### How the AI reads your data

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).

Each successful updated sync produces `latest.json.sleep_context` from a 35-date wellness window (D−34..D); existing baselines and reports still use their original 28-date slice. There is no separate sleep file or history-refresh requirement. A retained wellness snapshot keeps its acquisition time, recorded in `source_updated_at`; `source_freshness` describes its refresh status. The AI discovers sleep context through `READ_THIS_FIRST.sleep_context_note` in the same latest export. It is low-confidence context only, with explicit coverage and unavailable states, never a readiness signal. An unknown athlete timezone or current-date mismatch withholds comparison. See [Multi-night sleep context](../../SECTION_11.md#recovery-metrics-integration-hrv--rhr--sleep--feel).

- **Agentic platforms** (OpenClaw, Claude Code, Cowork, Codex CLI, Gemini CLI, Hermes): read files directly from whatever filesystem their runtime can reach. Where that runtime is this machine, it is the simplest path. Some run on a provider-hosted computer instead, which cannot see your data directory; check before assuming.
- **Sessions with no runtime filesystem** (ChatGPT, Gemini, Perplexity and similar chat apps): sync.py writes to a cloud-synced folder (Google Drive, OneDrive, Dropbox), and the AI reads via its connector. Your computer or server does the syncing; the AI just reads the result. A provider-hosted agentic runtime uses the same bridge for the same reason. Note: cloud connector support for `.json` varies by platform; see the [connector table](../../README.md#platform-setup).

### Why local

- **Cheapest reliable path**: sync.py runs on your machine for free. No GitHub Actions minutes, no compute costs.
- **Direct reads**: local file reads avoid remote URL caching; upstream sync requests can still be rate-limited or fail
- **Privacy**: your data goes only where you send it: the machine you run sync.py on, and any cloud storage or repository you configure
- **Speed**: a runtime that can reach the files reads them directly with zero latency. A connector read is slower than that but faster than URL fetching.
- **Works everywhere**: any machine that runs Python. Any AI whose runtime can reach the files, or that has a cloud connector.

---

## Prerequisites

- Python 3.11 or newer
- `requests` library in that interpreter: `python3 -m pip install requests` (Windows: `py -3 -m pip install requests`)
- [Intervals.icu](https://intervals.icu) account with training data

Check `python3 --version` and `python3 -c "import requests"` first (PowerShell: `py -3 --version` and `py -3 -c "import requests"`). If Python is missing or older, install Python 3.11 or newer from [python.org](https://www.python.org/downloads/), then reopen the terminal and repeat the check. macOS `/usr/bin/python3` is too old (3.9); select Python 3.11 or newer.

If pip reports `externally-managed-environment` (Homebrew Python or recent Debian/Ubuntu), create a venv **outside the data folder**, which is often cloud-synced: `python3 -m venv "$HOME/.venvs/section11"`, then `"$HOME/.venvs/section11/bin/python" -m pip install requests`. Use that interpreter for all commands below, starting with `"$HOME/.venvs/section11/bin/python" "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init`, so the standard timer uses it too.

Windows equivalent: `py -3 -m venv "$env:LOCALAPPDATA\Section11\venv"`, then `& "$env:LOCALAPPDATA\Section11\venv\Scripts\python.exe" -m pip install requests`; run `--init` and later commands with `& "$env:LOCALAPPDATA\Section11\venv\Scripts\python.exe"` instead of `py -3`. Keep that environment outside the data folder.

**Finding your Intervals.icu credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

---

## Initial Setup

Choose the final data directory before `--init`. For cloud connector access, use
the cloud-synced folder here instead of `~/training-data/` throughout these steps.
From the official [latest date release](https://github.com/CrankAddict/section-11/releases/latest), download its canonical
`section11-YYYY.MM.DD.zip` asset and extract it under `~/Downloads/section11-bootstrap/`.
Use the extracted `section11/examples/sync.py` as the bootstrap, outside your data
folder. Do not overwrite an old root script to stage it. The installer independently
verifies the latest official release before replacement. If no compatible release
exists yet, stop and wait; never substitute a development/source archive or raw main.

```bash
mkdir -p "$HOME/training-data" && cd "$HOME/training-data"

# Install the complete verified date release and auto sync; accept once
python3 "$HOME/Downloads/section11-bootstrap/section11/examples/sync.py" --init

# Configure credentials through the managed entry
python3 section11/examples/sync.py --setup
```

For an existing data folder, use the same bootstrap with `--update`. After verified
installation, root `sync.py`, `push.py` and `pull.py` are removed. All commands use
the managed entries. Missing `custom/` and its README are created without replacing
existing custom files. Auto sync is installed by default; `--no-timer` explicitly
opts out and persists that choice. `--timer` re-enables it on a later install/update.

```bash
# Copy the template only when no dossier file or symlink exists
[ -e DOSSIER.md ] || [ -L DOSSIER.md ] || cp section11/DOSSIER_TEMPLATE.md DOSSIER.md

# Run your first sync
python3 section11/examples/sync.py --output latest.json
```

**Windows PowerShell:** extract the same release ZIP outside the data folder, then:

```powershell
$DataFolder = Join-Path $HOME "Training data" # e.g. C:\Users\René Martin\Training data
New-Item -ItemType Directory -Path $DataFolder -Force | Out-Null
Set-Location -LiteralPath $DataFolder
py -3 "$HOME\Downloads\section11-bootstrap\section11\examples\sync.py" --init
py -3 ".\section11\examples\sync.py" --setup
# Create only if missing; existing files, folders and links stay untouched
if (-not (Get-ChildItem -LiteralPath . -Force -ErrorAction Stop | Where-Object Name -eq "DOSSIER.md")) {
    Copy-Item -LiteralPath ".\section11\DOSSIER_TEMPLATE.md" -Destination ".\DOSSIER.md" -ErrorAction Stop
}
py -3 ".\section11\examples\sync.py" --output ".\latest.json"
```

Root `DOSSIER.md` is the authoritative dossier; web-chat uploads are delivery copies. If a dossier already lives elsewhere, use that copy until you move it to the data-folder root yourself; the AI asks once and never moves or copies it. Do not create a competing dossier. Keep a repository containing it private; Git keeps old versions.

If a run is already in progress, wait a minute before trying your first sync again.

### Workspace layout

```
~/training-data/
├── section11/                  # complete verified managed release
│   ├── SECTION_11.md
│   ├── DOSSIER_TEMPLATE.md
│   ├── manifest.json
│   ├── .section11-release.json  # verified release identity
│   ├── examples/
│   │   ├── sync.py
│   │   ├── agentic/
│   │   │   ├── push.py
│   │   │   ├── pull.py
│   │   │   └── ...
│   │   ├── reports/
│   │   │   ├── PRE_WORKOUT_REPORT_TEMPLATE.md
│   │   │   ├── POST_WORKOUT_REPORT_TEMPLATE.md
│   │   │   ├── 7_DAY_REPORT_TEMPLATE.md
│   │   │   └── 28_DAY_REPORT_TEMPLATE.md
│   │   ├── workout-library/
│   │   │   └── WORKOUT_REFERENCE.md
│   │   └── ...
│   └── ...
├── .sync_config                # credentials and preferences (created by --setup)
├── .section11-state/           # update lock, journal, daily attempt and rollback ZIP
├── sync.log                    # standard timer output, including macOS launchd
├── custom/                    # personal code and overrides
├── DOSSIER.md                  # authoritative athlete dossier in the data-folder root
├── latest.json                 # auto-generated by sync.py
├── history.json                # auto-generated by sync.py
├── intervals.json              # auto-generated by sync.py (structured sessions)
├── routes.json                 # auto-generated by sync.py (when GPX/TCX attachments exist)
├── saved_workouts.json         # auto-generated by sync.py (Intervals.icu saved workouts mirror)
├── ftp_history.json            # auto-generated by sync.py
├── route_eta_history.json      # retained 180-day outdoor ETA calibration
├── maps/weather/               # up to 24 current PNG pages for six rides, for chat
└── state/                      # internal sync state; AI tools must ignore it
    ├── request-budget/<identity>/
    ├── sources/<identity>/
    └── README.md               # written by sync.py
```

Key principle: `section11/` holds the Section 11 files that `--update` keeps current. Your personal files live at the data directory root. Updates replace files inside `section11/`; your dossier, config, and data are never touched.

With sync 3.146, every data companion lives next to the file selected by `--output`, even when it names another directory. Retain that export folder between runs. The AI reads `latest.json.data_overview` first for available files, route validity, weather and map status, then resolves relative paths against that folder or its connector equivalent. File presence does not guarantee connector access. The AI reads and shows matching PNG pages in their listed order on request or in the weather/pre-workout report; otherwise it uses text. Maps are never user downloads. Display times use the event/athlete timezone with DST-aware labels or an explicit UTC fallback; wind uses compass directions.

**Clone used as an install:** the same accepted installer replaces its ordinary
Git metadata along with the tree. That history survives only in the single rollback
slot, until the next successful installation. Keep an actual development checkout
separate; external worktree/submodule metadata requires owner resolution.

The rolling recovery file `<data folder>/archive/carry-forward.state` keeps previously exported activity summaries if a later export is damaged. Keep it between runs; update and rollback preserve it. Sync writes compact JSON atomically only when its content changes. AI tools must ignore this file and read recovery notices only from `latest.json.carry_forward`. Whole-folder cloud sync can still copy it. It is separate from the request state described below and is not moved by `SECTION11_STATE_DIR`.

### Private sync state

sync.py keeps request counts, holds and cached source responses in `<data folder>/state/` between runs. This folder contains `request-budget/<identity>/`, `sources/<identity>/` and a `README.md` written by sync.py. The data folder is the folder containing the file selected by `--output`.

`SECTION11_STATE_DIR` replaces the whole `state/` folder. Both `request-budget/` and `sources/`, plus the generated `README.md`, go inside that override. Use the same override for sync.py and push.py if you set one. Existing state is not automatically moved to a new location.

State contains private athlete responses. Syncing the whole data folder to cloud storage also uploads `state/`; a connector with access to the whole folder can technically read it. The AI is explicitly told to ignore it by `latest.json.data_overview.state_note` and `READ_THIS_FIRST.state_note`: `Ignore state/: internal sync state, not training data; AI tools must not read it.` Use `source_freshness` for status. The supplied publishing and workflow artifact paths never commit or upload state, but that does not exclude it from your own whole-folder cloud sync.

The count is shared by sync.py and push.py for the same data folder, API key and athlete. It does not coordinate other folders, even on the same machine or with the same state override, and does not count other tools using the key. It is not the provider's complete key-wide balance. **We recommend one setup per user.** Before changing the sync path or moving to another machine, stop the old timer or workflow first to protect Intervals.icu.

Deleting state makes the next run larger and resets the local count, without resetting the provider's allowance. Never delete it to force requests. Hash-named subfolders from an earlier API key or data-folder location can be deleted once they stop changing; the active one changes on every check. These old identity folders are not cleaned up automatically.

---

## Connect Your Agent

**Calendar naming:** To let the calendar support a deload week, name its sessions with "Deload" or "Recovery week", for example "Recovery week - easy ride". Single recovery rides inside normal weeks are not read as a deload week. Names support the phase assessment; they do not establish it on their own.

Point your agent at `~/training-data/`; this is your data directory. The agent sees personal files (dossier, JSON data) at the root, and the full protocol, templates, and tools in `section11/`.

On platforms where the agent workspace is separate from the data directory (e.g., OpenClaw's workspace is typically `~/clawd/`), set the `Data directory` field in DOSSIER.md so the skill knows where to find files.

### OpenClaw

OpenClaw's agent workspace (e.g., `~/clawd/`) is typically separate from the data directory (`~/training-data/`). Set the `Data directory` field in DOSSIER.md to `~/training-data/` so the Section 11 skill can locate your data files. HEARTBEAT.md stays in the agent workspace; that's where OpenClaw looks for it. Configure `HEARTBEAT.md` data sources with local file paths instead of URLs.

### Claude Code

```bash
cd ~/training-data && claude
```

Verify that Claude Code can read `latest.json`, `DOSSIER.md`, and `section11/SECTION_11.md` in this directory; write and execution access are separate capabilities.

### Claude Cowork

Grant Cowork access to the `~/training-data/` folder and verify that it can read the required files.

### ChatGPT Codex CLI

Run from `~/training-data/` and verify that Codex CLI can read the required files; write and execution access are separate capabilities.

### Gemini CLI

```bash
cd ~/training-data
gemini
```

Verify that Gemini CLI can read the required files in the working directory; write and execution access are separate capabilities.

### OpenCode

[OpenCode](https://opencode.ai/docs/) supports multiple model providers. Start it from `~/training-data/` and use the agentic contract under [Project instructions](#project-instructions) below.

### Hermes Agent

Hermes reads the filesystem of its runtime host, which may be this machine or a remote box you control, not necessarily the one you are reading this on. It uses the agentic contract named under [Project instructions](#project-instructions) below.

Point it at your data with a pointer file rather than copying files onto the host. Its working directory is not guaranteed to be where you think it is; set paths explicitly and check the resolved working directory before relying on a relative path.

### Grok Bot (experimental)

Grok Bot's filesystem is provider-hosted, so it cannot read this machine. It still has the agentic capability class and uses the agentic contract named under [Project instructions](#project-instructions) below; the data reaches it by connector or authenticated repository rather than from your disk. It is **experimental**: not validated end to end against the Section 11 pipeline, and capability class is not a support promise. Verify any write against the specific target before relying on it.

All Bots on your account share one cloud computer: files, browser sessions and command-line credentials are not isolated. Deleting a Bot does not clear shared files or browser sessions. Cloud storage is required and Legacy Privacy Mode is unavailable. Check your xAI and Cursor privacy settings before pointing it at a dossier carrying medication or health context.

### Open-weight options

Open-weight setups are another option, for example, GLM with ZCode, Qwen with Qwen Code, or DeepSeek through a compatible agent. These are examples, not fixed pairings: choose the models and tools that fit your needs.

### Control interfaces

[T3 Code](https://t3.codes/) is an optional control interface for supported agents, not a separate coaching runtime.

### Project instructions

Your coach's instructions live in one canonical contract, not in this guide. Which one you use depends on whether the AI has a runtime filesystem at all, not on which sync method you chose, and not on the platform's name. If it has one, whether that is this machine or a provider-hosted computer, it is an agentic session: copy the block between the fences in [`PROJECT_INSTRUCTIONS_AGENTIC.md`](../../PROJECT_INSTRUCTIONS_AGENTIC.md) into the agent's project settings. That holds even when the data itself arrives through a connector.

That contract names the Workout Reference Library and report templates. Verify that the agent can read the required files at `section11/examples/workout-library/WORKOUT_REFERENCE.md` and `section11/examples/reports/`; a path on your machine does not establish access from another runtime.

---

## Using with Web Chat Platforms

If your AI coach has no runtime filesystem at all, such as a web or phone chat app, it cannot read a filesystem directly. It can still receive the files another way: through a connector or authenticated repository, as an upload or attachment, or by fetching a URL. The usual bridge is the first of those: sync.py writes to a cloud-synced folder, and the AI reads it through its connector.

For a session with no runtime filesystem, the canonical contract is [`PROJECT_INSTRUCTIONS_WEB.md`](../../PROJECT_INSTRUCTIONS_WEB.md); copy the block between its fences into the AI's project settings. It names report templates and the Workout Reference Library; verify that the connected source exposes the required files at `section11/examples/reports/` and `section11/examples/workout-library/WORKOUT_REFERENCE.md`, or supply them as attachments.

An agent on a provider-hosted computer is a different case. It has a runtime filesystem, just not this machine's, so it uses the same bridge to receive the data but stays on the agentic contract.

**The simplest version:** sync.py outputs to your Google Drive folder. Google Drive desktop app syncs it to the cloud. Your AI reads it through its Google Drive connector. That's it. (Support and refresh behavior vary by platform; see the [connector table](../../README.md#platform-setup).)

### How to set it up

1. Install [Google Drive for Desktop](https://www.google.com/drive/download/) (or OneDrive, Dropbox, whatever your AI platform has a connector for)
2. Choose the final data directory inside the synced folder before `--init`:
   ```
   ~/Google Drive/My Drive/training-data/
   ```
3. Complete [Initial Setup](#initial-setup) from that folder, including `--init` and
   `--setup`. The installed `section11/`, `.sync_config` and exported data
   then share the same data folder, which the standard timer uses.
4. Connect the AI platform's Drive connector to the folder

For an existing installation, stop the old timer, move the whole data folder
including `section11/` and `.sync_config`, then run
`python3 section11/examples/sync.py --update` once from the new folder to point
the standard timer there. Keep the folder's credentials private.

Your AI coach now reads your data from the synced folder: no URLs, no GitHub, no manual uploads. Refresh behavior varies by platform; see the [connector table](../../README.md#platform-setup).

> **Tip:** Check that the connector exposes the installed `section11/` folder and
> current exported data. For manual uploads, supply exported data files, `DOSSIER.md` if used, and a ZIP
> of the `section11/` folder only. Never zip the whole data folder, which can contain
> credentials and rollback state. An uploaded ZIP is a snapshot; re-upload for fresh
> data and after updates. Keep the optional dossier as root `DOSSIER.md`; uploads are delivery copies.

### Many ways to do this

Google Drive is just one example. The principle is: **sync.py writes files → something syncs them to the cloud → the AI reads via a connector.** A few other setups that work:

- **OneDrive**: same pattern, works with platforms that have OneDrive connectors
- **Dropbox**: same pattern
- **VPS + rclone**: a server runs sync.py and pushes files to Google Drive (or any cloud storage) using [rclone](https://rclone.org). Good if your main computer isn't always on.
- **NAS with cloud sync**: Synology and QNAP have built-in Google Drive/Dropbox sync

We can't list every combination; there are many. The pattern is always the same: a machine runs sync.py, the output reaches a place the AI can read.

---

## Automate the Refresh

Both `--init` and `--update` install or refresh the standard Section 11 timer at
`check_interval_minutes`. If you set up your own timer before, remove it.
The installer manages only its standard timer and never inspects other commands.
The standard timer declares `SECTION11_EXPORT_MODE=local_scheduled`, so export
freshness can supply a delivery deadline.

The optional `.sync_config` field `check_interval_minutes` accepts the integers **1, 2, 5 or 10**, with **1** as the default. To choose five-minute checks, add `"check_interval_minutes": 5` to your existing config, keeping its credentials and other settings. Strings such as `"5"`, booleans and other invalid values fall back to one minute with this warning:

```text
Warning: invalid check_interval_minutes; using one-minute checks (choose 1, 2, 5 or 10).
```

This setting applies to local sync only. GitHub and On-demand ignore it; their workflow schedules are unchanged.

The timer methods below resume after restart or wake. A timer invocation is not always a refresh: sync.py can wait for its next eligible check or a provider hold.

Intervals.icu allows **8,000 requests per API key per UTC day** and **2,500 per 15 minutes**. sync.py keeps 1,000 for other tools such as push.py, so sync uses at most 7,000 a day. A lower daily limit reported by Intervals.icu wins. The local controller also paces requests and uses a more conservative short-window limit.

A normal local run makes **4 Intervals.icu requests**: activities, one wellness range and two calendar reads. The profile refreshes hourly; curves and activity messages refresh every 6 hours, with affected sources refreshed straight away after an activity changes or push.py writes, subject to allowance and holds. First runs, new activities, history refreshes and retries can cost more. Weather and GitHub requests are separate from these Intervals.icu counts.

**One-minute checks fit within the daily limit.** The measured offline scenarios below include startup and scheduled refreshes. Remaining requests are the difference from the provider's 8,000 daily limit, before any other use of the key; sync.py still keeps its 1,000-request reserve.

| Chosen interval | Quiet day requests | Remaining of 8,000 | Two new rides requests | Remaining of 8,000 |
|---|---:|---:|---:|---:|
| 1 minute | 5,804 | 2,196 | 5,887 | 2,113 |
| 2 minutes | 2,924 | 5,076 | 3,007 | 4,993 |
| 5 minutes | 1,196 | 6,804 | 1,279 | 6,721 |
| 10 minutes | 620 | 7,380 | 703 | 7,297 |

These are measured offline scenarios, not a guarantee for every athlete. sync.py counts only its own requests and push.py's requests in the shared state. If other tools use the key, choose a slower interval to leave them more room.

An earlier live check observed **69 requests in about 47 s** on the first run after updating, then **4 per run in about 2 s**. That observation predates the state-location and interval-choice changes. Expect the first run to be larger while private state is populated.

The interval ladder is **1, 2, 5, 10 minutes**. When allowance requires it, sync.py starts from your chosen interval and selects a slower step that fits. It never checks faster than your choice. Reduction messages are:

```text
Request budget: checks reduced to every 2 minutes.
Request budget: checks reduced to every 5 minutes.
Request budget: checks reduced to every 10 minutes.
```

It returns to your chosen interval when allowance permits, including after the UTC daily reset. Restoring one-minute checks prints `Request budget: one-minute checks restored.` Other choices print `Request budget: checks restored to every N minutes.`, with N replaced by 2, 5 or 10. It pauses only if even ten-minute checks cannot fit; see [Request allowance and pauses](#request-allowance-and-pauses). A UTC reset does not bypass the wait until the next chosen check, and provider holds remain in force.

These local totals use retained private state. The updated [GitHub and On-demand workflow](../json-auto-sync/SETUP.md#private-state-and-request-limits) separately reuses slow sources, reducing a quiet cache-hit tick from about 31 requests to 4; it has no daily allowance controller or step-down.

The single installation confirmation also covers the standard timer. It runs
`section11/examples/sync.py` with `--lockfile` from the data directory. Existing
API-publishing configuration remains API publishing; otherwise it exports to
`latest.json`. After changing the interval, run `--update` to refresh the timer.

### macOS (launchd)

The standard name is `com.section11.sync`, with its definition at
`~/Library/LaunchAgents/com.section11.sync.plist`. The installer registers it.
Inspect its status through launchd and `sync.log`; do not add another plist.

### Linux / VPS (systemd)

The standard user units are `section11-sync.service` and `section11-sync.timer`
under `~/.config/systemd/user/`. The installer enables the timer. Inspect with
`systemctl --user status section11-sync.timer` and
`journalctl --user -u section11-sync.service`. A usable user systemd session is
required. Cron is used only when systemd is missing.

### cron (universal fallback)

The installer manages only the exact `# section11-sync` entry. It reads the
crontab solely to preserve unrelated lines unchanged, without inspecting their commands. It runs from the data directory with the declared export mode.

### Windows (Task Scheduler)

The installer registers the `Section11Sync` task, with a literal Python action,
the data directory as its working folder, and the selected interval. Its action
sets `SECTION11_EXPORT_MODE=local_scheduled` before running the managed script.
Inspect the task's result in Task Scheduler.

### Explicit manual-only choice

Use `python3 section11/examples/sync.py --update --no-timer` to remove only
the standard Section 11 timer and persist `"auto_sync": false` in the existing configuration.
Later updates will not add a timer. `--timer` re-enables auto sync. The same flags
work on `--init`; no timer menu is presented. Other timers remain owner-managed.
A separate manual export declares `SECTION11_EXPORT_MODE=manual`; never apply
that declaration machine-wide to scheduled invocations.

---

## Circuit Breaker

The `--lockfile` flag prevents overlapping runs automatically. It:

- Creates `.sync.lock` in the working directory
- If another sync is already running (PID alive, lock < 10 min old): exits silently
- If the previous sync crashed (PID dead or lock > 10 min old): overrides the stale lock with a warning
- Cleans up the lockfile on exit

Recommended for intervals under 5 minutes. If you're running every 5+ minutes, overlapping runs are unlikely but `--lockfile` is still good practice.

---

## Staying Up to Date

Automatic installation is off by default. Check the official release status, run a
confirmed update or roll back from the data directory:

```bash
cd ~/training-data
python3 section11/examples/sync.py --status
python3 section11/examples/sync.py --update
python3 section11/examples/sync.py --rollback
```

From an old local setup, obtain the release bootstrap described in
[Initial Setup](#initial-setup) and run it with `--update` from the existing data
folder. The old 3.165 `--update` still runs but may clear `history.json`,
`intervals.json` and `routes.json`. The first installation asks once, after this
fixed warning:

> Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

Updates replace the complete `section11/` tree and keep data, settings, `custom/`
and your dossier. Outside `section11/`, any file in any folder named exactly like
a release or historical Section 11 file is removed, except the keep list in the
update guide. Protection ignores case; removal requires exact spelling. Keep your
own files in `custom/` or outside the data folder. Every removal is listed before
acceptance and logged in full mode. The rollback ZIP is short-term recovery until
the next changing install, not a backup; only unprotected parents emptied by
removal are pruned. By default an outstanding verified update shows a fixed
`update_notice` in the next export; set `"auto_update": true` in the existing
config or pass `--auto-update` to install automatically. The check runs once per
UTC day, on the first run starting at or after **04:00 UTC**. `--rollback` restores
the one previous installation without network.

See [Updating Section 11](../maintenance/UPDATING.md#local-updates-and-automatic-toggle)
for the full rules and the
[recovery guide](../maintenance/UPDATING.md#rollback-and-interruption-recovery)
for interrupted updates.

---

## Write Side (push.py)

push.py uses the same `.sync_config` credentials: no extra setup needed.

To share sync.py's request count, push.py uses an explicit `--data-dir` first. Otherwise it checks the folder containing its `section11/` copy for `latest.json`, then the working directory for `latest.json`. If neither is found, it warns `Warning: data folder not found; use --data-dir or run beside latest.json. Request capacity is unknown.` It does not create a count in an arbitrary folder. When needed, specify the data folder before the subcommand, for example `python3 section11/examples/agentic/push.py --data-dir ~/training-data list`. This selects the shared state location, not credentials or write approval.

```bash
cd ~/training-data
python3 section11/examples/agentic/push.py push --name "Sweet Spot 3x15" --date 2026-03-10 --type Ride \
  --description "- 15m 55%\n\n3x\n- 15m 88-92%\n- 5m 55%\n\n- 10m 50%" \
  --duration 85 --tss 75
```

See [examples/agentic/README.md](../agentic/README.md) for all commands, workout syntax, and template mappings.

**The five write subcommands preview first.** Run through push.py's command line, `push`, `move`, `delete`, `set-threshold` and `annotate` all print what they would do and change nothing until you add `--confirm`. The example above previews. Your coach should show you the preview, wait for your approval, and only then re-run with `--confirm`. Approval of one change is not approval of the next.

That gate lives in the command line, not in the library. An agent that imports `IntervalsPush` and calls its methods directly bypasses the preview entirely and writes on the first call. If yours runs Python rather than shell commands, tell it to invoke push.py as a command.

## Read Side (pull.py)

pull.py fetches raw per-second activity streams (lat/lng, altitude, watts, HR, …) on demand. Used only when the AI needs detail beyond the precomputed `terrain_summary` / `weather_summary` already present on outdoor activities in `latest.json`, for example, locating a specific power spike or wind segment within the GPS track.

```bash
cd ~/training-data
python3 section11/examples/agentic/pull.py trace --activity-id i142557875 --types latlng,altitude
```

Same `.sync_config` credentials. Read-only: no `--confirm` gate. Don't reach for pull.py if `latest.json` already answers the question; the streams payload is several MB per ride.

---

## Verification and Troubleshooting

### Verify sync is running

```bash
# Check data freshness
ls -la ~/training-data/latest.json

# Check timer status (macOS)
launchctl list | grep section11

# Check timer status (Linux)
systemctl --user status section11-sync.timer

# Tail the log
tail -f ~/training-data/sync.log
```

### Common gotchas

**`--init` download fails:** read the exact error. No published date release means
wait for the first official release. Otherwise check access to the release asset
and pinned manifest endpoints; a development clone is not an equivalent install.

**macOS launchd doesn't inherit shell PATH**: specify the full Python path in the plist (e.g., `/usr/local/bin/python3`). Find yours with `which python3`.

**`.sync_config` must be in the working directory**: the data directory root (`~/training-data/`), not inside `section11/`. If sync.py can't find credentials, check that your timer's `WorkingDirectory` is set correctly.

Older setups migrate automatically on the next normal sync. If renaming fails, sync uses `.sync_config.json` and retries next run. If both exist, `.sync_config` wins and the old file stays untouched. Never upload either file.

**Optional config fields** (add manually to `.sync_config` or re-run `--setup`):

- `auto_update`: boolean, default `false`; opt in to verified daily automatic installation after data work, including definitive failure or defer. Unknown data publication holds maintenance. Edit this field manually; the setup wizard preserves existing optional settings.
- `route_weather_default_start`: local HH:MM, default `"10:00"`, used only for date-only/exact-midnight workouts. `SECTION11_ROUTE_WEATHER_DEFAULT_START` in the timer environment overrides it. The AI labels ASSUMED and asks for the actual time. See [departure handling](../../README.md#route-weather-departure), including genuine midnight rides and confirmed push.py time updates.
- `week_start`: training week start day (`mon`–`sun`, default: `mon`)
- `zone_preference`: per-sport zone override for aggregations, e.g. `"run:hr,cycling:power"`. Only override what you need; unspecified sports default to power-preferred with HR fallback.
- `report_main_sports`: optional comma-separated report IDs, e.g. `"cycling,swimming"`. Absent by default; only sports present in the period can be retained. The sync process environment `REPORT_MAIN_SPORTS` is the fallback. This affects report selection, main-sport load and per-sport curves; skiing is accepted as an alias for nordic_skiing, while everyday overrides never select a main sport. See the protocol for exact IDs and recorded historical settings.

**Permissions**: the timer runs as your user. Ensure the output directory and its `state/` folder (or your [state override](#private-sync-state)) are writable.

**First run after updating or a long gap**: private sources and history may need rebuilding, so it can take longer and make more requests than a normal run. Use `--lockfile` to prevent overlap; see the [measured counts](#automate-the-refresh).

**Empty or missing data**: verify your Intervals.icu API key is valid and you have activities in the last 7 days. Run with `--debug` for detailed API output.

### Request allowance and pauses

Step-down warnings describe sync.py's effective interval; keep the timer at its configured check interval. When even ten-minute checks cannot fit the allowance, the exact message is:

> Request allowance cannot sustain a ten-minute check. Another sync or tool may be using this key. Check other syncs and tools, or use a new key.

Check for duplicate syncs and other tools using the key, including other machines. Reduce that competing usage or configure a new key as the message suggests. The timer rechecks allowance automatically. A `rate_hold` warning gives the provider's hold time; wait until it expires. Do not delete private state to force more requests: that loses the local count without resetting the provider's allowance.

`private_state_unavailable` means capacity is unknown. Check the state path, its permissions and the timer's environment. In this mode only up to three paced core reads are permitted per invocation, with no optional reads or writes; a coherent new export may be impossible and the previous output stays in place.

### Source freshness in latest.json

`source_freshness` records the budget, effective schedule, warnings and each source's status and age. `fresh` means valid under that source's refresh rules; `stale` means it needs refresh; `deferred` means refresh was held back; `unavailable` means no usable snapshot. `age_seconds` is time since acquisition, not since the export was written, and null means unknown. A valid unchanged activity cache can remain fresh as its age grows. Warnings describe step-down, pause, provider hold, unavailable private state, a full private cache or sources needing refresh. `source_store_capacity` means the private cache is full: new responses remain usable this run but may need fetching again until space is available. A new export timestamp alone does not mean every source was just fetched. See the [field reference](../json-examples/README.md#source-freshness).

---

## Privacy Notes

sync.py does not anonymize your data. Only `metadata.athlete_id` is redacted; activity names, date of birth, sex, height, location, timezone, athlete notes, and route coordinates are passed through, and `saved_workouts.json` carries your saved workouts in full: their names, descriptions, folder names and complete structures, which reveal planning intent such as goal events, target adaptations and prescribed intensities. See [Privacy & Security](../../README.md#privacy--security).

Activity and event IDs are always real (opaque database keys, not PII) to enable features like coach annotations and planned-vs-actual pairing.

Your data stays on this machine unless you send it somewhere: cloud storage for connector access, or a repository you configure. Where you do, it lands in an account you control, and Section 11 does not share it with anyone else, but the provider's own terms then apply to it.

sync.py reaches the network in more places than the data path alone, and which calls happen depends on what you ran.

Normal sync reads the training API and route attachments recorded there. After
data work on an eligible run, including definitive failure or defer, both half-mode advisories and full-mode updates use the official
release API, release asset and pinned raw manifest at most once per UTC day,
including failed attempts. They never advise from unpublished main content.
`--no-auto-update` suppresses this maintenance for the run. Local release requests
are anonymous. `--init`, `--status` and `--update` use those release endpoints
without reading training data; `--rollback` is offline.
`--setup` and `--generate-manifest` also return before that data path, so they make no Intervals.icu call.

Where a planned event carries a route file, sync.py fetches that attachment from whatever host Intervals.icu records for it. Where you configure GitHub publishing, it also calls `api.github.com` to read and write your repository using the token you supply. Confirmed local API publication uses the same daily release policy as file exports. It does not run the old separate changelog-Issue check; an uncertain publication holds maintenance.

Supported GitHub setups use the shared workflow
and its verified direct Update operation instead.
