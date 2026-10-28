# Local Sync Setup Guide

Run Section 11 from a machine you control: no GitHub needed. A script syncs your training data from Intervals.icu on a timer, and your AI coach reads the output, either directly from a filesystem its runtime can reach (agentic platforms) or via a cloud connector (AI chats with no runtime filesystem; [platform support varies](../../README.md#platform-setup)).

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

- Python 3.8+
- `requests` library: `pip install requests`
- [Intervals.icu](https://intervals.icu) account with training data

**Finding your Intervals.icu credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

---

## Initial Setup

Three commands to get started:

```bash
mkdir ~/training-data && cd ~/training-data

# Download sync.py (the bootstrap copy)
curl -O https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/sync.py

# Configure credentials
python3 sync.py --setup

# Download the full Section 11 repo
python3 sync.py --init
```

After `--init`, the bootstrap `sync.py` in the data directory root is removed. It's now at `section11/examples/sync.py`. All commands from here use the repo copy:

```bash
# Create your athlete profile from the template. -n refuses to overwrite an existing one
cp -n section11/DOSSIER_TEMPLATE.md DOSSIER.md

# Run your first sync
python3 section11/examples/sync.py --output latest.json
```

### Workspace layout

```
~/training-data/
├── section11/                  # the repo — exact mirror of github.com/CrankAddict/section-11
│   ├── SECTION_11.md
│   ├── DOSSIER_TEMPLATE.md
│   ├── manifest.json
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
├── .sync_config.json           # credentials and preferences (created by --setup)
├── DOSSIER.md                  # your athlete profile, and the official copy unless you record another location
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

**Alternative to `--init`:** If you prefer git, `git clone https://github.com/CrankAddict/section-11.git section11` gives you the complete repository, including maintainer files that `--init` does not install. Run `--update` once afterward to check the copy against the current manifest.

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
2. Set your data directory inside the synced folder:
   ```
   ~/Google Drive/My Drive/training-data/
   ```
3. Point your timer's `--output` at that folder (same as the regular local setup, just a different path)
4. Connect the AI platform's Drive connector to the folder

Your AI coach now reads your data from the synced folder: no URLs, no GitHub, no manual uploads. Refresh behavior varies by platform; see the [connector table](../../README.md#platform-setup).

> **Tip:** If your data directory already contains `DOSSIER.md` and `section11/`, and you sync the whole directory rather than the JSON alone, one connection gives the AI your data, your dossier and the protocol files together. Check what the connector is actually scoped to; where it exposes only the JSON, supply `SECTION_11.md` and the dossier separately.

### Many ways to do this

Google Drive is just one example. The principle is: **sync.py writes files → something syncs them to the cloud → the AI reads via a connector.** A few other setups that work:

- **OneDrive**: same pattern, works with platforms that have OneDrive connectors
- **Dropbox**: same pattern
- **VPS + rclone**: a server runs sync.py and pushes files to Google Drive (or any cloud storage) using [rclone](https://rclone.org). Good if your main computer isn't always on.
- **NAS with cloud sync**: Synology and QNAP have built-in Google Drive/Dropbox sync

We can't list every combination; there are many. The pattern is always the same: a machine runs sync.py, the output reaches a place the AI can read.

---

## Automate the Refresh

Set up a timer to run sync.py every **60 seconds**. Keep the timer at one minute even if you choose a slower check interval; sync.py decides when a check is due.

The optional `.sync_config.json` field `check_interval_minutes` accepts the integers **1, 2, 5 or 10**, with **1** as the default. To choose five-minute checks, add `"check_interval_minutes": 5` to your existing config, keeping its credentials and other settings. Strings such as `"5"`, booleans and other invalid values fall back to one minute with this warning:

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

These savings apply to local runs with retained private state. GitHub sync and On-demand keep their current behavior at about **31 requests per run**; their request savings come in a later release.

Command for all platforms:

```bash
python3 ~/training-data/section11/examples/sync.py --output ~/training-data/latest.json --lockfile
```

The `--lockfile` flag prevents overlapping runs if a sync takes longer than the interval.

### macOS (launchd)

Create `~/Library/LaunchAgents/com.section11.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.section11.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/YOUR_USERNAME/training-data/section11/examples/sync.py</string>
        <string>--output</string>
        <string>/Users/YOUR_USERNAME/training-data/latest.json</string>
        <string>--lockfile</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/training-data</string>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/training-data/sync.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/training-data/sync.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

**Replace `/usr/local/bin/python3` with your actual Python path** (`which python3`); launchd doesn't inherit your shell PATH.

**Replace `YOUR_USERNAME` with your macOS username.**

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.section11.sync.plist
```

To stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.section11.sync.plist
```

### Linux / VPS (systemd)

Create two files:

**`~/.config/systemd/user/section11-sync.service`:**

```ini
[Unit]
Description=Section 11 Intervals.icu Sync

[Service]
Type=oneshot
WorkingDirectory=%h/training-data
ExecStart=/usr/bin/python3 %h/training-data/section11/examples/sync.py --output %h/training-data/latest.json --lockfile
```

**`~/.config/systemd/user/section11-sync.timer`:**

```ini
[Unit]
Description=Section 11 sync timer

[Timer]
OnBootSec=30
OnUnitActiveSec=60
AccuracySec=10

[Install]
WantedBy=timers.target
```

Enable:

```bash
mkdir -p ~/.config/systemd/user
# (create both files above)
systemctl --user daemon-reload
systemctl --user enable --now section11-sync.timer
```

Check status:

```bash
systemctl --user status section11-sync.timer
journalctl --user -u section11-sync.service -f
```

### cron (universal fallback)

```bash
crontab -e
```

Add:

```
* * * * * cd ~/training-data && python3 section11/examples/sync.py --output latest.json --lockfile >> sync.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler → Create Basic Task
2. Trigger: repeat every 1 minute
3. Action: Start a program
   - Program: `python`
   - Arguments: `section11\examples\sync.py --output latest.json --lockfile`
   - Start in: `C:\Users\YOUR_USERNAME\training-data`

See [Microsoft's Task Scheduler docs](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page) for detailed instructions.

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

sync.py checks for Section 11 updates once per day during normal sync runs. If any operational files in `section11/` are behind, it prints:

```
⚠️  2 Section 11 updates available — run: python3 section11/examples/sync.py --update
```

To update:

```bash
cd ~/training-data
python3 section11/examples/sync.py --update
```

This shows what changed, then asks for confirmation before downloading:

```
   Updates available (2 files):

   sync.py          3.75 → 3.76   Data sync engine
   SECTION_11.md    11.13 → 11.14  Coaching protocol

   Already current (6):

   ✅ push.py          0.3
   ✅ WORKOUT_REF      0.6
   ...

   Pull 2 updates? [y/N]
```

Only changed files are downloaded. Personal files at the data directory root (dossier, config, data) are never touched. Nothing changes without your confirmation. Same principle as `--confirm` on push.py writes.

**Renames and removals use a second confirmation.** After checking downloads, `--update` lists files that no longer exist upstream as orphaned items and asks separately before deleting them. Approve that prompt to complete a rename or removal. Declining it, or running non-interactively, leaves the old files in place.

---

## Write Side (push.py)

push.py uses the same `.sync_config.json` credentials: no extra setup needed.

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

Same `.sync_config.json` credentials. Read-only: no `--confirm` gate. Don't reach for pull.py if `latest.json` already answers the question; the streams payload is several MB per ride.

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

**`--init` zip download fails**: corporate firewalls or proxies may block GitHub's archive endpoint. Alternative: `git clone https://github.com/CrankAddict/section-11.git section11` produces the same result, then run `--update` once to check it against the current manifest.

**macOS launchd doesn't inherit shell PATH**: specify the full Python path in the plist (e.g., `/usr/local/bin/python3`). Find yours with `which python3`.

**`.sync_config.json` must be in the working directory**: the data directory root (`~/training-data/`), not inside `section11/`. If sync.py can't find credentials, check that your timer's `WorkingDirectory` is set correctly.

**Optional config fields** (add manually to `.sync_config.json` or re-run `--setup`):

- `route_weather_default_start`: local HH:MM, default `"10:00"`, used only for date-only/exact-midnight workouts. `SECTION11_ROUTE_WEATHER_DEFAULT_START` in the timer environment overrides it. The AI labels ASSUMED and asks for the actual time. See [departure handling](../../README.md#route-weather-departure), including genuine midnight rides and confirmed push.py time updates.
- `week_start`: training week start day (`mon`–`sun`, default: `mon`)
- `zone_preference`: per-sport zone override for aggregations, e.g. `"run:hr,cycling:power"`. Only override what you need; unspecified sports default to power-preferred with HR fallback.
- `report_main_sports`: optional comma-separated report IDs, e.g. `"cycling,swimming"`. Absent by default; only sports present in the period can be retained. The sync process environment `REPORT_MAIN_SPORTS` is the fallback. This affects report selection, main-sport load and per-sport curves; skiing is accepted as an alias for nordic_skiing, while everyday overrides never select a main sport. See the protocol for exact IDs and recorded historical settings.

**Permissions**: the timer runs as your user. Ensure the output directory and its `state/` folder (or your [state override](#private-sync-state)) are writable.

**First run after updating or a long gap**: private sources and history may need rebuilding, so it can take longer and make more requests than a normal run. Use `--lockfile` to prevent overlap; see the [measured counts](#automate-the-refresh).

**Empty or missing data**: verify your Intervals.icu API key is valid and you have activities in the last 7 days. Run with `--debug` for detailed API output.

### Request allowance and pauses

Step-down warnings describe sync.py's effective interval; keep the timer at one minute. When even ten-minute checks cannot fit the allowance, the exact message is:

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

sync.py reaches the network in more places than the data path alone, and which calls happen depends on what you ran. A normal sync run calls the Intervals.icu API, and checks `raw.githubusercontent.com` for a newer manifest at most once a day. `--setup`, `--init`, `--update` and `--generate-manifest` return before that data path, so they make no Intervals.icu call: `--init` downloads the repository from GitHub's archive endpoint, and `--update` downloads each changed file from raw content, once per file. Where a planned event carries a route file, sync.py fetches that attachment from whatever host Intervals.icu records for it. Where you configure GitHub publishing, it also calls `api.github.com` to read and write your repository. After publishing, and only when you have configured both a GitHub token and a repository, it reads the upstream changelog and may open an issue. The `api.github.com` calls carry the token you supply; the changelog read carries none, though it happens only because both are set. On that publish path sync.py applies no cadence gate of its own, unlike the once-a-day manifest check.
