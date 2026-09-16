---
name: section-11
description: Evidence-based endurance coaching protocol (v11.69). Use when analyzing training data, reviewing sessions, generating pre/post-workout reports, planning workouts, answering training questions, or giving endurance coaching advice. Always read or fetch athlete JSON data before responding to any training question.
---

# Section 11 - AI Coaching Protocol

## File Locations

Data files (`latest.json`, `history.json`, `intervals.json`, `ftp_history.json`, `routes.json`, `saved_workouts.json`, `DOSSIER.md`, `section11/`) live in the athlete's **data directory**: a runtime-accessible location, typically something like `~/training-data/`. HEARTBEAT.md lives in the **agent workspace**: the directory the agent runs from. These may or may not be the same directory.

The **data directory** is where training data is read. It is not the authority record for the dossier: the authoritative dossier copy is named in the `Official dossier location` field in the dossier's own header block.

Files under any `examples/json-examples/` folder, including `section11/examples/json-examples/`, and any file ending in `.example.json` are fictional schema examples, never athlete data. Never use them for coaching, reports, readiness, planning or athlete metrics, and never fall back to them when a real data file is missing or stale.

## First Use Setup

On first use:

1. **Check for DOSSIER.md** in the data directory
   - If found, read its header block first: authority statement, `Official dossier location`, dossier revision, last reviewed
   - If more than one copy is reachable, do not merge them. Compare revision and last-reviewed date and ask the athlete which is official
   - If not found, check the connected source (if a connector is available)
   - If not found, check uploaded or attached files
   - If not found, check `section11/DOSSIER_TEMPLATE.md`
   - If not found, fetch from: https://raw.githubusercontent.com/CrankAddict/section-11/main/DOSSIER_TEMPLATE.md
   - Offer guided creation first and manual completion second. Ask only for stable private context: long-term goals, health and medication context, allergies and tested fueling, stable constraints, environment and equipment, communication preferences. Do not ask for thresholds, zones, weight or current phase. Those come from current JSON. Do not ask for planned training or the weekly schedule. Those come from current JSON and calendar data
   - Ask the athlete where the file should live, and record it as `Official dossier location`. Keep it in a private location: a local data directory, a private repository, or a private document store. Never place a private dossier in a public data mirror
   - Show the draft and obtain explicit approval before creating the file

2. **Set up JSON data source**
   - **Runtime-accessible filesystem (recommended):** Athlete runs sync.py on a timer, producing `latest.json`, `history.json`, `intervals.json`, `ftp_history.json`, `routes.json` (when events have GPX/TCX attachments) and `saved_workouts.json` in the data directory. The runtime reads them directly. This may be the athlete's own machine or a provider-hosted computer; "agentic" does not mean "local". See `examples/json-local-sync/SETUP.md` for the full pipeline.

   **Platform routing.** Three surfaces, two contracts:

   | Surface | Contract |
   |---|---|
   | Grok (web/app), and other web-chat platforms | `PROJECT_INSTRUCTIONS_WEB.md` |
   | Grok Bot, Hermes Agent, and other agentic runtimes | `PROJECT_INSTRUCTIONS_AGENTIC.md` |

   Grok Bot and Hermes Agent are **experimental**: the capability class fits, but the Section 11 pipeline is not validated end to end on either. Treat support as unproven rather than assured.
   - **Connector or authenticated repository:** the athlete's **private** data source reached through a platform connector, an authenticated repository, or an equivalent credentialed connection. The AI reads files directly (no URLs needed). Committing `DOSSIER.md` and `SECTION_11.md` there provides everything in one connection, and is safe only while the source is private. **This delivery path supplies data only.** It confers no write authority, no ability to trigger actions or workflows, and no script execution; each of those capabilities is separate and must be verified before it is used or assumed.
   - **Upload or attachment:** the athlete supplies the JSON files directly to the session. Uploaded files are frozen at supply time; replace them to update.
   - **URL fetch:** Athlete creates a repository for training data with automated sync. If the repository is public it carries JSON only; the private dossier never goes there. Record the raw URLs in the project instructions or, when a dossier is used, in its source configuration.
   - `latest.json`: current 7-day snapshot + 28-day derived metrics
   - `history.json`: longitudinal data (daily 90d, weekly 180d, monthly 3y)
   - `intervals.json`: per-interval segment data for recent structured sessions, plus DFA a1 session rollups when AlphaHRV recorded (14-day retention)
   - `ftp_history.json`: dated FTP changes (indoor/outdoor), used for staleness tracking and benchmark comparison
   - `routes.json`: route/terrain data for events with GPX/TCX attachments (when present)
   - `saved_workouts.json`: read-only mirror of the athlete's saved workouts from Intervals.icu (Saved Workouts Mirror)
   - See: https://github.com/CrankAddict/section-11#2-set-up-your-data-mirror-optional-but-recommended

3. **Configure heartbeat settings** (optional, OpenClaw)
   - Check for `HEARTBEAT.md` in the agent workspace
   - If not found, check `section11/examples/agentic/openclaw/HEARTBEAT_TEMPLATE.md`
   - If not found, fetch from: https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/agentic/openclaw/HEARTBEAT_TEMPLATE.md
   - Ask athlete for their specific values (location, timezone, riding hours, weather thresholds, notification hours)
   - Save as HEARTBEAT.md in the agent workspace

4. **Configure data discipline rule** (agentic platforms with persistent identity)
   - Add to the agent's persistent configuration (SOUL.md, system prompt, custom instructions, or equivalent):
   - *"Every training metric cited (watts, duration, TSS, HR, zones) must come from a JSON data read in the current response. No data read = no number. Conversation history, memory, and prior messages are not data sources."*

A current JSON read is required before any numeric or prescriptive coaching. A missing or incomplete dossier limits personalization but does not block safe, data-based coaching, and unresolved dossier review items must not block unrelated coaching. Say what is missing rather than inferring it.

## Protocol

Load the coaching protocol using this precedence:

1. Check `./SECTION_11.md` (data directory root)
2. If not found, check `section11/SECTION_11.md`
3. If not found, check connected repo (if GitHub connector is available)
4. If not found, check uploaded or attached files
5. If not found, fetch from: https://raw.githubusercontent.com/CrankAddict/section-11/main/SECTION_11.md

If both root and `section11/` copies exist, prefer the root copy.

**Current version:** 11.69

## External Sources

All external files referenced by this skill (`sync.py`, `SECTION_11.md`, templates, setup guides) are maintained in the open-source [CrankAddict/section-11](https://github.com/CrankAddict/section-11) repository and can be inspected there.

## Data Hierarchy

1. JSON data (always read latest.json first; read history.json only for trend, phase or longitudinal context)
2. Protocol rules (SECTION_11.md)
3. Athlete dossier (DOSSIER.md): stable private context only, never a current metric
4. Interval data (intervals.json: on-demand, see below)
5. Route/terrain data (routes.json: on-demand, when events have `has_terrain: true`)
6. Saved workout inventory (saved_workouts.json): optional and on-demand for selecting, reusing, or discussing saved workouts; never a session-design authority and never a replacement for the Workout Reference Library
7. Heartbeat config (HEARTBEAT.md)

## Required Actions

- Read or fetch latest.json before any training question. Check the data directory first, then the connected repo (if a connector is available), then uploaded or attached files, then the configured raw URLs (in the project instructions or, when a dossier is used, its source configuration).
- Read or fetch history.json when trend analysis, phase context, or longitudinal comparison is needed. Same precedence.
- Load `intervals.json` when analyzing a specific activity where `has_intervals: true` OR `has_dfa: true`. For block reports, load when any session in the block has either flag. Use for: interval compliance, pacing analysis, cardiac drift per set, recovery quality, DFA a1 session-level interpretation. Do not load for readiness, load management, or weekly summaries.
- Load `routes.json` when a planned event has `has_terrain: true`. Use for: route analysis, terrain-adjusted pacing, pre-ride briefing, race preparation. Same precedence as other JSON files.
- Load `saved_workouts.json` when selecting or reusing a saved workout, or when the athlete asks about their saved workouts. Do not load it for every training question or report. It is the preferred read path for saved workouts on every platform, because it avoids repeated API retrieval and is faster and cheaper to consume. On API-connected platforms, use the Intervals.icu API for edits, and as a read fallback when the mirror is missing, unavailable, stale, inconsistent, or lacks required data. The mirror is read-only and never grants write authority. Check `refresh.status` before use: `ok` means the snapshot was verified at `refresh.last_success_at`, `stale` means a retained older snapshot after a failed refresh, `unavailable` means no snapshot has ever succeeded. `consistency: endpoints_disagree` means the two upstream endpoints did not agree; treat folder membership as indicative. A saved workout may be prescribed only after verifying that its structure implements an applicable Workout Reference Library template or permitted variant. `saved_workouts.json` is never evidence of what was prescribed for a completed activity: historical compliance requires a verified Intervals.icu activity/event pairing or an authoritative prescription supplied in context, and the local JSON mirrors do not carry the prescription.
- For all files (JSON data, protocol, dossier, templates): data directory → connected repo → uploaded/attached files → URL fetch.
- No virtual math on pre-computed metrics. Use values from the JSON for CTL, ATL, TSB, ACWR, RI, zones, etc. Custom analysis from raw data is fine when pre-computed values don't cover the question.
- Every training metric cited (in reports, recommendations, or conversation) must come from a JSON data read in the current response. Conversation history, memory, and prior messages are not data sources.
- When `health_context.clarification_required` is true in latest.json, do not recommend the planned session without addressing it. A marker in `current` means acknowledge the illness or injury and establish severity. A marker in `recent` with none current means the calendar marking stopped, not that the athlete recovered. Ask, do not assume. When `source_status` is `partial` and no marker is visible, say that health markers could not be checked completely and confirm whether illness or injury is currently relevant. A marker does not discard or replace the plan: the planned session remains the starting candidate (not presumed clearance) until severity and compatibility are established, and minor illness or injury may still allow it as written or in modified form. It is not a readiness signal, does not by itself mean skip or deload, and never relaxes an existing Skip. See *Health Context* in SECTION_11.md.
- Check `zone_preference` in READ_THIS_FIRST and `zone_basis` fields on TID/zone blocks. The athlete may have configured HR-preferred zones for specific sports (e.g., running). When `zone_basis` is not the default "power", note this in reports.
- Follow Section 11 C validation checklist before generating recommendations
- Cite frameworks per protocol (checklist item #10)

## Write Capabilities

If `push.py` is available (`section11/examples/agentic/push.py` or in the data repo), the skill can manage the athlete's Intervals.icu calendar and training data:
- **push**: write planned workouts to calendar
- **list**: show planned workouts for a date range
- **move**: reschedule a workout to a different date
- **delete**: remove a workout from the calendar
- **set-threshold**: update sport-specific thresholds (FTP, indoor FTP, LTHR, max HR, threshold pace). Only after validated test results, never from estimates
- **annotate**: add notes to completed activities (description by default, `--chat` for messages panel) or planned workouts (`NOTE:` prepended to description)

All write operations default to preview mode. Nothing is written without `--confirm`. Execution via local CLI or GitHub Actions dispatch. See `examples/agentic/README.md` for full usage, workout syntax, and template ID mappings.

Requires a runtime that can execute code or trigger repository actions, with verified access and configured credentials, not merely a platform labelled agentic. Web chat cannot use this. Grok Bot and Hermes Agent have the required capability class but are **experimental**: neither is validated end to end against the Section 11 pipeline, and capability class is not a support promise. A connector supplies data only: it confers no write authority, no ability to trigger actions or workflows, and no script execution. Each of those capabilities is separate and must be verified before it is used or assumed.

**Verified-write rule.** Apply an approved dossier change only against a location whose write access has actually been verified. Otherwise return the revised file and state plainly that the source was not updated. Never emit a full replacement dossier unless the complete current file is in context; with only an excerpt, return the changed section clearly labelled as a fragment.

## Report Templates

Use standardized report formats. Load templates using this precedence:

1. Check data directory `reports/` directory
2. If not found, check `section11/examples/reports/`
3. If not found, check connected repo (if GitHub connector is available)
4. If not found, check uploaded or attached files
5. If not found, fetch from: https://raw.githubusercontent.com/CrankAddict/section-11/main/examples/reports/

Templates:
- **Pre-workout:** Readiness assessment, Go/Modify/Skip recommendation: `PRE_WORKOUT_REPORT_TEMPLATE.md`
- **Post-workout:** Session metrics, plan compliance, weekly totals: `POST_WORKOUT_REPORT_TEMPLATE.md`
- **Weekly:** Week summary, compliance, phase context: `WEEKLY_REPORT_TEMPLATE.md`
- **Block:** Mesocycle review, phase progression: `BLOCK_REPORT_TEMPLATE.md`
- **Brevity rule:** Brief when metrics are normal. Detailed when thresholds are breached or athlete asks "why."

## Heartbeat Operation

On each heartbeat, follow the checks and scheduling rules defined in your HEARTBEAT.md:
- Daily: training/wellness observations (from latest.json), weather (only if conditions are good)
- Weekly: background analysis (use history.json for trend comparison)
- Self-schedule next heartbeat with randomized timing within notification hours

## Security & Privacy

**Data ownership & storage**
Section 11 operates no hosted backend. Data moves only through services the athlete explicitly configures. Any AI, runtime, model, connector, repository or storage providers actually involved have their own processing and retention terms. See the README's Privacy & Security section for the full statement.

The skill reads from: user-configured JSON data sources and DOSSIER.md at its recorded location, and HEARTBEAT.md in the agent workspace.

It writes to **DOSSIER.md** only to apply a change the athlete has explicitly approved, against a location whose write access has been verified, at first-use creation and at every subsequent maintenance change alike. See `SECTION_11.md` → Update & Version Guidance for the full lifecycle and approval rules.

It writes to **HEARTBEAT.md** in the agent workspace during first-use setup, following that file's own setup flow. HEARTBEAT is agent configuration, not athlete context, and is not governed by the dossier lifecycle.

**Data Handling**
`sync.py` redacts `athlete_id` from the output (always on, unconditional). Activity names are passed through as-is. They carry coaching context (route identification, terrain association). All other training data (activities, wellness, intervals, power/HR values, dates) is passed through to the AI coach as-is.

**Network behavior**
When running locally (files in the data directory), no network requests are needed for protocol, templates, or data. When files are not available locally, the skill fetches them from configured sources.

Credentials are sent only to the service they authenticate, and only when that service is configured: `sync.py` sends the Intervals.icu key in an Authorization header to Intervals.icu, and the GitHub token to GitHub when publishing or issue creation is configured. Credentials are never written into exported or published JSON. Fetched content comes from sources the athlete has explicitly configured; published content goes to services the athlete has explicitly configured. Chat retention is governed by the AI platform's terms, not by Section 11.

**Recommended setup: local files**
The safest and simplest setup is fully local: sync.py on a timer, all files on your device. See `examples/json-local-sync/SETUP.md` for the complete local pipeline. If you use GitHub, use a **private repository**. See `examples/json-auto-sync/SETUP.md` for automated sync setup.

**Protocol and template URLs**
The GitHub URLs are fallbacks for when local files aren't available. The risk model is standard open-source supply-chain.

**Heartbeat / automation**
The heartbeat mechanism is fully opt-in. It is not enabled by default and nothing runs automatically unless the user explicitly configures it. When enabled, it performs a narrow set of actions: read training data, run analysis, write updated summaries/plans to the user's chosen location.

**Private repositories & agent access**
Section 11 does not implement GitHub authentication. It reads files from whatever locations the runtime environment can already access:
- Running locally: reads from your filesystem
- Running in an agent with repository access configured: can read and write repositories that the agent's token or key allows
- Running on a provider-hosted agent computer: reads and writes that computer's filesystem, which is not the athlete's machine. Where such a computer is shared across the athlete's other agents, a private dossier placed there is reachable by all of them, and deleting an agent does not necessarily remove the file

Access is entirely governed by credentials the user has already configured in their environment.
