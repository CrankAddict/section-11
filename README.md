# Section 11 - AI Coaching Protocol

[Project website](https://section11.net/)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An open protocol for deterministic, auditable AI-powered endurance coaching. Built for athletes who want AI coaches that follow science, not speculation.

---

## What Is This?

**Section 11** is a structured framework that enables AI systems (ChatGPT, Claude, Gemini, Grok (web/app), Mistral, etc.) to provide evidence-based endurance training advice with full auditability and deterministic reasoning.

### Core Principles

- **Deterministic**: Same inputs produce same outputs
- **Auditable**: Every recommendation cites specific data and frameworks
- **Evidence-based**: Grounded in 15+ peer-reviewed endurance science models
- **Athlete-controlled**: Your data, your thresholds, your goals

---

## What's Included

| File | Description |
|------|-------------|
| [SECTION_11.md](SECTION_11.md) | Complete protocol: AI Coach Guidance (11 A), Training Plan Protocol (11 B), Validation Protocol (11 C) |
| [examples/workout-library/](examples/workout-library/) | Workout Reference Library: 26 session templates, adapted to your data |
| [examples/agentic/](examples/agentic/) | Calendar writes, activity stream reads and external API reference |
| [examples/agentic/fit-file-and-merger/](examples/agentic/fit-file-and-merger/) | Multi-source FIT fusion, identity, verification, recovery and duplicate-cleanup reference; documentation only |
| [examples/json-local-sync/](examples/json-local-sync/) | Local automated sync, no GitHub needed |
| [examples/dfa_a1/NON_GARMIN.md](examples/dfa_a1/NON_GARMIN.md) | DFA a1 requires Garmin + AlphaHRV; other-platform verification guidance |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Your stable private athlete context |
| [examples/](examples/) | Sync guides and fictional JSON schema examples |
| [examples/reports/](examples/reports/) | Pre-workout, post-workout, rolling 7-day and 28-day, Season and on-request weather reports |
| [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) | Interactive AI-guided setup |
| [manifest.json](manifest.json) | File versions and update tracking |
| [LICENSE](LICENSE) | MIT license |

---

## Privacy & Security

`sync.py` redacts `metadata.athlete_id`, but does not anonymize your export. Activity names and IDs, date of birth, age, sex, height, location, timezone, notes, wellness and training data remain. Saved-workout names, descriptions, folders and full structures reveal planning intent, including goal events, target adaptations and prescribed intensities. Route JSON and weather maps reveal geometry and departure times; opaque map filenames do not hide their content. Keep exports and your dossier private. A public repository exposes its files.

Section 11 operates no hosted backend. Your data passes through the services you configure, and the AI, runtime, model, connector, repository and storage providers involved set their own processing and retention terms. See [Route Weather](#route-weather) for forecast-provider data transfers, defaults and both off switches.

Configured credentials go to their corresponding service: the Intervals.icu API key in its Authorization header, and a GitHub token to GitHub for configured publishing or issue creation. They are never included in exported or published JSON.

sync.py and push.py use [private sync state](examples/json-local-sync/SETUP.md#private-sync-state) in `<data folder>/state/` for request accounting and cached athlete responses. Local and Manual keep it between runs; syncing the whole folder to cloud storage uploads it too, and a whole-folder connector can technically read it. `data_overview.state_note` and `READ_THIS_FIRST.state_note` in latest.json explicitly tell AI tools to ignore it. The supplied publishing and workflow artifact paths never commit or upload state; GitHub and On-demand create it fresh each run and do not keep it. Use `latest.json.source_freshness` for status.

---

## Quick Start

**Before you start:** The documented data setups use [Intervals.icu](https://intervals.icu). You need an account containing your training data, plus your athlete ID and API key.

Section 11 is free to use. Your chosen AI platform or hosting may have its own costs.

> **Recommended:** Give [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) to your AI for guided setup, whether you use a chat app such as ChatGPT or Claude, or OpenClaw and similar always-on agentic setups. Or use the [Section 11 skill](SKILL.md), if supported.

You can also follow the step-by-step guides below.

### 1. Create Your Dossier: your stable private context

Copy `DOSSIER_TEMPLATE.md` and fill in the context your AI cannot read from your data: background, equipment, stable constraints, health and injury history, tested fueling, and how you prefer to be coached. Current thresholds and load always come from your JSON. You can start coaching before the dossier exists; a missing dossier limits personalisation, not safety.

### 2. Set Up Your Data Sync

Choose how your data reaches the AI:

- **[Local sync](examples/json-local-sync/SETUP.md):** uses a one-minute timer on a machine you control. Choose checks every 1, 2, 5 or 10 minutes; sync.py can reduce them to a slower step or pause when allowance requires it. The AI reads the files directly if its runtime can reach them, or through a cloud connector.
- **[GitHub sync](examples/json-auto-sync/SETUP.md):** writes to a private repository every 30 minutes by default. Schedules are best-effort; **Sync Now** requests a run and may queue. Runs consume Actions minutes. See [schedule options and costs](examples/json-auto-sync/SETUP.md#sync-schedule-and-github-actions-usage) before changing frequency.
- **[On-demand sync](examples/json-on-demand/SETUP.md):** trigger from your phone or browser, then download the JSON artifact or refresh your connector. No schedule or local Python.
- **[Manual export](examples/json-manual/SETUP.md):** run once for your chosen date range, then upload. Re-export when data changes.

Plain raw URLs require a public repository. For private data, use authenticated access or uploads.

**We recommend one setup per user.** Before changing the sync path or moving to another machine, stop the old timer or workflow first to protect Intervals.icu. The local count is per data folder, API key and athlete; separate folders do not coordinate, even on the same machine.

A normal local run uses **4 Intervals.icu requests**. The provider allows **8,000 per key per UTC day** and **2,500 per 15 minutes**; sync reserves 1,000 for other tools and uses at most 7,000 daily, or less if the provider reports a lower limit. One-minute checks fit within the limit in the measured offline scenarios; this is not a guarantee for every athlete. sync.py counts only its own and push.py's requests in shared state, so choose a slower interval if other tools use the key. GitHub and On-demand keep their current behavior at about **31 requests per run**; savings for those paths follow in a later release. See [interval choices, measured daily counts and automatic step-down](examples/json-local-sync/SETUP.md#automate-the-refresh), including the larger first run after updating.

### 3. Configure Your AI Platform

Choose your path:

- **[Agentic Platforms](#agentic-setup)**: OpenClaw, Claude Code, ChatGPT Codex, Grok Bot, and Hermes Agent, etc.
- **[Web Chat Platforms](#web-chat-setup)**: ChatGPT, Claude, Gemini, Grok, Mistral Vibe, etc.

### 4. Make Files Available to Your AI

Supply `SECTION_11.md`, your current `latest.json`, and `DOSSIER.md` if you use one. Supply companion JSON when the task needs it, plus the [report templates](examples/reports/) and [Workout Reference Library](examples/workout-library/) for reports and prescriptions.

Use the runtime's data folder, an authenticated repository/cloud connector, or uploads. If your connector exposes only data, supply the protocol and dossier separately or connect the protocol repository too.

Uploads are frozen. Replace old copies after updates, without leaving two official versions. Connectors may need refresh or re-import; check [Platform Setup](#platform-setup).

### Having trouble?

- [Activities are missing or incomplete, including Strava imports](#activities-show-null-or-missing-fields)
- [Your data looks out of date](#data-appears-stale-after-sync)
- [Your AI cannot read the data files](#ai-asks-for-data-instead-of-fetching)

---

## Agentic Setup

For sessions with a runtime filesystem, whether on your own machine or a hosted computer. Filesystem access, code execution and write access are separate capabilities, verified per target. Reading data does not authorize calendar writes.

Use [Local sync](examples/json-local-sync/SETUP.md) when the runtime can reach your data folder, or [GitHub sync](examples/json-auto-sync/SETUP.md) for repository access and backup. Hosted runtimes may need a connector or authenticated repository to reach your data.

Copy the block in [PROJECT_INSTRUCTIONS_AGENTIC.md](PROJECT_INSTRUCTIONS_AGENTIC.md) into the agent's persistent configuration. Point it at your files using [Connect Your Agent](examples/json-local-sync/SETUP.md#connect-your-agent).

### OpenClaw (formerly ClawdBot/MoltBot)

This is the reference setup. Section 11 works well with [OpenClaw](https://github.com/openclaw/openclaw): persistent memory, heartbeat scheduling, autonomous execution, and structured validation.

1. Clone or copy the Section 11 skill folder into your OpenClaw skills directory (skills are just directories with a `SKILL.md`)
2. Authenticate: `gh auth login`, or for limited access use a [fine-grained personal access token](https://github.com/settings/tokens?type=beta) scoped to your data repo only

### Claude Code

1. Install: see [claude.ai/download](https://claude.ai/download) or `npm install -g @anthropic-ai/claude-code`
2. Authenticate: `gh auth login` for GitHub repo access, or clone your data repo locally

### Claude Cowork

Cowork is a desktop app that can read files directly from your filesystem.

1. Clone your data repo locally and grant Cowork access to that folder
2. Or add GitHub from Cowork's Connectors directory.

### ChatGPT Codex

1. Connect your GitHub account at [chatgpt.com/codex](https://chatgpt.com/codex) and authorize your data repo; web and desktop app connect directly
2. Or install the CLI: `npm install -g @openai/codex` (reads from local filesystem)

### Gemini CLI

1. Install: `npm install -g @google/gemini-cli` (or `npx @google/gemini-cli`)
2. Clone your data repo locally and verify that Gemini CLI can read the required files

### Grok Bot (experimental)

Runs on a user-scoped shared computer and authenticates through Cursor. It has the agentic capability class, but it is **experimental**: it is not validated end to end against the Section 11 pipeline, and capability class is not a support promise. Any write must be verified against the specific target before it is used or assumed.

All Bots on your account share one cloud computer: files, browser sessions and command-line credentials are not isolated. Deleting a Bot does not clear shared files or browser sessions. Cloud storage is required and Legacy Privacy Mode is unavailable. Check your [xAI](https://docs.x.ai/) and Cursor privacy settings before adding a sensitive dossier.

### Hermes Agent

Experimental: not validated end to end with Section 11. Hermes reads its runtime host's filesystem, which may differ from your machine. Use a pointer file for your data, set paths explicitly, and verify the resolved working directory before relying on relative paths.

### OpenCode

An open-source coding agent for the terminal, IDE and desktop.

**Control interfaces.** T3 Code provides an interface for supported agents such as Claude Code, ChatGPT Codex and OpenCode. Section 11 access depends on the underlying agent's configured filesystem and tool permissions; T3 Code is not a separate coaching runtime.

### Agentic Tools

With verified execution, credentials and access, use [examples/agentic/](examples/agentic/):

- **`push.py`:** manage planned workouts, update sport-specific thresholds and annotate activities. Preview writes through the CLI; confirm only after approving the exact change.
- **`pull.py`:** read raw per-second GPS, altitude, power and HR when the synced summaries are insufficient.
- **`EXTERNAL_APIS.md`:** endpoints for Strava, MET Norway, Open-Meteo and Intervals.icu. Read sync's briefs for covered route forecasts; direct weather calls are for uncovered locations or times.

The [FIT File & Merger reference](examples/agentic/fit-file-and-merger/) needs no execution to read. It describes a cycling-tested implementation; other sports and sources need their own validation.

---

## Web Chat Setup

For AI platforms reached through a browser or app, with no runtime-accessible filesystem. These sessions reach your data through a connector or authenticated repository, an upload or attachment, or a URL fetch.

### Project Instructions

Copy the block between the fences in [PROJECT_INSTRUCTIONS_WEB.md](PROJECT_INSTRUCTIONS_WEB.md) into your Project, Space, Gem or custom instructions. If the AI has a runtime filesystem, use [PROJECT_INSTRUCTIONS_AGENTIC.md](PROJECT_INSTRUCTIONS_AGENTIC.md).

For URL fetch, replace `[USERNAME]/[REPO]` with your public data repository path. Connectors need no URL editing and grant no write authority by themselves.

### Platform Setup

Create a project, add the instructions above, then connect your data or upload the files listed in Quick Start. Check `metadata.last_updated` before relying on a report. Access does not guarantee freshness.

**GitHub connector status for web-chat platforms.** Runtime repository access is covered in [Agentic Setup](#agentic-setup).

| Platform | How to Connect | Plans | Private Repos | Refresh | Permissions / Caveats |
|----------|----------------|-------|---------------|---------|-----------------------|
| [ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt) | **Apps** / **Plugins** → GitHub | Varies: plan, workspace, surface | Selected repositories | On demand; no index | Read-only; Codex for writes; chat availability varies |
| [Claude](https://support.claude.com/en/articles/10167454-use-the-github-integration) | **+** → **Add from GitHub** | All, including Free; organization policy | Yes | Manual **Sync now** | Files only; no history, PRs or metadata |
| [Gemini](https://support.google.com/gemini/answer/16176929) | **Add files** → **More uploads** → **Import code** | Personal/eligible Workspace; 18+; Keep Activity on | Linked GitHub account | Frozen; re-import to refresh | Computer only; read-only; one repo/chat; 5,000 files / 100 MB; not Gem Knowledge |
| [Grok (web/app)](https://docs.x.ai/grok/connectors) | `grok.com/connectors` → GitHub | All; Business/Enterprise admin provisioning | Authorized repositories | On demand | Repo/issues/PRs/code; writes undocumented; review OAuth grant |
| [Mistral Vibe](https://docs.mistral.ai/vibe/work/connectors) | **Work** → **Connectors** → **GitHub App** | All, including Free; organization policy | Authorized repositories | Real-time / on demand | Search/issues/PR actions; approval required |
| [Perplexity](https://www.perplexity.ai/help-center/en/articles/12275669-github-connector-for-enterprise) | **Settings** → **Connectors** → **GitHub** | Pro, Max, Enterprise Pro/Max | Yes | On demand | Actions; broad grant includes repository deletion/workflow updates; review carefully |

**Google Drive access for `.json` files.** ✅ Supported; ⚠️ supported with connector limits or transition.

| Platform | `.json` via Drive | Plans | Refresh | Notes |
|----------|-------------------|-------|---------|-------|
| [ChatGPT](https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt) | ⚠️ Supported; connector limited | Plus/Pro; enabled Business/Enterprise/Edu | On-demand search; sync on Pro/eligible workspaces | [App capability](https://help.openai.com/en/articles/11487775-apps-in-chatgpt), region and policy limits |
| [Claude](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors) | ✅ Supported | All; organization policy | On demand; re-select changes | [JSON attachments](https://support.claude.com/en/articles/8241126-upload-files-to-claude); only Google Docs stay synced |
| [Gemini](https://support.google.com/gemini/answer/14903178) | ✅ Supported | Signed-in; Workspace policy | Re-select changes | **Add from Drive**; supported-file uploads; plan limits |
| [Grok (web/app)](https://docs.x.ai/grok/connectors/google-drive) | ✅ Supported | All; Business/Enterprise admin provisioning | Real-time / on demand | [JSON supported](https://docs.x.ai/grok/faq); Docs/Sheets/Slides/other files |
| [Mistral Vibe](https://docs.mistral.ai/vibe/work/connectors/knowledge-connectors) | ⚠️ Supported; transition | Legacy: Team/Enterprise; MCP: admin setup | Legacy: scheduled; MCP: tool-dependent | [JSON/files](https://docs.mistral.ai/vibe/work/files-and-canvas); legacy connector being replaced; check Mistral's docs |
| [Perplexity](https://www.perplexity.ai/help-center/en/articles/12870620-connecting-perplexity-with-google-drive) | ✅ Supported | Pro, Max, Enterprise Pro/Max | Real-time search; selected-file sync | Enterprise: My Files sync/high-precision search |

**Note:** Check the linked vendor documentation before setup. Connector availability and behavior change often, and a stale connector can silently serve old training data.

#### ChatGPT (Projects)

Create a Project and add instructions in its settings. Install the GitHub app for the repository owner and select your repository. Name the repository and file path in requests. Otherwise upload to Project Files.

#### ChatGPT (CustomGPT)

Create GPT → Configure. Paste instructions, upload files under Knowledge, and enable Web Browsing for URL fetch.

#### Claude (Projects)

Create a Project and add Project Instructions. Select repository files through the GitHub integration, or upload to Project Knowledge. Enable Web search for public URL fetch.

#### Gemini (Gems)

Create a Gem. Put the project contract in Instructions and `SECTION_11.md`, plus your optional dossier, in Knowledge. Supply current JSON separately. Use ordinary chats for repository import. Do not upload the whole repository as a ZIP; ordinary ZIP upload has a ten-file limit.

#### Grok (web/app)

Create a Project and add instructions. Connect your data using the table above, or upload to Sources.

#### Mistral (Vibe)

Create a Project and add instructions. Connect your data, or upload during project creation.

#### Perplexity

Create a Space or use chat, then add instructions. Connect your data, or upload to the Space.

---

## Testing Your Setup

After configuration, test with:

### Post-Workout Test

> "How was today's workout?"

**Good response includes:**

- ✅ Reads current `latest.json`; loads companion detail only when needed
- ✅ Available session facts: name/type/start, moving/total/paired planned time, distance/ascent, sport-specific speed/pace, terrain, temperature, wind, climbs, power avg/NP/W/kg, max power/peaks, HR/zones, cadence, work, calories, Carbs used and TSS
- ✅ Executed structure, gated diagnostics and subjective fields per the [post-workout template](examples/reports/POST_WORKOUT_REPORT_TEMPLATE.md); peaks describe this activity only
- ✅ Weekly totals, brief Interpretation and every planned Tomorrow session
- ✅ Plain formatting without source-marker clutter or excessive emojis

**Bad response:**

- ❌ Requests accessible data, invents fields or omits available session data
- ❌ Treats peaks as FTP/readiness evidence or whole-session power as main-set power
- ❌ Recommends recovery for normal TSB (-10 to -30) without other triggers

### Pre-Workout Test

> "Good morning, what's my workout today?"

**Good response includes:**
- ✅ Readiness assessment (HRV, RHR, Sleep vs 7d/28d baselines)
- ✅ Load context (TSB, ACWR, Monotony if > 2.3)
- ✅ Capability snapshot (Durability (cycling) 7d + trend, TID drift if not consistent)
- ✅ Today's planned workout details from planned_workouts
- ✅ Go / Modify / Skip recommendation with reasoning

**Bad response:**
- ❌ Skipping readiness check and jumping straight to workout description
- ❌ Missing capability snapshot (Durability (cycling), TID drift)
- ❌ Generic "listen to your body" without referencing actual metrics

### Weather Test

> "weather for my rides"

**Good response includes:**

- ✅ Route names/dates, labelled weather, moving/total time, and matching readable map pages
- ✅ An explicit assumption for unset start times, and one linked attribution naming the actual provider
- ✅ Missing/stale/disabled status, or the no-route message and GPX/TCX hint; Weather at home only with a resolved Place/source and actual fetch capability

**Bad response:**

- ❌ Invented weather, unseen maps or precise section forecasts from an outlook
- ❌ Home weather substituted for a stale route brief

See the [Weather Report template](examples/reports/WEATHER_REPORT_TEMPLATE.md).

### Stable-Context Test

If you use a dossier, ask about something it records:

> "What's in my regular training bottle?"

**Good response includes:**

- ✅ Your recorded bottle/equipment, or a clear statement that the official copy or entry is unavailable
- ✅ On "Which dossier did you read?", the matching authority statement, Official dossier location, revision and last-reviewed date
- ✅ On "How many should I take on my next long ride?", a current JSON/planned-session read before prescribing numbers, or a statement that no session is planned

**Bad response:**

- ❌ A generic answer or earlier-chat value presented as yours
- ❌ A stale or unofficial dossier treated as current

---

## Troubleshooting

Check the source file, the delivered copy, and the AI's current read. Your [web](PROJECT_INSTRUCTIONS_WEB.md) or [agentic](PROJECT_INSTRUCTIONS_AGENTIC.md) instructions define access and freshness rules.

### AI asks for data instead of fetching

Ask which configured paths failed. Check the runtime's actual data directory, connector scope, attached files, or public raw URL and browsing capability. A connected account may lack access to the particular repository.

Reload the project instructions, then ask the AI to identify the file it read and its timestamp/version. If it still sees an old copy, try a fresh conversation.

### 404 error on JSON URLs / Private repo access

Plain `raw.githubusercontent.com` URLs return 404 for private repositories as well as wrong paths. Check the repository, branch and root filename. For private data, select the repository in an authorized connector or authenticate the runtime; organization approval may be needed. If access still fails, upload fresh files as described in [Quick Start](#4-make-files-available-to-your-ai).

### Data appears stale after sync

Compare the source and the AI's `latest.json` using `metadata.last_updated` and a reliable current time. From sync 3.164 it is UTC (Z); an older value without an offset uses the sync machine's local time. Do not guess that timezone; say age cannot be verified when it matters. Expect under 12 hours. At 12-24 hours, mention age when relevant; beyond 24 hours, request refresh for advice needing current data. Continue qualified coaching; lateness alone is never a global stop.

For ordinary coaching, read `source_freshness.warnings`: mention `source_stale` only when its named sources affect the answer. Other warning codes describe sync operation, not bad data. Sync owns cached-source validity; do not rejudge per-source acquisition ages or statuses. Empty warnings and a recent `as_of` do not certify a live feed. Metric dates and native validity rules still apply. See the [field reference](examples/json-examples/README.md#source-freshness).

If the source is old, check sync below. Otherwise replace uploads, refresh/re-import connectors, or let your cloud folder finish syncing. Raw GitHub content can lag a few minutes. Ask for a fresh read in this response; use a new conversation if old values persist.

### Sync workflow not updating JSON

Check the API key, athlete ID and run log; no recent activities can legitimately mean no new activity data.

- **Local:** check the timer, `sync.log` and `source_freshness` for a step-down, pause or provider hold before treating the timer as broken. Keep `.sync_config.json` at the data root and retain `state/` there unless you set a state override. See [request allowance and pauses](examples/json-local-sync/SETUP.md#request-allowance-and-pauses) for the exact pause message and recovery steps.
- **GitHub:** inspect **Actions → Auto-Sync Intervals.icu Data**. Check secrets, Actions minutes and workflow permissions; request **Sync Now** when needed. See [workflow troubleshooting](examples/json-auto-sync/SETUP.md#troubleshooting).
- **On-demand:** trigger the workflow and download its completed `training-data` artifact within seven days, or refresh your connector.
- **Manual:** export again and replace uploads.

For script/workflow replacement, see [Update Notifications](#update-notifications).

### Activities show null or missing fields

Missing device measurements remain unavailable. `terrain_status` and `weather_status` can explain absent data.

Strava-sourced activities may appear in Intervals.icu but reach its API only as stubs under Strava's API terms. Connect Garmin, Wahoo or your device platform directly to Intervals.icu, or upload original activity files so new records arrive from a non-Strava source.

### HRV shows as unavailable on Apple Watch

Readiness needs rMSSD in Intervals.icu's `hrv` field. Apple Health commonly supplies SDNN, which passes through as `hrv_sdnn` for context and never substitutes for rMSSD. SDNN-only records report `rmssd_missing_sdnn_available`.

An upstream tool must supply rMSSD. [Community projects](https://forum.intervals.icu/c/external-projects/14) are not verified or supported by Section 11; allow about a week for a new seven-day baseline. See [Readiness Decision](SECTION_11.md#readiness-decision-v1113).

### Gemini can't access your repo or ignores data

Use Knowledge files for Gems and repository import for ordinary chats. Re-import after changes; check account eligibility and GitHub authorization in [Platform Setup](#platform-setup). Large archives may exceed import limits: see [Archive](examples/json-auto-sync/SETUP.md#archive). If the AI ignores data, ask it to read the root `latest.json` and report `metadata.last_updated`.

### Grok (web/app) can't connect to GitHub

Check [Platform Setup](#grok-webapp), including administrator provisioning in Business/Enterprise. If the connector remains unavailable, upload fresh files; public URL fetch exposes the data described in [Privacy & Security](#privacy--security).

### AI uses the wrong dossier or ignores your preferences

Ask for its authority statement, Official dossier location, revision and last-reviewed date; compare with your official copy. Resolve conflicting copies yourself, then replace or remove superseded ones.

Dossier changes require your exact approval and verified write access, otherwise the AI returns a revised artifact for you to save. Check that its revision increased. The [dossier template](DOSSIER_TEMPLATE.md) explains preference precedence and maintenance.

### AI fabricates metrics or ignores synced data

Reload the project instructions and ask for the protocol version, current `latest.json` timestamp and, if used, dossier revision. Compare them with the source; a confident summary is insufficient. Resolve stale, missing or duplicate copies before continuing.

For a fresh protocol copy, use the [local updater](examples/json-local-sync/SETUP.md#staying-up-to-date), or download the [repository](https://github.com/CrankAddict/section-11) in a format your platform accepts. It contains no private athlete data: supply your own current JSON. Files under `examples/json-examples/` and all `.example.json` files are fictional schema examples, never coaching data.

Detailed causes, companion markers and refresh checks: [source-copy checks](examples/README.md#checking-source-copies).

---

## How It Works

### Section 11 A: AI Coach Guidance Protocol

Defines behavioral rules for AI coaches:

- **No virtual math:** use current logged values
- **Missing data:** read configured sources, then ask if required data is unavailable
- **Tolerances and auditability:** apply the protocol's numeric checks and evidence rules
- **Self-validation:** complete Steps 0–10, including 5b and 6b

See the [AI Self-Validation Checklist](SECTION_11.md#ai-self-validation-checklist).

### Section 11 B: AI Training Plan Protocol

Defines rules for AI systems generating or modifying training plans:

- Phase alignment with macro-cycle
- Volume ceiling validation (±10% of baseline)
- Intensity distribution control (80/20 polarization)
- Session composition rules
- Audit metadata requirements

### Section 11 C: AI Validation Protocol

Records data access, source timestamps, protocol version, passed/failed checks, confidence and missing inputs in structured audit metadata. See the [schema and field definitions](SECTION_11.md#validation-metadata-schema).

### Scientific Foundations

The protocol integrates 19+ validated endurance science frameworks:

| Framework | Application |
|-----------|-------------|
| Seiler's 80/20 Polarized Training | Intensity distribution |
| Gabbett's ACWR (2016) | Retrospective load context, not standalone injury prediction |
| Banister's Impulse-Response | CTL/ATL/TSB dynamics |
| Foster's Monotony & Strain | Overuse detection |
| Issurin's Block Periodization | Phase structure |
| Coggan's Power-Duration Model | Efficiency tracking |
| San Millán's Zone 2 Model | Metabolic health |
| Skiba's Critical Power Model | Fatigue prediction |
| And more... | See Section 11 for full list |

---

## Key Features

### Rolling Phase Logic

Training blocks adapt dynamically using dual-stream phase detection:

```
Build ↔ Base ↔ Deload ↔ Peak → Taper → Recovery
                                  ↑ Race calendar
Overreached (safety gate — triggers from any state)
```

Phase classification combines retrospective history (4-week CTL/ACWR/hard-day trends) with prospective calendar data (planned workouts + race proximity). Confidence scoring (high/medium/low) and reason codes provide full auditability.

### Readiness Thresholds

Examples from the protocol's readiness rules:

| Trigger | Response |
|---------|----------|
| HRV ↓ >20% | Consider easy day / deload |
| RHR ↑ ≥5 bpm | Flag fatigue/illness |
| Current Feel ≥4/5 (solicited) | Adjust volume 30–40% for 3–4 days |
| RI <0.6 | Mandatory deload |

### Progression Triggers

Green-light criteria for safe load increases:

- Durability Index ≥0.97 for 3+ long rides (≥2 h)
- HR drift <3% in aerobic sessions
- Recovery Index ≥0.85 (7-day mean)
- ACWR within 0.8–1.3
- Monotony <2.5
- Current Feel ≤3/5, when solicited

---

## Data Integration

### Intervals.icu (Recommended)

The protocol is designed to work with [Intervals.icu](https://intervals.icu) as the primary data source. Set up a JSON mirror that syncs your fitness metrics, recent activities, wellness data, zone distributions, and planned workouts.

### Derived Metrics

The sync script pre-calculates Section 11-compliant metrics so AI doesn't need to compute them. Key metrics include ACWR, Recovery Index, Monotony/Strain, Grey Zone %, Quality Intensity %, Easy Time Ratio, Benchmark Index, Phase Detection, Seiler TID, Durability (cycling), per-sport curve deltas and main-sport TID Drift; strain alarms use strain_main_sports while legacy strain remains all-sport context.

Zone aggregations (TID, polarization, grey zone %) default to power zones with HR fallback. Configure `ZONE_PREFERENCE` to override per sport, e.g. `run:hr,cycling:power` for runners who prefer HR-based zone analysis. See [auto-sync setup](examples/json-auto-sync/SETUP.md) or [local sync setup](examples/json-local-sync/SETUP.md) for configuration.

See [examples/README.md](examples/README.md) for the full derived metrics table and data output structure.

Report intensity selects main sports independently per period and shows separate power/HR lines with covered weeks and sessions. Pace-only sports can qualify, with zones unavailable until pace mapping is supported. Legacy fields and activity zone_reference retain their meanings. New history blocks appear on normal refresh; missing blocks are unavailable. Optional report_main_sports is an explicit producer configuration, absent by default. See [Report intensity source](SECTION_11.md#report-intensity-source).

### Longitudinal History

The script generates `history.json` with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Includes period summaries, FTP timeline, and data gap detection. `latest.json` covers current coaching. Provide `history.json` for trend, phase or longitudinal questions, and `intervals.json` or `routes.json` (if present) when a task needs them.

### FTP History Tracking

The script maintains `ftp_history.json` to track indoor and outdoor FTP changes over time, enabling Benchmark Index calculation. See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md#ftp-history-tracking) for details.

### Completed Session Structure

`latest.json` includes `interval_data` per recent activity: timeline plan match, scoped compliance evidence and descriptive Intervals.icu detected intervals side by side. `has_structure` points to 14-day detail; only plan-match context survives through 28 days. See [Which interval data to use](SECTION_11.md#which-interval-data-to-use).

Whole-session average power and NP are not main-set power. Unknown, no-plan and descriptive fallback differ; broad plan match does not prove formal compliance. See [Completed Session Structure](SECTION_11.md#completed-session-structure) for interpretation, freshness and limits.

### Interval-Level Data

`intervals.json` holds per-interval power, HR, cadence, zones, timing and W'bal, plus session-level DFA a1 when AlphaHRV recorded. Follow the independent `has_intervals`, `has_dfa` and `has_structure` flags in `latest.json`; an entry alone may be a whole-session RECOVERY placeholder.

Interval/DFA data covers cycling, run, ski, rowing and swim, with a 72-hour scan window and 14-day retention. Structure has separate sport rules. See [Interval Data Mirror](SECTION_11.md#interval-data-mirror-intervalsjson) for fields and interpretation.

### Route & Terrain Data

The script writes `routes.json` on every sync, with terrain analysis for planned events that have GPX/TCX file attachments: distance, elevation, course character, climbs (position, length, average and max gradient), descents and a downsampled polyline. Planned-route climbs support pre-workout reports; completed-activity terrain comes from `latest.json` for post-workout reports. Events with terrain are flagged `has_terrain: true`. Attachments are cached after download and parsing.

### Data Overview

`latest.json` starts with `data_overview`, immediately after `READ_THIS_FIRST` when present: companion files, locations and route/weather/map availability. The AI reads it first; file presence does not guarantee access.

**Upgrading from before 11.80:** GitHub and On-demand users must replace both `sync.py` and `.github/workflows/auto-sync.yml` once. Follow the [upgrade steps](examples/json-auto-sync/SETUP.md#updating-an-existing-repository), retaining custom settings and On-demand's manual-only trigger.

Keep the export folder between runs, including `routes.json` and `route_eta_history.json`. GitHub/On-demand persist these and maps in the repository; their six-JSON download artifact excludes maps and ETA history. Manual uploads need no extra map step. Run one sync process at a time; automated local timers should use `--lockfile`.

### Route Weather

For planned outdoor rides with routes in the next five days, sync forecasts wind relative to travel, gusts, rain and temperature, timed with an estimate calibrated on your outdoor rides when history allows. Pre-workout reports include weather; ask "weather for my rides" anytime. PNG maps appear in `maps/weather/` ([example map](examples/reports/example-route-weather-map.png)). Without a usable route, a fetch-capable AI can give a home forecast.

**On by default.** Disable with `"route_weather": false` in sync config or `SECTION11_ROUTE_WEATHER=0` ([GitHub repository variable](examples/json-auto-sync/SETUP.md#optional-route-weather-variables)). Sampled route coordinates/elevations go to [Open-Meteo](https://open-meteo.com/), with [MET Norway](https://api.met.no/) fallback; providers see the requesting IP, but no credentials, event names or activity history. Open-Meteo's free service is for non-commercial use. Maps reveal your route. Forecasts are planning aids, not safety assessments. See [SECTION_11](SECTION_11.md#weather-data-source) for details.

#### Route weather departure

Without a start time, **10:00 local is assumed** and the AI asks when you leave. Set the time in Intervals.icu or `route_weather_default_start`.

### Saved Workouts Mirror

`saved_workouts.json` mirrors your Intervals.icu folders and complete saved-workout structures for convenient reads through any data path. It is read-only; edits belong in Intervals.icu. Refresh runs on a six-hour throttle and retains the last good copy on failure, so check `refresh.status` before use.

It is inventory, not the Workout Reference Library or proof of historical prescriptions. See [Saved Workouts Mirror](examples/json-examples/README.md#saved-workouts-mirror).

### Update Notifications

**GitHub/On-demand:** the shared output-only workflow sends no update notification. Replace `sync.py` and update workflow changes manually, preserving customizations; see [Updating an Existing Repository](examples/json-auto-sync/SETUP.md#updating-an-existing-repository). The separate configured direct-publishing path can open update issues.

**Local:** sync prints a daily notice when updates are available. Use `python3 section11/examples/sync.py --update`; renames/removals need a second confirmation. Declining or running non-interactively leaves orphaned files. See [Staying Up to Date](examples/json-local-sync/SETUP.md#staying-up-to-date).

### Data Hierarchy

When sources conflict, trust order is:

1. Intervals.icu (primary)
2. JSON Mirror (Tier-1 verified)
3. Athlete-provided values (<7 days old)

The athlete dossier is **not** a rung in this hierarchy. It holds stable private context, never a current metric.

### Other Platforms

Also compatible with any platform that exports structured training data.

---

## Example Use Cases

### Daily Check-In
> "How was today's workout?"

### 7-day Review
> "Analyze my last 7 days against my targets. What's my compliance rate? Any red flags?"

### Progression Decision
> "Have I met the green-light criteria for extending my Friday long ride to 5 hours?"

### Session Analysis
> "Here's my workout file. Did I hit my intervals within tolerance? What does the HR drift tell us?"

---

## Limitations

- **AI still makes mistakes**: This protocol reduces errors but doesn't eliminate them
- **Not a replacement for human coaches**: Best used alongside professional guidance for serious athletes
- **Requires honest data**: Garbage in, garbage out
- **No medical advice**: Consult professionals for health concerns

---

## Contributing

This is an open protocol. Contributions welcome:

- **Bug reports**: Found an inconsistency? Open an issue
- **Framework additions**: Know a validated model that should be included? Propose it
- **Translation**: Help make this accessible in other languages
- **Integration guides**: Built a tool that uses this? Share it

---

## License

This project is licensed under the MIT License; see [LICENSE](LICENSE) for details.

You can:
- Use it for personal or commercial projects
- Copy, modify, and distribute it
- Include it in closed-source or open-source tools

You must:
- Include the copyright notice
- Include the MIT license text in copies or substantial portions of the software

The software is provided "as is", without warranty of any kind.

---

## Acknowledgments

- **[David Tinker](https://intervals.icu)**: Creator of Intervals.icu
- **[Clive King](https://www.cliveking.net/)**: Pioneer of GPT-based endurance coaching and URF
- **[Intervals.icu Forum](https://forum.intervals.icu)** community
- **Researchers** behind the scientific frameworks cited in Section 11

---

## Links

- **Website:** [section11.net](https://section11.net/)
- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Examples:** [examples/](examples/)
- **Report Templates:** [examples/reports/](examples/reports/)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum Thread](https://forum.intervals.icu/t/section-11-open-protocol-for-ai-endurance-coaching-chatgpt-claude-grok-mistral/120602)

---
