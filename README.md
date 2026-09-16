# Section 11 - AI Coaching Protocol

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
| [examples/workout-library/](examples/workout-library/) | Workout Reference Library: 26 session templates that Section 11 B §8 requires AI systems to select from |
| [examples/agentic/](examples/agentic/) | Agentic tools (calendar writes, raw activity stream reads, external API reference) for runtimes with verified access, configured credentials and a tested execution path |
| [examples/agentic/fit-file-and-merger/](examples/agentic/fit-file-and-merger/) | FIT File & Merger: a reusable reference architecture for multi-source FIT fusion, device identity, verification, recovery and platform-specific duplicate cleanup. Documentation, no runnable scripts in this phase |
| [examples/json-local-sync/](examples/json-local-sync/) | Local automated sync for runtimes that can reach your filesystem (no GitHub needed) |
| [examples/dfa_a1/NON_GARMIN.md](examples/dfa_a1/NON_GARMIN.md) | DFA a1 platform support status: documents that the feature requires Garmin + AlphaHRV today, plus discovery commands for Suunto / Karoo / phone-fallback verification |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Template for your athlete dossier: the stable private context your AI cannot read from your data |
| [examples/](examples/) | Full examples directory |
| [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) | Interactive AI-guided setup: paste into any AI chat to get started |
| [manifest.json](manifest.json) | Version tracking (consumed by sync.py for update notifications) |
| [LICENSE](LICENSE) | MIT: permissive license, commercial use allowed with attribution |

---

## Privacy & Security

`sync.py` always redacts `metadata.athlete_id`, but it does not anonymize the exported dataset. Output may include activity names and IDs, date of birth, age, sex, height, location, timezone, athlete notes, wellness and training data, route coordinates/polylines, and your saved workouts: their names, descriptions, folder names and full structures, which reveal planning intent such as goal events, target adaptations and prescribed intensities. Store the output in a private location. Publishing the files in a public repository exposes that information.

Section 11 operates no hosted backend. Data moves only through services you explicitly configure. Credentials are sent only to the service they authenticate, and only when that service is configured: `sync.py` sends your Intervals.icu key in an Authorization header to Intervals.icu, and your GitHub token to GitHub when publishing or issue creation is configured. Credentials are never included in exported or published JSON. Any AI, runtime, model, connector, repository or storage providers actually involved have their own processing and retention terms, which Section 11 neither sets nor can promise.

---

The setup paths documented here are proven starting points, not the only ways to use Section 11. The protocol is open, and the data is yours. Build what fits you.

An AI with persistent memory and a runtime that can execute code reaches more of the project. Filesystem reach, code execution and write access are separate capabilities, each verified per target; none of them follows from a platform's label. See [Agentic Setup](#agentic-setup).

---

## Quick Start

> **Recommended:** Paste [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) into ChatGPT, Claude, Gemini, or any AI chat, and it will walk you through everything below step by step. This is the easiest path for most users.

You can also follow the step-by-step guides below.

### 1. Create Your Dossier: your stable private context

Copy `DOSSIER_TEMPLATE.md` and fill in the context your AI cannot read from your data: background, equipment, stable constraints, health and injury history, tested fueling, and how you prefer to be coached. Current thresholds and load always come from your JSON. You can start coaching before the dossier exists; a missing dossier limits personalisation, not safety.

### 2. Set Up Your Data Sync

Keep your Intervals.icu data fresh for your AI coach automatically.

**[Local sync](examples/json-local-sync/SETUP.md)**: a script on a machine you control syncs your data on a 60-second timer. An AI whose runtime can reach that filesystem reads the files directly; otherwise it reads them through a cloud connector (Google Drive, OneDrive; [platform support varies](#platform-setup)).

**[GitHub sync](examples/json-auto-sync/SETUP.md)**: GitHub Actions syncs every 15 minutes to a private repo. Your AI reads via GitHub connector or raw URL.

**[On-demand sync](examples/json-on-demand/SETUP.md)**: trigger a fresh sync from your phone or browser via your repo's README. Download the data as a ZIP artifact. No schedule, no local Python.

**[Manual export](examples/json-manual/SETUP.md)**: run once, upload the file. No automation. Custom ranges available. Remember the upload is frozen. Re-export and replace it before a report if your data has moved on.

### 3. Configure Your AI Platform

Choose your path:

- **[Agentic Platforms](#agentic-setup)**: OpenClaw, Claude Code, Claude Cowork, ChatGPT Codex, Gemini CLI (code execution, push workouts to calendar). Grok Bot and Hermes Agent have the capability class but are **experimental**; capability class is not a support promise. Calendar writes need verified access, configured credentials and a tested integration.
- **[Web Chat Platforms](#web-chat-setup)**: ChatGPT Projects, Claude Projects, Gemini Gems, Grok (web/app), Mistral Vibe

### 4. Make Files Available to Your AI

Your AI needs access to `SECTION_11.md` (the protocol), plus `DOSSIER.md` (your stable private context and preferences) if you use one. How depends on your setup:

- **Local/agentic:** Where the runtime can reach your filesystem, the AI reads the files directly.
- **GitHub connector:** If these files are in your connected repo, the AI reads them directly. If only `DOSSIER.md` is in your data repo, upload `SECTION_11.md` separately (or connect the CrankAddict/section-11 repo too).
- **Cloud connector (Google Drive, OneDrive; [platform support varies](#platform-setup)):** If these files are in your synced folder, the AI reads them through the connector.
- **URL fetch (no connector):** If your data repo is public, the AI can fetch raw URLs directly.
- **Manual upload:** Upload `SECTION_11.md`, and `DOSSIER.md` if you use one, to your AI platform or project. Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.

---

## Agentic Setup

For runtimes that can execute code, access the filesystem, and run shell commands. These can read your JSON files directly (no web fetch needed) and run sync.py locally. Pushing planned workouts to your Intervals.icu calendar is a separate capability: it needs verified access, configured credentials and a tested integration, and follows from none of the above.

> **Recommended where the runtime reaches your filesystem: [Local sync](examples/json-local-sync/SETUP.md).** sync.py runs on a 60-second timer, the agent reads files directly. Cheapest, fastest, most reliable. No GitHub needed.

> **Alternative: GitHub sync.** A private repo with GitHub Actions gives you multi-device access and backup. Follow the per-platform instructions below.

Your agent needs `SECTION_11.md` (the protocol), plus your `DOSSIER.md` if you use one. If you cloned the repos locally, the agent reads them from the filesystem. If using GitHub sync, the agent reads them from the repo (no manual upload needed).

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
2. Clone your data repo locally; Gemini CLI has full filesystem access

### Grok Bot (experimental)

Runs on a user-scoped shared computer and authenticates through Cursor. It has the agentic capability class, but it is **experimental**: it is not validated end to end against the Section 11 pipeline, and capability class is not a support promise. Any write must be verified against the specific target before it is used or assumed.

All Bots on your account share one cloud computer: files, browser sessions and command-line credentials are not isolated. Deleting a Bot does not clear shared files or browser sessions. Cloud storage is required and Legacy Privacy Mode is unavailable. Check your [xAI](https://docs.x.ai/) and Cursor privacy settings before adding a sensitive dossier.

### Hermes Agent (experimental)

Reads the filesystem of its runtime host, not your machine. It has the agentic capability class, but it is **experimental** and not validated end to end against the Section 11 pipeline.

Point it at your data with a pointer file rather than copying files onto the host. Its working directory is not guaranteed to be where you think it is. Set paths explicitly and check the resolved working directory before relying on a relative path.

### Agentic Tools

Runtimes with verified access, configured credentials and a tested execution path can use the tools in [examples/agentic/](examples/agentic/) for:

- **`push.py`**: write planned workouts to your Intervals.icu calendar (push, list, move, delete), update sport-specific thresholds, annotate activities
- **`pull.py`**: fetch raw per-second activity streams (GPS, altitude, watts, HR, …) when `terrain_summary`/`weather_summary` in `latest.json` aren't enough and the AI needs the underlying track
- **`EXTERNAL_APIS.md`**: endpoint reference for Strava, MET Norway, Open-Meteo, and Intervals.icu streams + weather, used by agentic flows for pre-ride enrichment

These all require code execution; web chat platforms cannot use them.

See [examples/agentic/README.md](examples/agentic/README.md) for setup, commands, and workout syntax.

**Advanced reference.** [examples/agentic/fit-file-and-merger/](examples/agentic/fit-file-and-merger/) documents a reusable reference architecture for building one authoritative activity from multiple source recordings: base and donor selection, field-by-field precedence, device identity rewriting, pre-upload validation, post-upload verification, recovery, and platform-specific duplicate cleanup. This phase contains documentation only, with no runnable scripts, so it is readable on any platform rather than requiring code execution. The working implementation it describes is cycling-tested; other sources and sports need their own implementation and validation.

---

## Web Chat Setup

For AI platforms reached through a browser or app, with no runtime-accessible filesystem. These sessions reach your data through a connector or authenticated repository, an upload or attachment, or a URL fetch.

### Project Instructions

Copy the block between the fences in [`PROJECT_INSTRUCTIONS_WEB.md`](PROJECT_INSTRUCTIONS_WEB.md) into your AI Project, Space, Gem, or custom instructions.

That file is the canonical web and connector contract. It states which sessions it covers, what a delivery path does and does not confer, and how to handle stale or conflicting copies. If your AI runs on a filesystem it can read, use [`PROJECT_INSTRUCTIONS_AGENTIC.md`](PROJECT_INSTRUCTIONS_AGENTIC.md) instead.

**Running local sync?** A runtime that reads your filesystem is agentic, not web chat; use [`PROJECT_INSTRUCTIONS_AGENTIC.md`](PROJECT_INSTRUCTIONS_AGENTIC.md) and see [local sync setup](examples/json-local-sync/SETUP.md).

**If using a connector (GitHub, Google Drive, OneDrive; [platform support varies](#platform-setup)):** The AI reads files through the connector (no URL editing needed). Refresh behavior varies by platform; follow the [Platform Setup](#platform-setup) guidance and refresh or re-import when required. A connector supplies data only; it confers no write authority, and every further capability is separate and must be verified. Committing `DOSSIER.md` to your data repo provides your data and dossier in one connection, and is safe only while that repo stays private. `SECTION_11.md` can be uploaded separately or accessed via a second connector to the CrankAddict/section-11 repo.

**If using URL fetch:** Replace `[USERNAME]/[REPO]` with your GitHub data mirror path.

### Platform Setup

Most major web-chat platforms can access private GitHub repositories, but access and freshness are separate questions. Some connectors query live data, some maintain an index, and some require a manual sync or re-import. A private connector replaces a public repo only when its refresh model keeps `latest.json` and `history.json` current enough for your workflow.

**GitHub connector status for web-chat platforms.** A runtime with verified repository access, configured credentials and a tested integration may also use authenticated GitHub tools and workflow dispatch; see [Agentic Setup](#agentic-setup). This table covers the web-chat connector experience.

*GitHub table: the ChatGPT and Gemini rows were re-verified 2026-09-15 against vendor documentation. The other rows and the Google Drive table were verified 2026-08-16 using vendor documentation and, where available, hands-on testing. Plans, interfaces, permissions, and regional availability can change.*

| Platform | How to Connect | Plans | Private Repos | Refresh | Permissions / Caveats |
|----------|----------------|-------|---------------|---------|-----------------------|
| [ChatGPT](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt) | **Apps** or **Plugins** → GitHub | Varies by plan, workspace, and product surface | Yes, once the GitHub app is installed for the owning account and the repository is selected | On demand; no synced GitHub index | Read-only in ChatGPT; use Codex for repository writes. Availability may include standard chat, deep research, or agent workflows, depending on plan and product surface; some accounts have GitHub in deep research or agent mode but not standard chat. |
| [Claude](https://support.claude.com/en/articles/10167454-use-the-github-integration) | **+** → **Add from GitHub** | All plans including Free; organization policy may restrict | Yes | Manual **Sync now** | Files only; no commit history, pull requests, or other repository metadata. |
| [Gemini](https://support.google.com/gemini/answer/16176929) | **Add files** → **More uploads** → **Import code** (ordinary chats) | Personal accounts and qualifying Workspace accounts with Gemini apps enabled; 18+ with Keep Activity on | Yes, with the GitHub account linked to your Google Account | Frozen at import; re-import to refresh | Import on a computer; one repository per chat, up to 5,000 files / 100 MB; read-only. Not a Gem Knowledge source. |
| [Grok (web/app)](https://docs.x.ai/grok/connectors) | `grok.com/connectors` → GitHub | All users; Business/Enterprise requires admin provisioning | Authorized repositories | On demand | Public documentation identifies repository, issue, pull-request, and code access but does not state whether the GitHub connector can write; review the OAuth grant before authorizing. |
| [Mistral Vibe](https://docs.mistral.ai/vibe/work/connectors) | **Work** → **Connectors** → **GitHub App** | All plans including Free; organization policy may restrict | Authorized repositories | Real-time / on demand | Can search repositories, review issues, and manage pull requests; actions require approval. |
| [Perplexity](https://www.perplexity.ai/help-center/en/articles/12275669-github-connector-for-enterprise) | **Settings** → **Connectors** → **GitHub** | Pro, Max, Enterprise Pro, Enterprise Max | Yes | On demand | Can perform actions. The OAuth grant includes unusually broad scopes, including repository deletion and workflow updates; review it carefully. |

**Google Drive access for `.json` files.** `✅` means the Drive-to-chat JSON path is supported. `⚠️` means JSON works, but connector availability or lifecycle is limited.

| Platform | `.json` via Drive | Plans | Refresh | Notes |
|----------|-------------------|-------|---------|-------|
| [ChatGPT](https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt) | ⚠️ Supported; connector limited | Plus and Pro; Business, Enterprise, and Edu when enabled | On-demand file search; continuous sync on Pro and supported workspace plans | JSON is supported. [App capability](https://help.openai.com/en/articles/11487775-apps-in-chatgpt), region, and workspace policy may limit availability. |
| [Claude](https://support.claude.com/en/articles/10166901-use-google-workspace-connectors) | ✅ Supported | All users; organization policy may restrict | On demand; re-select after changes | Claude supports [JSON files](https://support.claude.com/en/articles/8241126-upload-files-to-claude) and Drive attachments. Only Google Docs are explicitly documented as staying synchronized. |
| [Gemini](https://support.google.com/gemini/answer/14903178) | ✅ Supported | Signed-in users; Workspace policy may restrict | Re-select after changes | **Add from Drive** uses Gemini's supported-file upload path. Google documents support for most file types; limits vary by plan. |
| [Grok (web/app)](https://docs.x.ai/grok/connectors/google-drive) | ✅ Supported | All users; Business/Enterprise requires admin provisioning | Real-time / on demand | xAI documents [JSON file support](https://docs.x.ai/grok/faq), while the Drive connector reads Docs, Sheets, Slides, and other file types. |
| [Mistral Vibe](https://docs.mistral.ai/vibe/work/connectors/knowledge-connectors) | ⚠️ Supported; connector transition | Team and Enterprise for the legacy indexed connector; replacement MCP requires admin setup | Legacy: scheduled sync; MCP: tool-dependent | Vibe supports [JSON files](https://docs.mistral.ai/vibe/work/files-and-canvas) and Drive file reading. The legacy Knowledge Connector is scheduled for removal at the end of August 2026 in favor of an admin-added MCP connector. |
| [Perplexity](https://www.perplexity.ai/help-center/en/articles/12870620-connecting-perplexity-with-google-drive) | ✅ Supported | Pro, Max, Enterprise Pro, Enterprise Max | Real-time standard search; selected-file sync also available | JSON is explicitly listed. Enterprise adds My Files sync and high-precision search. |

**Note:** Check the linked vendor documentation before setup. Connector availability and behavior change often, and a stale connector can silently serve old training data.

#### ChatGPT (Projects)

1. Create a Project
2. Add instructions to Project settings
3. **GitHub connector:** Open **Apps** or **Plugins** → GitHub → Connect, install the ChatGPT GitHub app for the account or organization that owns your data repository, and select the repository. Availability varies by plan, workspace, and product surface. ChatGPT retrieves repository content on demand and keeps no synced index, so name the repository and file path when you ask for a report. The connector is read-only.
4. **No connector?** Upload SECTION_11.md, and DOSSIER.md if used, to "Project Files". If using the connector but `SECTION_11.md` isn't in your data repo, upload it separately (or connect the CrankAddict/section-11 repo too). Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.

#### ChatGPT (CustomGPT)

1. Create GPT → Configure
2. Paste instructions in "Instructions" field
3. Upload files under "Knowledge"
4. Enable "Web Browsing" in Capabilities

#### Claude (Projects)

1. Create a Project
2. Add instructions to "Project Instructions"
3. **GitHub connector:** Click **+** in a chat or the project's Files section → **Add from GitHub** → select files. Private repositories are supported. Click **Sync now** before a report when the repository has changed.
4. **No connector?** Upload SECTION_11.md, and DOSSIER.md if used, to "Project Knowledge". If using the connector but `SECTION_11.md` isn't in your data repo, upload it separately (or connect the CrankAddict/section-11 repo too). Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.
5. Enable "Web search" in settings if using URL-based fetch instead of the connector

#### Gemini (Gems)

1. Create a Gem.
2. **Instructions:** paste the block between the fences in `PROJECT_INSTRUCTIONS_WEB.md`. Do not paste the full Section 11 protocol into the instructions field.
3. **Knowledge:** add `SECTION_11.md` as a knowledge file, plus `DOSSIER.md` if you use one. Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the Gem.
4. **Current JSON:** supply `latest.json`, and any other file the task needs, through the delivery path you configured (see the tables above).
5. **GitHub repository (ordinary Gemini chat):** Google documents repository import for chats, not as Gem Knowledge. On a computer, open **Add files** → **More uploads** → **Import code**, paste the repo URL, and link your GitHub account if prompted. Private repositories are supported, but the imported repository is frozen: changes do not sync, so re-import it before the next report.

Do not upload the complete Section 11 repository as a ZIP. Gemini's ordinary ZIP upload accepts at most ten files.

> **Note:** Not all Google accounts have the same access. Gemini's capabilities vary by account type, Workspace edition, and region. If Gemini can't access your repo, see [Troubleshooting](#troubleshooting).

#### Grok (web/app)

1. Create Project
2. Add instructions to Project configuration
3. **GitHub connector:** Open `grok.com/connectors` → **New Connector** → GitHub → authorize. Connectors are available to all Grok (web/app) users; Business and Enterprise workspaces require an administrator to provision them first.
4. **No connector?** Upload SECTION_11.md, and DOSSIER.md if used, to "Sources". If using the connector but some files aren't in your data repo, upload those separately. Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.

#### Mistral (Vibe)

1. Create New Project
2. Add instructions
3. **GitHub connector:** Switch to **Work** → **Connectors** → **GitHub App** → Connect and authorize. Vibe can manage pull requests as well as read repository data, and asks for approval before actions.
4. **No connector?** Upload SECTION_11.md, and DOSSIER.md if used, during project creation. If using the connector but some files aren't in your connected repo, upload those separately. Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.

#### Perplexity

1. Create a Space (or use standard chat)
2. Add instructions
3. **GitHub connector:** **Settings** → **Connectors** → GitHub. Available on Pro, Max, Enterprise Pro, and Enterprise Max. Review the OAuth grant before authorizing: it includes broad administrative scopes, repository deletion, and GitHub Actions workflow updates.
4. **No connector?** Upload SECTION_11.md, and DOSSIER.md if used, to the Space. Free users without connector access can use URL-based fetch, which requires a public repo (see [Privacy & Security](#privacy--security) for what publishing exposes), or upload files manually. Uploaded files are frozen at upload. Replace the old copy when you update one, and don't leave two versions in the store.

---

## Testing Your Setup

After configuration, test with:

### Post-Workout Test

> "How was today's workout?"

**Good response includes:**
- ✅ Read latest.json automatically (no asking for it); history.json only when the question needs trend or longitudinal context
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

Most data problems sit in one of five places: the AI has not loaded your project instructions, it cannot reach the files, the source files are old, the copy it sees is old, or it is answering from an earlier read. Your contract, [`PROJECT_INSTRUCTIONS_WEB.md`](PROJECT_INSTRUCTIONS_WEB.md) or [`PROJECT_INSTRUCTIONS_AGENTIC.md`](PROJECT_INSTRUCTIONS_AGENTIC.md), defines the delivery paths: a runtime-accessible filesystem (agentic runtimes), a connector or authenticated repository, an upload or attachment, and URL fetch. Current connect and refresh details for each platform are in [Platform Setup](#platform-setup).

### AI asks for data instead of fetching

If every configured path fails, the contracts require the AI to say which paths it tried and what failed, and then ask you. Ask for that report, then check the failing path:

- **Filesystem:** the data directory the runtime actually used. Some runtimes override the configured working directory.
- **Connector or repository:** the connector is available in this project or chat and authorized for the repository or folder that holds your files. A connector shown as connected can still lack access to a specific repository.
- **Upload:** the files are attached to this project or conversation.
- **URL fetch:** web fetch or browsing is enabled, the repository is public, and the raw URLs in your project instructions, or in your dossier's source configuration when you use one, are correct.

After you replace a file, ask the AI to report the marker for that file: the `Protocol Version` for `SECTION_11.md`, `metadata.last_updated` for `latest.json`, or the dossier revision and last-reviewed date for `DOSSIER.md` when you use one. Start a fresh conversation only if it still reports the old copy.

### 404 error on JSON URLs / Private repo access

A `raw.githubusercontent.com` URL can be read without credentials only from a public repository. A private repository returns `404 Not Found`, the same response as a wrong path.

- **Public repository:** check the username, repository, branch (`main`) and file name, and confirm that the sync has committed `latest.json` to the repository root. See [Privacy & Security](#privacy--security) for what a public repository publishes.
- **Private repository:** use a connector or authenticated repository instead. If the connector is connected but the repository is missing, check that the platform's GitHub app is installed for the account or organization that owns the repository and that the repository is selected. An organization or workspace administrator may need to approve or enable it. See [Platform Setup](#platform-setup).
- **No working connector:** upload `latest.json`, plus `history.json` for trend questions and `intervals.json`, `routes.json` or `saved_workouts.json` when the task needs them. Upload `SECTION_11.md`, and your dossier if you use one, when the connector was supplying them. Replace older copies rather than adding new ones.
- **Agentic runtime:** clone the data repository or authenticate the runtime to it. See [Agentic Setup](#agentic-setup).

### Data appears stale after sync

Check each layer in turn.

1. **Source.** `latest.json` records `metadata.last_updated` on every sync, as the clock time of the machine that ran it, without a timezone offset. Section 11 expects it to be under 24 hours old and asks for a refresh beyond 48 hours. If it is old, see [Sync workflow not updating JSON](#sync-workflow-not-updating-json). Other files follow their own schedules: `history.json` is regenerated about every four weeks and whenever `sync.py` changes, with its age reported under `history` in `latest.json`, and `saved_workouts.json` reports `refresh.status`.
2. **Delivered copy.** Uploads are frozen at upload; re-export and replace them. Connectors differ. Claude's GitHub integration refreshes the selected files when you click **Sync now**. A Gemini repository import never updates and must be imported again. ChatGPT retrieves permitted repository content on demand, with availability depending on plan and product surface. For other platforms, follow [Platform Setup](#platform-setup) and the linked vendor documentation. When the source is a cloud-drive folder, your computer must also finish syncing it before a connector can see the change.
3. **Fetch cache (URL fetch).** Raw GitHub content can stay cached for a few minutes after a commit. Wait, then fetch again.
4. **Conversation.** An AI can keep answering from an earlier read. Every cited metric must come from a read in the current response, so ask it to re-read `latest.json` and report `metadata.last_updated`. Start a fresh conversation if it keeps using old values.

### Sync workflow not updating JSON

Start with the sync path you use. On every path, check that your Intervals.icu API key and athlete ID are valid; a period without activities legitimately adds none.

- **Local sync:** check the timer (`launchctl list | grep section11` on macOS, `systemctl --user status section11-sync.timer` on Linux, or your scheduler's status), read `sync.log`, keep `.sync_config.json` in the data directory root rather than inside `section11/`, and run once by hand with `--debug`. See [Verification and Troubleshooting](examples/json-local-sync/SETUP.md#verification-and-troubleshooting).
- **GitHub sync:** open your data repository's **Actions** tab and check the latest **Auto-Sync Intervals.icu Data** run; its log names the cause, such as a missing secret. Scheduled runs can be delayed, and in a public repository GitHub disables scheduled workflows after 60 days without repository activity. Private repositories consume your account's GitHub Actions allowance, so check your current usage against [GitHub's billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions). If a push fails with a permission error, check **Settings → Actions → General → Workflow permissions**. The copies of `sync.py` and `auto-sync.yml` in your data repository never update themselves; see [Update Notifications](examples/json-auto-sync/SETUP.md#update-notifications) and [the GitHub sync troubleshooting](examples/json-auto-sync/SETUP.md#troubleshooting).
- **On-demand sync:** nothing runs until you trigger the workflow. Confirm that the run completed, then download the `training-data` artifact, which is kept for seven days, and replace your uploads, or refresh your connector as your platform requires.
- **Manual export:** nothing updates by itself. Run `sync.py` again and replace the uploaded files.

### Activities show null or missing fields

An empty field is not always a fault. A field stays empty when the device did not record it, and some fields report unavailability explicitly, such as `terrain_status` and `weather_status`.

Activities imported through Strava are different. Strava's API terms do not allow Intervals.icu to pass Strava-sourced activities on through its own API, so Intervals.icu shows you the activity but its API returns only a stub, with little or no detail for the export.

**Fix:** connect your device platform (Garmin, Wahoo and similar) directly to Intervals.icu, or upload the original activity files, so that new activities arrive from a non-Strava source.

### HRV shows as unavailable on Apple Watch

Readiness uses the Intervals.icu wellness `hrv` field as rMSSD. SDNN is stored separately in `hrvSDNN`; `latest.json` passes it through as `hrv_sdnn` for context, and Section 11 never substitutes it for rMSSD. When a usable rMSSD value is present, readiness uses it whichever device produced it. When the latest wellness record has only SDNN, `readiness_decision.signals.hrv` is `unavailable` with `reason: "rmssd_missing_sdnn_available"`. Apple Health has long reported HRV as SDNN, which is why Apple Watch users often see this.

**Fix:** a tool upstream of Intervals.icu must write rMSSD to its `hrv` field. Community projects are discussed in the [Intervals.icu forum's External Projects category](https://forum.intervals.icu/c/external-projects/14); none is verified or supported by Section 11. A new source may bring no history, and the readiness baseline uses the last seven days, so allow about a week of values before relying on it.

### Gemini can't access your repo or ignores data

- Repository import is documented for ordinary Gemini chats, not as Gem Knowledge. In a Gem, add `SECTION_11.md` under Knowledge instead; see [Gemini (Gems)](#gemini-gems).
- A repository import never updates. Import it again before a report if the repository has changed.
- Account type, age, activity settings and Workspace policy affect availability, and a private repository needs your GitHub account linked to your Google Account. See the Gemini row in [Platform Setup](#platform-setup).
- An import is limited in files and size. The GitHub sync adds a timestamped copy of `latest.json` under `archive/` on every run, so a long-running data repository can outgrow the limit.
- If Gemini answers without using the data, ask it to open the root `latest.json` and report `metadata.last_updated` before anything else.

### Grok (web/app) can't connect to GitHub

Connectors are available to all Grok (web/app) users. Add GitHub at `grok.com/connectors` → **New Connector**. In Business and Enterprise workspaces an administrator must provision connectors first. If it's still unavailable, upload files manually, or use a public repo with URL-based fetch; see [Privacy & Security](#privacy--security) for what publishing exposes.

### AI uses the wrong dossier or ignores your preferences

`DOSSIER.md` is optional. When you use one, it holds your stable private athlete context: long-term goals, health context, constraints, equipment and source configuration. It also holds your portable coaching and communication defaults and your athlete-specific preferences and behavioral overrides, which apply below platform safety rules, your explicit current request and task-specific Section 11 requirements. It is never a source of current metrics, readiness, zones, phase or schedule; those come from your data. Without a dossier the AI loses that personalization but can still coach safely from your data.

- Ask the AI to report the dossier's authority statement, **Official dossier location**, **Dossier revision** and **Last reviewed**, and compare them with your official copy.
- If it finds more than one copy, it must not merge them. It compares their authority statements, locations, revisions and last-reviewed dates, and asks you which copy is official. Once you have decided, replace or remove the superseded copies.
- The AI may propose dossier changes. It applies one only after your exact approval, and only where write access to the official copy has been verified; otherwise it returns a revised file for you to save. After saving, check that the revision number increased.
- Keep the dossier private. Never place it in a public repository.

### AI fabricates metrics or ignores synced data

This can happen when the AI fails to fetch or parse your JSON data, when the context window overflows, when a platform or runtime update drops your project instructions, when a connector, import or upload serves missing, stale or duplicate files, or when the AI answers from an earlier read or from memory.

**First, reload the rules.** Start a fresh conversation if needed and tell the AI to re-read and follow your project instructions ([`PROJECT_INSTRUCTIONS_WEB.md`](PROJECT_INSTRUCTIONS_WEB.md) or [`PROJECT_INSTRUCTIONS_AGENTIC.md`](PROJECT_INSTRUCTIONS_AGENTIC.md)). `SECTION_11.md` governs coaching decisions and reports, your data is the only source of current metrics, and `DOSSIER.md` supplies stable context and preferences as described above. If a file the task needs is unavailable, the AI must say so rather than guess.

**Then verify what it read.** Ask it to report these values and compare them with the source:

- The `Protocol Version` in `SECTION_11.md`.
- `metadata.last_updated` in the root `latest.json`, not in a copy under `archive/`.
- The dossier revision and last-reviewed date, when you use a dossier.
- For the task at hand: `history.age_days` in `latest.json` for trend work, `generated_at` in `intervals.json` or `routes.json` when those files are needed, and `refresh.status` in `saved_workouts.json` for saved-workout questions.
- Whether it can see more than one copy of any of these files.

Exact matches are evidence that it read the files; a confident summary is not. If anything is wrong or missing, work through [Data appears stale after sync](#data-appears-stale-after-sync).

**Fallback: provide a fresh protocol copy.** On agentic setups, clone or update the [section-11 repo](https://github.com/CrankAddict/section-11); with local sync, run `python3 section11/examples/sync.py --update`. Otherwise download the repository as a zip and attach or import it in the format your platform accepts; some platforms limit how many files a ZIP may contain. The bundled files under `examples/json-examples/` end in `.example.json`; every value in them is fictional, and they must never be used as athlete data. The repository contains none of your private athlete data. The AI still needs your current `latest.json` for current coaching, `history.json` for trend work, `intervals.json`, `routes.json` or `saved_workouts.json` when the task needs them, and your `DOSSIER.md`, if you use one, for your stored personalization and preferences. Uploaded copies are frozen at upload. Replace them when Section 11 changes, and don't leave two copies in the store.

---

## How It Works

### Section 11 A: AI Coach Guidance Protocol

Defines behavioral rules for AI coaches:

- **No virtual math**: AI must use your actual logged values, not estimates
- **Explicit data requests**: If data is missing, AI asks rather than assumes
- **Tolerance compliance**: Recommendations stay within ±3W / ±1bpm / ±1% variance
- **Framework citations**: Every recommendation references specific science
- **11-point validation checklist**: AI self-validates before responding (Step 0–10)

### Section 11 B: AI Training Plan Protocol

Defines rules for AI systems generating or modifying training plans:

- Phase alignment with macro-cycle
- Volume ceiling validation (±10% of baseline)
- Intensity distribution control (80/20 polarization)
- Session composition rules
- Audit metadata requirements

### Section 11 C: AI Validation Protocol

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

Zone aggregations (TID, polarization, grey zone %) default to power zones with HR fallback. Configure `ZONE_PREFERENCE` to override per sport, e.g. `run:hr,cycling:power` for runners who prefer HR-based zone analysis. See [auto-sync setup](examples/json-auto-sync/SETUP.md) or [local sync setup](examples/json-local-sync/SETUP.md) for configuration.

See [examples/README.md](examples/README.md) for the full derived metrics table and data output structure.

### Longitudinal History

The script generates `history.json` with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Includes period summaries, FTP timeline, and data gap detection. `latest.json` covers current coaching. Provide `history.json` for trend, phase or longitudinal questions, and `intervals.json` or `routes.json` (if present) when a task needs them.

### FTP History Tracking

The script maintains `ftp_history.json` to track indoor and outdoor FTP changes over time, enabling Benchmark Index calculation. See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md#ftp-history-tracking) for details.

### Interval-Level Data

The script generates `intervals.json` with per-interval segment data (power, HR incl. min, cadence, zone, timing, W'bal start/end) for recent structured sessions, plus per-session DFA a1 rollups when AlphaHRV recorded. Activities in `latest.json` carry two independent flags: `has_intervals: true` (structured segments) and `has_dfa: true` (AlphaHRV session). Either flag indicates an entry in `intervals.json`. Incrementally cached with a 72h scan window and 14-day retention. Only activities in whitelisted sport families (cycling, run, ski, rowing, swim) with either detected interval structure or AlphaHRV data are included. Note that Intervals.icu emits a whole-session `RECOVERY` placeholder on many unstructured activities, which counts as "detected structure" for inclusion but sets neither flag; follow `has_intervals` / `has_dfa`, not the presence of an entry.

### Route & Terrain Data

The script generates `routes.json` with terrain analysis for planned events that have GPX/TCX file attachments. Includes total distance, elevation, course character classification, climb detection (Cat 4 through HC), descent detection, and a 500m-downsampled polyline with elevation. Events with terrain data are flagged with `has_terrain: true` in `latest.json`. Cached by attachment ID. Files are only downloaded and parsed once.

### Saved Workouts Mirror

The script generates `saved_workouts.json`, a read-only mirror of your saved workouts from Intervals.icu: folders and complete workout definitions, including each workout's structure exactly as Intervals.icu stores it. Intervals.icu remains the source of truth and the only write path; the mirror never writes back. It exists as a faster, cheaper read path than repeated API retrieval, and it makes your saved workouts available to platforms without API access through connectors, repositories, URLs and file uploads. It refreshes on its own 6-hour throttle rather than on every sync, keeps the last good copy when a refresh fails, and reports whether what you are reading was just verified or is a retained older snapshot. See [`examples/json-examples/README.md`](examples/json-examples/README.md#saved-workouts-mirror) for the full description.

### Update Notifications

The sync script checks for upstream updates. Runs that **publish to GitHub with configured credentials** open a GitHub Issue in the data repo when a new release is available; the automated data-mirror workflow does not, since it runs `sync.py` in output-only mode. **Local users** see a one-line notification during sync runs (once per day) and can run `--update` to pull changes. See [json-local-sync](examples/json-local-sync/SETUP.md#staying-up-to-date) for details.

**Renames and removals:** `--update` lists files that no longer exist upstream as orphaned items and asks separately before deleting them. Approve that prompt to complete a rename or removal. Declining it, or running non-interactively, leaves the old files in place.

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

### Weekly Review
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

- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Examples:** [examples/](examples/)
- **Report Templates:** [examples/reports/](examples/reports/)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum Thread](https://forum.intervals.icu/t/section-11-open-protocol-for-ai-endurance-coaching-chatgpt-claude-grok-mistral/120602)

---
