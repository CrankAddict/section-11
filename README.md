# Section 11 — AI Coaching Protocol

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An open protocol for deterministic, auditable AI-powered endurance coaching. Built for athletes who want AI coaches that follow science, not speculation.

---

## What Is This?

**Section 11** is a structured framework that enables AI systems (ChatGPT, Claude, Gemini, Grok, Mistral, etc.) to provide evidence-based endurance training advice with full auditability and deterministic reasoning.

### Core Principles

- **Deterministic** — Same inputs produce same outputs
- **Auditable** — Every recommendation cites specific data and frameworks
- **Evidence-based** — Grounded in 15+ peer-reviewed endurance science models
- **Athlete-controlled** — Your data, your thresholds, your goals

---

## What's Included

| File | Description |
|------|-------------|
| [SECTION_11.md](SECTION_11.md) | Complete protocol: AI Coach Guidance (11 A), Training Plan Protocol (11 B), Validation Protocol (11 C) |
| [examples/workout-library/](examples/workout-library/) | Workout Reference Library — 26 session templates that Section 11 B §8 requires AI systems to select from |
| [examples/agentic/](examples/agentic/) | Agentic tools — calendar writes, raw activity stream reads, external API reference — for AI platforms with code execution |
| [examples/json-local-sync/](examples/json-local-sync/) | Local automated sync for agentic platforms — no GitHub needed |
| [examples/dfa_a1/NON_GARMIN.md](examples/dfa_a1/NON_GARMIN.md) | DFA a1 platform support status — documents that the feature requires Garmin + AlphaHRV today, plus discovery commands for Suunto / Karoo / phone-fallback verification |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Blank athlete dossier template — fill in your own data |
| [examples/](examples/) | Full examples directory |
| [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) | Interactive AI-guided setup — paste into any AI chat to get started |
| [manifest.json](manifest.json) | Version tracking — consumed by sync.py for update notifications |
| [LICENSE](LICENSE) | MIT — permissive license, commercial use allowed with attribution |

---

## Privacy & Security

Your data stays on your machine or in repos you control. Section 11 does not run a backend, does not store your data, and does not send your training data, API keys, or chat history anywhere.

---

The setup paths documented here are proven starting points — not the only ways to use Section 11. The protocol is open, and the data is yours. Build what fits you.

For the full experience, an agentic platform with persistent memory and code execution unlocks the complete project. See [Agentic Setup](#agentic-setup).

---

## Quick Start

> **Recommended:** Paste [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) into ChatGPT, Claude, Gemini, or any AI chat, and it will walk you through everything below step by step. This is the easiest path for most users.

You can also follow the step-by-step guides below.

### 1. Create Your Dossier

Copy `DOSSIER_TEMPLATE.md` and fill in your athlete profile (age, weight, goals), equipment, current FTP/HR zones, training schedule, and nutrition protocol.

### 2. Set Up Your Data Sync

Keep your Intervals.icu data fresh for your AI coach automatically.

**[Local sync](examples/json-local-sync/SETUP.md)** — a script on a machine you control syncs your data on a 60-second timer. Your AI reads directly from the filesystem or via a cloud connector (Google Drive, OneDrive — [platform support varies](#platform-setup)).

**[GitHub sync](examples/json-auto-sync/SETUP.md)** — GitHub Actions syncs every 15 minutes to a private repo. Your AI reads via GitHub connector or raw URL.

**[On-demand sync](examples/json-on-demand/SETUP.md)** — trigger a fresh sync from your phone or browser via your repo's README. Download the data as a ZIP artifact. No schedule, no local Python.

**[Manual export](examples/json-manual/SETUP.md)** — run once, upload the file. No automation. Custom ranges available.

### 3. Configure Your AI Platform

Choose your path:

- **[Agentic Platforms](#agentic-setup)** — OpenClaw, Claude Code, Claude Cowork, ChatGPT Codex, Gemini CLI (code execution, push workouts to calendar) ← **full protocol experience**
- **[Web Chat Platforms](#web-chat-setup)** — ChatGPT Projects, Claude Projects, Gemini Gems, Grok, Mistral Le Chat

### 4. Make Files Available to Your AI

Your AI needs access to `SECTION_11.md` (the protocol) and `DOSSIER.md` (your profile). How depends on your setup:

- **Local/agentic:** The AI reads directly from the filesystem.
- **GitHub connector:** If these files are in your connected repo, the AI reads them directly. If only `DOSSIER.md` is in your data repo, upload `SECTION_11.md` separately (or connect the CrankAddict/section-11 repo too).
- **Cloud connector (Google Drive, OneDrive — [platform support varies](#platform-setup)):** If these files are in your synced folder, the AI reads them through the connector.
- **URL fetch (no connector):** If your data repo is public, the AI can fetch raw URLs directly.
- **Manual upload:** Upload both files to your AI platform or project.

---

## Agentic Setup

For AI platforms that can execute code, access the filesystem, and run shell commands. These platforms can read your JSON files directly (no web fetch needed), push planned workouts to your Intervals.icu calendar, and run sync.py locally.

> **Recommended for agentic: [Local sync](examples/json-local-sync/SETUP.md).** sync.py runs on a 60-second timer, the agent reads files directly. Cheapest, fastest, most reliable. No GitHub needed.

> **Alternative: GitHub sync.** A private repo with GitHub Actions gives you multi-device access and backup. Follow the per-platform instructions below.

Your agent needs `SECTION_11.md` (the protocol) and your `DOSSIER.md`. If you cloned the repos locally, the agent reads them from the filesystem. If using GitHub sync, the agent reads them from the repo — no manual upload needed.

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
2. Or connect GitHub via Settings → Connectors → GitHub (or configure via `.mcp.json`)

### ChatGPT Codex

1. Connect your GitHub account at [chatgpt.com/codex](https://chatgpt.com/codex) and authorize your data repo — web and desktop app connect directly
2. Or install the CLI: `npm install -g @openai/codex` — reads from local filesystem

### Gemini CLI

1. Install: `npm install -g @google/gemini-cli` (or `npx @google/gemini-cli`)
2. Clone your data repo locally — Gemini CLI has full filesystem access

### Agentic Tools

Agentic platforms can use the tools in [examples/agentic/](examples/agentic/) for:

- **`push.py`** — write planned workouts to your Intervals.icu calendar (push, list, move, delete), update sport-specific thresholds, annotate activities
- **`pull.py`** — fetch raw per-second activity streams (GPS, altitude, watts, HR, …) when `terrain_summary`/`weather_summary` in `latest.json` aren't enough and the AI needs the underlying track
- **`EXTERNAL_APIS.md`** — endpoint reference for Strava, MET Norway, Open-Meteo, and Intervals.icu streams + weather, used by agentic flows for pre-ride enrichment

These all require code execution — web chat platforms cannot use them.

See [examples/agentic/README.md](examples/agentic/README.md) for setup, commands, and workout syntax.

---

## Web Chat Setup

For AI platforms accessed through a browser — no code execution, no terminal. These platforms use web search or GitHub connectors to fetch your JSON data.

### Project Instructions

Add these instructions to your AI Project/Space settings:

```
# AI Coach Instructions

You are my endurance coach. Follow Section 11 protocol strictly.

## DATA ACCESS:
Read data using the first method that works:
0. **Attached files** — If JSON data files are provided directly in the conversation, use those
1. **Connected repo/filesystem** — If data files are available via connector (GitHub, Google Drive, OneDrive — platform support varies) or local filesystem, read latest.json, history.json, intervals.json, and routes.json directly
2. **URL fetch** — Fetch https://raw.githubusercontent.com/[USERNAME]/[REPO]/main/latest.json (append ?date= with today's date). Same for history.json
3. If activities don't match today's date, re-fetch or re-read before concluding no data exists
4. Load intervals.json when analyzing a specific activity with `has_intervals: true` or `has_dfa: true` — use for interval compliance, pacing, cardiac drift, recovery quality, DFA a1 session-level interpretation
5. Load routes.json when a planned event has `has_terrain: true` — use for route analysis, terrain-adjusted pacing, pre-ride briefing

Do NOT ask me for data — read or fetch it yourself.

## SOURCE HIERARCHY:
1. **JSON data** — Current metrics from latest.json (READ/FETCH FIRST) + longitudinal data from history.json + interval detail from intervals.json (on-demand) + route/terrain data from routes.json (when events have GPX/TCX attachments)
2. **Section 11 protocol** (attached) — Coaching rules, thresholds, metric hierarchy
3. **Dossier** — Athlete profile, zones, goals
4. **Report templates** — Fetch from https://github.com/CrankAddict/section-11/tree/main/examples/reports if not attached

Do NOT search web for training advice. Section 11 is the authority.

## OUTPUT FORMAT:
No citations, no source markers, no parenthetical references. Raw data and analysis only.

**Post-workout reports** use structured line-by-line format per session (not bullets). Flow:
1. Data timestamp
2. One-line summary
3. Session block(s) — one per activity, line-by-line:
   Activity type & name, start time, duration (actual vs planned), distance, power (avg/NP), power zones (%), Grey Zone (Z3) %, Quality (Z4+) %, HR (avg/max), HR zones (%), cadence, decoupling (with label), EF (when power + HR available), Variability Index (with label), calories (kcal), carbs used (g), TSS (actual vs planned)
4. Weekly totals: Polarization, Durability (7d/28d + trend), TID 28d (+ drift), TSB, CTL, ATL, Ramp rate, ACWR, Hours, TSS
5. Overall: Coach note (2–4 sentences — compliance, quality observations, load context, recovery note)

Omit fields only if data unavailable for that activity type.

**Pre-workout reports** must include: readiness (HRV, RHR, Sleep vs baselines), load context (TSB, ACWR, Monotony if > 2.3), capability snapshot (durability 7d + trend, TID drift if not consistent), today's planned workout, Go/Modify/Skip recommendation.

## RULES:
- Follow Section 11 validation checklist (Step 0: Data Source Fetch)
- No virtual math on pre-computed metrics — use fetched values for CTL, ATL, TSB, ACWR, RI, zones, etc. Custom analysis from raw data is fine when pre-computed values don't cover the question
- TSB −10 to −30 is typically normal — don't recommend recovery unless other triggers present
- Metric hierarchy: Tier 1 (RI, HRV, RHR, Sleep) → Tier 2 (Stress Tolerance, Load-Recovery Ratio, ACWR) → Tier 3 (diagnostics)
- Brief when metrics are normal. Detailed when thresholds are breached or I ask "why"

## DOCUMENTS:
- SECTION_11.md — AI coaching protocol (attached, in connected repo, or fetch from CrankAddict/section-11)
- DOSSIER.md — Profile, zones, goals (attached or in connected data repo)
```

**If using local sync:** The AI reads files from the data directory. No URL editing needed. See [local sync setup](examples/json-local-sync/SETUP.md) for project instructions tailored to filesystem access.

**If using a connector (GitHub, Google Drive, OneDrive — [platform support varies](#platform-setup)):** The AI reads files directly — no URL editing needed. If you committed `DOSSIER.md` to your data repo, the connector provides your data and dossier in one connection. `SECTION_11.md` can be uploaded separately or accessed via a second connector to the CrankAddict/section-11 repo.

**If using URL fetch:** Replace `[USERNAME]/[REPO]` with your GitHub data mirror path.

### Platform Setup

Most major AI platforms now have native GitHub connectors that can access private repos directly. This means you no longer need a public repo or manual file uploads in most cases.

**GitHub connector status for web chat platforms.** Agentic platforms (OpenClaw, Claude Code, Codex, etc.) have full GitHub access including workflow dispatch — see [Agentic Setup](#agentic-setup).

| Platform | GitHub Connector | Private Repos | Can Trigger Actions | Plan Notes |
|----------|-----------------|---------------|---------------------|------------|
| ChatGPT | Settings → Apps → GitHub | Yes | No (read-only)¹ | Varies by plan and experience |
| Claude | Settings → Connectors → GitHub | Yes | No (read-only)² | All plans including Free |
| Gemini | + → Import code / Connected Apps | Yes (link account) | No (read-only snapshot)³ | Account/region dependent — see Gemini docs |
| Grok | Settings → Connected Apps | Yes | No (read-only) | Grok Business/Enterprise; consumer tier availability TBD |
| Mistral | Side panel → Intelligence → Connectors → GitHub | Yes | No (full read/write, no dispatch) | All tiers including free |
| Perplexity | Connectors → GitHub | Yes | No (full read/write, no dispatch) | Pro, Max, and Enterprise |

**Google Drive connector status for web chat platforms (.json files).** For users on the [local sync](examples/json-local-sync/SETUP.md) path who want their AI to read data files via Google Drive.

| Platform | Google Drive (.json) | How to Connect | Plan Notes |
|----------|---------------------|----------------|------------|
| Gemini | ✅ | + → Drive (enable Workspace extensions) | Free tier works |
| Perplexity | ✅ | Settings → Connectors → Google Drive | Pro, Max, and Enterprise |
| ChatGPT | ⚠️ | Settings → Apps → Google Drive | Workspace accounts only — not personal Gmail |
| Claude | ✅ | Settings → Connectors → Google Drive | All plans including Free |
| Grok | ✅ | Settings → Connected Apps → Google Drive | Business/Enterprise only |
| Mistral | ⚠️ | Side panel → Connectors → Google Drive | Beta — Team & Enterprise; admin setup required |

**Note:** Cloud storage connectors are still rolling out across platforms. Availability may change by plan, region, and account type. Check your platform's current connector settings if something listed here doesn't appear.

#### ChatGPT (Projects)

1. Create a Project
2. Add instructions to Project settings
3. **GitHub connector:** Settings → Apps → GitHub → Connect → authorize repos. Once connected, ChatGPT reads your private data repo directly — and any files in it (including `DOSSIER.md` if you committed it).
4. **No connector?** Upload SECTION_11.md and DOSSIER.md to "Project Files". If using the connector but `SECTION_11.md` isn't in your data repo, upload it separately (or connect the CrankAddict/section-11 repo too).

#### ChatGPT (CustomGPT)

1. Create GPT → Configure
2. Paste instructions in "Instructions" field
3. Upload files under "Knowledge"
4. Enable "Web Browsing" in Capabilities

#### Claude (Projects)

1. Create a Project
2. Add instructions to "Project Instructions"
3. **GitHub connector:** Click "+" in Project Knowledge → search/paste your repo URL → select files. Or connect via Settings → Connectors → GitHub. Available on all plans including Free.
4. **No connector?** Upload SECTION_11.md and DOSSIER.md to "Project Knowledge". If using the connector but `SECTION_11.md` isn't in your data repo, upload it separately (or connect the CrankAddict/section-11 repo too).
5. Enable "Web search" in settings if using URL-based fetch instead of the connector

#### Gemini (Gems)

1. Create Gem
2. Paste instructions in instructions field
3. **GitHub connector:** Click **+** → **Import code**, paste the repo URL, and authorize. This also works for Gems. For private repos, authorize your GitHub account when prompted.
4. **No connector?** Paste Section 11 content into the instructions field and upload dossier separately. If using the connector but `SECTION_11.md` isn't in your data repo, upload it separately.

> **Note:** Not all Google accounts have the same access. Gemini's capabilities vary by account type, Workspace edition, and region. If Gemini can't access your repo, see [Troubleshooting](#troubleshooting).

#### Grok

1. Create Project
2. Add instructions to Project configuration
3. **GitHub connector:** Settings → Connected Apps → GitHub → Connect. Available on Grok Business and Enterprise plans; consumer tier availability TBD.
4. **No connector?** Upload SECTION_11.md and DOSSIER.md to "Sources". If using the connector but some files aren't in your data repo, upload those separately.

#### Mistral (Le Chat)

1. Create New Project
2. Add instructions
3. **GitHub connector:** Open side panel → Intelligence → Connectors → find GitHub in the directory → Connect and authorize. Available on all tiers including free.
4. **No connector?** Upload SECTION_11.md and DOSSIER.md during project creation. If using the connector but some files aren't in your connected repo, upload those separately.

#### Perplexity

1. Create a Space (or use standard chat)
2. Add instructions
3. **GitHub connector:** Available on Pro, Max, and Enterprise plans via App Connectors.
4. **No connector?** Upload SECTION_11.md and DOSSIER.md to the Space. Free users without connector access should use URL-based fetch (requires public repo) or upload files manually.

---

## Testing Your Setup

After configuration, test with:

### Post-Workout Test

> "How was today's workout?"

**Good response includes:**
- ✅ Fetched both latest.json and history.json automatically (no asking for it)
- ✅ Session summary with all fields (type, start time, duration, power, HR, TSS, cadence, decoupling, EF, zones, carbs, energy)
- ✅ Training load context (TSB, CTL, ATL, weekly totals)
- ✅ Brief interpretation
- ✅ No "(GitHub)" or URL citations
- ✅ No excessive emojis
- ✅ No false recovery warnings for normal TSB (-10 to -30)

**Bad response:**
- ❌ "I don't have access to your data, please provide..."
- ❌ Missing session fields
- ❌ "(GitHub)" citations throughout
- ❌ "Your TSB is -23, consider recovery" (when no other triggers present)

### Pre-Workout Test

> "Good morning, what's my workout today?"

**Good response includes:**
- ✅ Readiness assessment (HRV, RHR, Sleep vs 7d/28d baselines)
- ✅ Load context (TSB, ACWR, Monotony if > 2.3)
- ✅ Capability snapshot (durability 7d + trend, TID drift if not consistent)
- ✅ Today's planned workout details from planned_workouts
- ✅ Go / Modify / Skip recommendation with reasoning

**Bad response:**
- ❌ Skipping readiness check and jumping straight to workout description
- ❌ Missing capability snapshot (durability, TID drift)
- ❌ Generic "listen to your body" without referencing actual metrics

---

## Troubleshooting

### AI asks for data instead of fetching

- Verify web search/browsing is enabled for your platform
- Check your JSON URL is correct and publicly accessible (or that your GitHub connector is properly authorized)
- Try starting a fresh conversation — some platforms cache instructions per-session
- If using a GitHub connector, verify the connector shows as "Connected" in your platform's settings

### 404 error on JSON URLs / Private repo access

Most AI platforms now have GitHub connectors that can access private repos directly. Check the [Platform Setup](#platform-setup) table for your platform's connector path.

If your platform doesn't support connectors or you can't get them working: use a public repo, upload `latest.json`, `history.json`, `intervals.json`, and `routes.json` (if present) manually to your AI Project/Space, or use an [agentic platform](#agentic-setup) with GitHub access configured.

### Data appears stale after sync

- Try a fresh conversation (some platforms cache per-session)
- Manually append a different query param: `...latest.json?v=2`
- If using a GitHub connector, click "Sync now" or re-import to pull latest changes

### Sync workflow not updating JSON

- Check GitHub Actions ran successfully in the Actions tab
- Verify Intervals.icu API key is valid
- Check workflow permissions are set to "Read and write" (Settings → Actions → General → Workflow permissions)
- See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md) for workflow-specific issues

### Activities show null or missing fields

If your device syncs through Strava, the API returns stripped data. Strava's API terms restrict detailed fields when accessed through third-party APIs — Intervals.icu shows everything in the UI, but the API returns empty fields.

**Fix:** Connect your device (Garmin, Wahoo, etc.) directly to Intervals.icu in Settings → Connections. Keep Strava connected if you want, but the training data needs to come in direct.

### Gemini can't access your repo or ignores data

- Enable the GitHub extension: gemini.google.com → Settings → Extensions (Connected Apps) → turn on GitHub
- If it's a private repo, make sure your GitHub account is linked — you'll be prompted during import, or check Connected Apps settings
- Try referencing the repo directly in chat using `@GitHub`
- Gemini capabilities vary by Google account type, Workspace edition, and region — not all accounts have the same access

### Grok can't connect to GitHub

The GitHub connector for Grok requires a Grok Business or Enterprise plan. If it's not available in your Settings → Connected Apps, upload files manually or use a public repo with URL-based fetch.

### AI fabricates metrics or ignores synced data

This can happen when the AI fails to fetch or parse your JSON data, when the context window overflows, or when the platform's web search doesn't reliably retrieve raw JSON.

**Nuclear option:** Download the full [section-11 repo](https://github.com/CrankAddict/section-11) as a zip and upload it directly into your AI Project, Gem, Space, or chat. This bypasses all fetch/connector issues and gives the AI the protocol and templates in one package. You'll still need to provide your own `latest.json`, `history.json`, `intervals.json`, `routes.json` (if present), and `DOSSIER.md` separately.

---

## How It Works

### Section 11 A — AI Coach Guidance Protocol

Defines behavioral rules for AI coaches:

- **No virtual math** — AI must use your actual logged values, not estimates
- **Explicit data requests** — If data is missing, AI asks rather than assumes
- **Tolerance compliance** — Recommendations stay within ±3W / ±1bpm / ±1% variance
- **Framework citations** — Every recommendation references specific science
- **11-point validation checklist** — AI self-validates before responding (Step 0–10)

### Section 11 B — AI Training Plan Protocol

Defines rules for AI systems generating or modifying training plans:

- Phase alignment with macro-cycle
- Volume ceiling validation (±10% of baseline)
- Intensity distribution control (80/20 polarization)
- Session composition rules
- Audit metadata requirements

### Section 11 C — AI Validation Protocol

Standardized metadata schema for audit trails:

```json
{
  "validation_metadata": {
    "data_source_fetched": true,
    "json_fetch_status": "success",
    "protocol_version": "11.24",
    "checklist_passed": [0, 1, 2, 3, 4, 5, 6, "6b", 7, 8, 9, 10],
    "checklist_failed": [],
    "data_timestamp": "2026-01-23T10:02:07Z",
    "data_age_hours": 2.3,
    "confidence": "high",
    "missing_inputs": [],
    "frameworks_cited": ["Seiler 80/20", "Gabbett ACWR"]
  }
}
```

### Scientific Foundations

The protocol integrates 19+ validated endurance science frameworks:

| Framework | Application |
|-----------|-------------|
| Seiler's 80/20 Polarized Training | Intensity distribution |
| Gabbett's ACWR (2016) | Load progression, injury prevention |
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

Automatic load adjustment based on recovery status:

| Trigger | Response |
|---------|----------|
| HRV ↓ >20% | Easy day / deload |
| RHR ↑ ≥5 bpm | Flag fatigue/illness |
| Feel ≥4/5 | Reduce volume 30-40% |
| RI <0.6 | Mandatory deload |

### Progression Triggers

Green-light criteria for safe load increases:

- Durability Index ≥0.97 for 3+ long rides
- HR drift <3% in aerobic sessions
- Recovery Index ≥0.85 (7-day mean)
- ACWR within 0.8–1.3
- Feel ≤3/5

---

## Data Integration

### Intervals.icu (Recommended)

The protocol is designed to work with [Intervals.icu](https://intervals.icu) as the primary data source. Set up a JSON mirror that syncs your fitness metrics, recent activities, wellness data, zone distributions, and planned workouts.

### Derived Metrics

The sync script pre-calculates Section 11-compliant metrics so AI doesn't need to compute them. Key metrics include ACWR, Recovery Index, Monotony/Strain, Grey Zone %, Quality Intensity %, Easy Time Ratio, Benchmark Index, Phase Detection, Seiler TID, Aggregate Durability, and TID Drift.

Zone aggregations (TID, polarization, grey zone %) default to power zones with HR fallback. Configure `ZONE_PREFERENCE` to override per sport — e.g. `run:hr,cycling:power` for runners who prefer HR-based zone analysis. See [auto-sync setup](examples/json-auto-sync/SETUP.md) or [local sync setup](examples/json-local-sync/SETUP.md) for configuration.

See [examples/README.md](examples/README.md) for the full derived metrics table and data output structure.

### Longitudinal History

The script generates `history.json` with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Includes period summaries, FTP timeline, and data gap detection. Provide `latest.json`, `history.json`, `intervals.json`, and `routes.json` (if present) to your AI coach for the most complete analysis.

### FTP History Tracking

The script maintains `ftp_history.json` to track indoor and outdoor FTP changes over time, enabling Benchmark Index calculation. See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md#ftp-history-tracking) for details.

### Interval-Level Data

The script generates `intervals.json` with per-interval segment data (power, HR, cadence, zone, decoupling, W'bal) for recent structured sessions, plus per-session DFA a1 rollups when AlphaHRV recorded. Activities in `latest.json` carry two independent flags: `has_intervals: true` (structured segments) and `has_dfa: true` (AlphaHRV session). Either flag indicates an entry in `intervals.json`. Incrementally cached with a 72h scan window and 14-day retention. Only activities in whitelisted sport families (cycling, run, ski, rowing, swim) with either detected interval structure or AlphaHRV data are included.

### Route & Terrain Data

The script generates `routes.json` with terrain analysis for planned events that have GPX/TCX file attachments. Includes total distance, elevation, course character classification, climb detection (Cat 4 through HC), descent detection, and a 500m-downsampled polyline with elevation. Events with terrain data are flagged with `has_terrain: true` in `latest.json`. Cached by attachment ID — files are only downloaded and parsed once.

### Update Notifications

The sync script checks for upstream updates using `manifest.json`. **GitHub Actions users** get a GitHub Issue created in their data repo when updates are available. **Local users** see a one-line notification during sync runs (once per day) and can run `--update` to pull changes. See [json-local-sync](examples/json-local-sync/SETUP.md#staying-up-to-date) for details.

### Data Hierarchy

When sources conflict, trust order is:

1. Intervals.icu (primary)
2. JSON Mirror (Tier-1 verified)
3. Athlete-provided values (<7 days old)
4. Dossier baselines (fallback)

### Other Platforms

Also compatible with any platform that exports structured training data.

---

## Example Use Cases

### Daily Check-In
> "How was today's workout?"

### Weekly Review
> "Analyze my last 7 days against my targets. What's my compliance rate? Any red flags?"

### Progression Decision
> "Have I met the green-light criteria for extending my Friday long ride to 5 hours?"

### Session Analysis
> "Here's my workout file. Did I hit my intervals within tolerance? What does the HR drift tell us?"

---

## Limitations

- **AI still makes mistakes** — This protocol reduces errors but doesn't eliminate them
- **Not a replacement for human coaches** — Best used alongside professional guidance for serious athletes
- **Requires honest data** — Garbage in, garbage out
- **No medical advice** — Consult professionals for health concerns

---

## Contributing

This is an open protocol. Contributions welcome:

- **Bug reports** — Found an inconsistency? Open an issue
- **Framework additions** — Know a validated model that should be included? Propose it
- **Translation** — Help make this accessible in other languages
- **Integration guides** — Built a tool that uses this? Share it

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

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

- **[David Tinker](https://intervals.icu)** — Creator of Intervals.icu
- **[Clive King](https://www.cliveking.net/)** — Pioneer of GPT-based endurance coaching and URF
- **[Intervals.icu Forum](https://forum.intervals.icu)** community
- **Researchers** behind the scientific frameworks cited in Section 11

---

## Links

- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Examples:** [examples/](examples/)
- **Report Templates:** [examples/reports/](examples/reports/)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum Thread](https://forum.intervals.icu/t/section-11-open-protocol-for-ai-endurance-coaching-chatgpt-claude-grok-mistral/120602)

---