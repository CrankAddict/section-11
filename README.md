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
| [examples/agentic/](examples/agentic/) | Write planned workouts to Intervals.icu calendar — for agentic AI platforms with code execution |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Blank athlete dossier template — fill in your own data |
| [examples/](examples/) | JSON sync setup, report templates, README template, example files |
| [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) | Interactive AI-guided setup — paste into any AI chat to get started |
| [changelog.json](changelog.json) | Version tracking — consumed by sync.py for update notifications |
| [LICENSE](LICENSE) | MIT — permissive license, commercial use allowed with attribution |

---

## Privacy & Security

Your data stays on your machine or in repos you control. Section 11 does not run a backend, does not store your data, and does not send your training data, API keys, or chat history anywhere.

---

## Quick Start

> **Recommended:** Paste [SETUP_ASSISTANT.md](SETUP_ASSISTANT.md) into ChatGPT, Claude, Gemini, or any AI chat, and it will walk you through everything below step by step. This is the easiest path for most users.

If you prefer to set things up manually, follow the steps below.

### 1. Create Your Dossier

Copy `DOSSIER_TEMPLATE.md` and fill in your athlete profile (age, weight, goals), equipment, current FTP/HR zones, training schedule, and nutrition protocol.

### 2. Set Up Your Data Mirror (Optional but Recommended)

Create a JSON endpoint with your current Intervals.icu data so AI coaches can access real-time metrics without manual input each session.

```
https://raw.githubusercontent.com/[USERNAME]/[REPO]/main/latest.json
https://raw.githubusercontent.com/[USERNAME]/[REPO]/main/history.json
```

See [examples/](examples/) for setup guides: [automated sync](examples/json-auto-sync/SETUP.md) (recommended) or [manual export](examples/json-manual/SETUP.md).

### 3. Configure Your AI Platform

Choose your path:

- **[Web Chat Platforms](#web-chat-setup)** — ChatGPT Projects, Claude Projects, Gemini Gems, Grok, Mistral Le Chat
- **[Agentic Platforms](#agentic-setup)** — OpenClaw, Claude Code, Claude Cowork, ChatGPT Codex, Gemini CLI (code execution, push workouts to calendar)

### 4. Upload Files

Upload these files to your AI platform's knowledge base:

| File | Purpose |
|------|---------|
| `SECTION_11.md` | The coaching protocol (required) |
| `DOSSIER.md` | Your athlete profile (required) |

---

## Web Chat Setup

For AI platforms accessed through a browser — no code execution, no terminal. These platforms use web search or GitHub connectors to fetch your JSON data.

### Project Instructions

Add these instructions to your AI Project/Space settings:

```
# AI Coach Instructions

You are my endurance cycling coach. Follow Section 11 protocol strictly.

## DATA ACCESS:
1. Note today's date
2. Fetch: https://raw.githubusercontent.com/[you]/[repo]/main/latest.json
3. Fetch: https://raw.githubusercontent.com/[you]/[repo]/main/history.json
4. If activities don't match today's date, re-fetch before concluding no data exists

Do NOT ask me for data — fetch it yourself.

## RULES:
- Section 11 protocol is the authority — do NOT search the web for training advice
- No virtual math — use fetched values for CTL, ATL, TSB, ACWR, RI, zones, etc.
- TSB −10 to −30 is normal — don't flag recovery unless other triggers present
- Metric hierarchy: Tier 1 (RI, HRV, RHR, Feel) → Tier 2 (ACWR, Monotony) → Tier 3 (diagnostics)
- No citations, source markers, or parenthetical references — raw data and analysis only
- Brief when metrics are normal. Detailed when thresholds are breached or I ask "why"
- Fetch report templates from https://github.com/CrankAddict/section-11/tree/main/examples/reports if not attached

## DOCUMENTS ATTACHED:
- SECTION_11.md — AI coaching protocol
- DOSSIER.md — Profile, zones, goals
```

**Replace `[you]/[repo]` with your GitHub data mirror path.**

> **Note:** If you're using a platform with a GitHub connector (most platforms now support this), you can skip the fetch URLs and let the connector access your repo directly. The AI will read `latest.json` and `history.json` from your connected repository.

### Platform Setup

Most major AI platforms now have native GitHub connectors that can access private repos directly. This means you no longer need a public repo or manual file uploads in most cases.

**GitHub connector status for web chat platforms.** Agentic platforms (Claude Code, Codex, OpenClaw, etc.) have full GitHub access including workflow dispatch — see [Agentic Setup](#agentic-setup).

| Platform | GitHub Connector | Private Repos | Can Trigger Actions | Plan Notes |
|----------|-----------------|---------------|---------------------|------------|
| ChatGPT | Settings → Apps → GitHub | Yes | No (read-only) | Varies by plan and experience |
| Claude | Settings → Integrations → GitHub | Yes | No (read-only) | All plans including Free |
| Gemini | + → Import code / Connected Apps | Yes (link account) | No (read-only snapshot) | Account/region dependent — see Gemini docs |
| Grok | Settings → Connected Apps | Rolling out | TBD | Plan requirements TBD |
| Mistral | Connectors directory (MCP) | Yes | Not yet (writes supported, dispatch TBD) | All tiers including free |
| Perplexity | App Connectors → GitHub | Yes | No (read-only) | Pro, Max, and Enterprise |

#### ChatGPT (Projects)

1. Create a Project
2. Add instructions to Project settings
3. Upload SECTION_11.md and DOSSIER.md to "Project Files"
4. **GitHub connector:** Settings → Apps → GitHub → Connect → authorize repos. Once connected, ChatGPT can read your private data repo directly.

#### ChatGPT (CustomGPT)

1. Create GPT → Configure
2. Paste instructions in "Instructions" field
3. Upload files under "Knowledge"
4. Enable "Web Browsing" in Capabilities

#### Claude (Projects)

1. Create a Project
2. Add instructions to "Project Instructions"
3. Upload SECTION_11.md and DOSSIER.md to "Project Knowledge"
4. **GitHub connector:** Click "+" in Project Knowledge → search/paste your repo URL → select files. Or connect via Settings → Integrations → GitHub. Available on all plans including Free.
5. Enable "Web search" in settings if using URL-based fetch instead of the connector

#### Gemini (Gems)

1. Create Gem
2. Paste instructions + Section 11 content in instructions field
3. Upload dossier or paste contents
4. **GitHub connector:** In Gemini web chat, click **+** → **Import code**, paste the repo URL, and authorize. This also works for Gems. For private repos, authorize your GitHub account when prompted.

> **Note:** Not all Google accounts have the same access. Gemini's capabilities vary by account type, Workspace edition, and region. If Gemini can't access your repo, see [Troubleshooting](#troubleshooting).

#### Grok

1. Create Project
2. Add instructions to Project configuration
3. Upload files to "Sources"
4. **GitHub connector:** Settings → Connected Apps → GitHub → Connect. Rolling out — availability may vary by plan.

#### Mistral (Le Chat)

1. Create New Project
2. Add instructions and upload files
3. **GitHub connector:** Open side panel → Intelligence → Connectors → find GitHub in the directory → Connect and authorize. Available on all tiers including free.

#### Perplexity

1. Create a Space (or use standard chat)
2. Add instructions and upload files
3. **GitHub connector:** Available on Pro, Max, and Enterprise plans via App Connectors. Free users should use URL-based fetch (requires public repo) or upload files manually.

---

## Agentic Setup

For AI platforms that can execute code, access the filesystem, and run shell commands. These platforms can read your JSON files directly (no web fetch needed), push planned workouts to your Intervals.icu calendar, and run sync.py locally.

> **The most reliable experience is the agentic path:** a private repo with an agent platform that has GitHub access gives the AI direct access to your data and the full protocol without depending on web search or manual uploads.

### OpenClaw (formerly ClawdBot/MoltBot)

Section 11 works well with [OpenClaw](https://github.com/openclaw/openclaw). The combination of persistent memory + autonomous execution + structured validation makes for a capable coaching setup.

1. Install the GitHub skill: `npx skills add https://github.com/openclaw/openclaw --skill github`
2. Authenticate: `gh auth login`
3. For limited access, use a [fine-grained personal access token](https://github.com/settings/tokens?type=beta) scoped to your data repo only

### Claude Code

1. Install the Claude GitHub App at [github.com/apps/claude](https://github.com/apps/claude/installations/select_target) and grant access to your private data repo
2. Or clone the repo locally and work with local files
3. Claude Code has full filesystem access — point it at your data directory

### Claude Cowork

Cowork runs on your local machine and can read files directly from your filesystem.

1. Clone your private data repo locally and grant Cowork access to that folder
2. Or use the GitHub MCP connector in Cowork settings to access repos directly via a personal access token

### ChatGPT Codex

1. Connect your GitHub account via the ChatGPT GitHub connector at [chatgpt.com/codex](https://chatgpt.com/codex)
2. Authorize access to your private training data repo during setup
3. Codex clones the repo into an isolated container and reads `latest.json` and `history.json` directly
4. The Codex CLI works locally with your existing filesystem and Git setup

### Gemini CLI

1. Install: `npm install -g @google/gemini-cli` (or `npx @google/gemini-cli`)
2. Clone your data repo locally — Gemini CLI has full filesystem access
3. Supports MCP extensions for additional tool integration

### Pushing Workouts to Calendar

Agentic platforms can write planned workouts to your Intervals.icu calendar using [push.py](examples/agentic/). This requires code execution — web chat platforms cannot use this feature.

See [examples/agentic/README.md](examples/agentic/README.md) for setup, commands, and workout syntax.

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
- ✅ Load context (TSB, ACWR, Monotony if > 2.0)
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

If your platform doesn't support connectors or you can't get them working: use a public repo, upload `latest.json` and `history.json` manually to your AI Project/Space, or use an [agentic platform](#agentic-setup) with GitHub access configured.

### Data appears stale after sync

- Try a fresh conversation (some platforms cache per-session)
- Manually append a different query param: `...latest.json?v=2`
- If using a GitHub connector, click "Sync now" or re-import to pull latest changes

### Sync workflow not updating JSON

- Check GitHub Actions ran successfully in the Actions tab
- Verify Intervals.icu API key is valid
- Check workflow permissions are set to "Read and write" (Settings → Actions → General → Workflow permissions)
- See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md) for workflow-specific issues

### Gemini can't access your repo or ignores data

- Enable the GitHub extension: gemini.google.com → Settings → Extensions (Connected Apps) → turn on GitHub
- If it's a private repo, make sure your GitHub account is linked — you'll be prompted during import, or check Connected Apps settings
- Try referencing the repo directly in chat using `@GitHub`
- Gemini capabilities vary by Google account type, Workspace edition, and region — not all accounts have the same access

### Grok can't connect to GitHub

The GitHub connector for Grok is still rolling out. If it's not available in your Settings → Connected Apps, upload files manually or use a public repo with URL-based fetch.

### AI fabricates metrics or ignores synced data

This can happen when the AI fails to fetch or parse your JSON data, when the context window overflows, or when the platform's web search doesn't reliably retrieve raw JSON.

**Nuclear option:** Download the full [section-11 repo](https://github.com/CrankAddict/section-11) as a zip and upload it directly into your AI Project, Gem, Space, or chat. This bypasses all fetch/connector issues and gives the AI the protocol and templates in one package. You'll still need to provide your own `latest.json`, `history.json`, and `DOSSIER.md` separately.

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
    "protocol_version": "11.5",
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

The sync script pre-calculates Section 11-compliant metrics so AI doesn't need to compute them. Key metrics include ACWR, Recovery Index, Monotony/Strain, Grey Zone %, Quality Intensity %, Polarisation Index, Benchmark Index, Phase Detection, Seiler TID, Aggregate Durability, and TID Drift.

See [examples/README.md](examples/README.md) for the full derived metrics table and data output structure.

### Longitudinal History

The script generates `history.json` with tiered granularity: daily (90 days), weekly (180 days), and monthly (up to 3 years). Includes period summaries, FTP timeline, and data gap detection. Provide both `latest.json` and `history.json` to your AI coach for the most complete analysis.

### FTP History Tracking

The script maintains `ftp_history.json` to track indoor and outdoor FTP changes over time, enabling Benchmark Index calculation. See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md#ftp-history-tracking) for details.

### Update Notifications

The sync script automatically checks for upstream protocol updates. When a new version of Section 11 is released, a GitHub Issue is created in your data repo.

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

## Roadmap

- [x] Section 11 A/B/C Protocol
- [x] Dossier Template
- [x] JSON sync automation scripts
- [x] Report templates (pre/post workout)
- [x] Longitudinal history generation (tiered granularity)
- [x] Upstream update notifications via GitHub Issues
- [x] Capability metrics (aggregate durability, dual-timeframe TID)

---

## Links

- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Examples:** [examples/](examples/)
- **Report Templates:** [examples/reports/](examples/reports/)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum Thread](https://forum.intervals.icu/t/section-11-open-protocol-for-ai-endurance-coaching-chatgpt-claude-grok-mistral/120602)

---
