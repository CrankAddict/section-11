---
name: section-11
description: Evidence-based endurance cycling coaching protocol (v11.10). Use when analyzing training data, reviewing sessions, generating pre/post-workout reports, planning workouts, answering training questions, or giving cycling coaching advice. Always fetch athlete JSON data before responding to any training question.
---

# Section 11 — AI Coaching Protocol

## First Use Setup

On first use:

1. **Check for DOSSIER.md** in the workspace
   - If not found, fetch template from: https://raw.githubusercontent.com/CrankAddict/section-11/main/DOSSIER_TEMPLATE.md
   - Ask the athlete to fill in their data (zones, goals, schedule, etc.)
   - Save as DOSSIER.md in the workspace

2. **Set up JSON data source**
   - Athlete creates a private GitHub repo for training data, or keeps files locally
   - Set up automated sync from Intervals.icu to `latest.json` and `history.json`
   - Save both raw URLs in DOSSIER.md under "Data Source" (or local file paths if running locally)
   - `latest.json` — current 7-day snapshot + 28-day derived metrics
   - `history.json` — longitudinal data (daily 90d, weekly 180d, monthly 3y)
   - See: https://github.com/CrankAddict/section-11#2-set-up-your-data-mirror-optional-but-recommended
   - Or for interactive guided setup: have the athlete paste `SETUP_ASSISTANT.md` into any AI chat

3. **Configure heartbeat settings**
   - Fetch template from: https://raw.githubusercontent.com/CrankAddict/section-11/refs/heads/main/openclaw/HEARTBEAT_TEMPLATE.md
   - Ask athlete for their specific values:
     - Location for weather checks (city/area)
     - Timezone
     - Valid outdoor riding hours
     - Weather thresholds (min temp, max wind, max rain %)
     - Preferred notification hours
   - Save as HEARTBEAT.md in the workspace

Do not proceed with coaching until dossier, data source, and heartbeat config are complete.

## Protocol

Fetch and follow: https://raw.githubusercontent.com/CrankAddict/section-11/main/SECTION_11.md

**Current version:** 11.5

## External Sources

All external files referenced by this skill (`sync.py`, `SECTION_11.md`, templates, setup guides) are maintained in the open-source [CrankAddict/section-11](https://github.com/CrankAddict/section-11) repository and can be inspected there.

## Data Hierarchy
1. JSON data (always fetch latest.json first, then history.json for longitudinal context)
2. Protocol rules (SECTION_11.md)
3. Athlete dossier (DOSSIER.md)
4. Heartbeat config (HEARTBEAT.md)

## Required Actions
- Fetch latest.json before any training question
- Fetch history.json when trend analysis, phase context, or longitudinal comparison is needed
- No virtual math on pre-computed metrics — use fetched values for CTL, ATL, TSB, ACWR, RI, zones, etc. Custom analysis from raw data is fine when pre-computed values don't cover the question.
- Follow Section 11 C validation checklist before generating recommendations
- Cite frameworks per protocol (checklist item #10)

## Write Capabilities

If `push.py` is available in the data repo, the skill can manage the athlete's Intervals.icu calendar and training data:
- **push** — write planned workouts to calendar
- **list** — show planned workouts for a date range
- **move** — reschedule a workout to a different date
- **delete** — remove a workout from the calendar
- **set-threshold** — update sport-specific thresholds (FTP, indoor FTP, LTHR, max HR, threshold pace). Only after validated test results, never from estimates
- **annotate** — add notes to completed activities (description by default, `--chat` for messages panel) or planned workouts (`NOTE:` prepended to description)

All write operations default to preview mode — nothing is written without `--confirm`. Execution via GitHub Actions dispatch (uses existing repository secrets configured by the athlete) or local CLI. See `examples/agentic/README.md` for full usage, workout syntax, and template ID mappings.

Only available on platforms that can execute code or trigger GitHub Actions (OpenClaw, Claude Code, Cowork, etc.). Web chat users cannot use this.

## Report Templates

Use standardized report formats from `/examples/reports/`:
- **Pre-workout:** Readiness assessment, Go/Modify/Skip recommendation — see `PRE_WORKOUT_TEMPLATE.md`
- **Post-workout:** Session metrics, plan compliance, weekly totals — see `POST_WORKOUT_TEMPLATE.md`
- **Brevity rule:** Brief when metrics are normal. Detailed when thresholds are breached or athlete asks "why."

Fetch templates from:
- https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/reports/PRE_WORKOUT_TEMPLATE.md
- https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/reports/POST_WORKOUT_TEMPLATE.md

## Heartbeat Operation

On each heartbeat, follow the checks and scheduling rules defined in your HEARTBEAT.md:
- Daily: training/wellness observations (from latest.json), weather (only if conditions are good)
- Weekly: background analysis (use history.json for trend comparison)
- Self-schedule next heartbeat with randomized timing within notification hours

## Security & Privacy

**Data ownership & storage**
All training data is stored where the user chooses: on their own device or in a Git repository they control. This project does not run any backend service, cloud storage, or third-party infrastructure. Nothing is uploaded anywhere unless the user explicitly configures it.

The skill reads from: user-configured JSON data sources, DOSSIER.md, and HEARTBEAT.md in the workspace. It writes to: DOSSIER.md and HEARTBEAT.md in the workspace (during first-use setup only).

**Anonymization**
`sync.py` (maintained in the source repository) anonymizes raw training data. The skill does not perform anonymization itself. Only aggregated and derived metrics (CTL, ATL, TSB, zone distributions, power/HR summaries) are used by the AI coach.

**Network behavior**
The skill performs simple HTTP GET requests to fetch:
- The coaching protocol (`SECTION_11.md`) from this repository
- Report templates from this repository
- Athlete training data (`latest.json`, `history.json`) from user-configured URLs

It does **not** send API keys, LLM chat histories, or any user data to external URLs. All fetched content comes from sources the user has explicitly configured.

**Recommended setup: local files or private repos**
The safest and simplest setup is fully local: export your data as JSON and point the skill at files on your device (see `examples/json-manual/`). If you use GitHub, use a **private repository**. See `examples/json-auto-sync/SETUP.md` for automated sync setup including private repo usage with agents.

**Protocol and template URLs**
The default protocol and template URLs point to this repository. The risk model is standard open-source supply-chain.

**Heartbeat / automation**
The heartbeat mechanism is fully opt-in. It is not enabled by default and nothing runs automatically unless the user explicitly configures it. When enabled, it performs a narrow set of actions: read training data, run analysis, write updated summaries/plans to the user's chosen location.

**Private repositories & agent access**
Section 11 does not implement GitHub authentication. It reads files from whatever locations the runtime environment can already access:
- Running locally: reads from your filesystem
- Running in an agent (OpenClaw, Claude Cowork, etc.) with GitHub access configured: can read/write repos that the agent's token/SSH key allows

Access is entirely governed by credentials the user has already configured in their environment.
