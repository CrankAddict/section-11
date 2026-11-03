# Heartbeat Configuration Template

Copy this file to your agent workspace as `HEARTBEAT.md` and fill in the bracketed values.

---

## Setup

| Setting | Value |
|---------|-------|
| Timezone | [TIMEZONE, e.g., "Europe/Copenhagen"] |
| Notification hours | [START]-[END], e.g., 09:00-22:30 |
| Notification channel | [CHANNEL, e.g., "telegram"] |
| Notification ID | [CHANNEL_ID] |

> Weather is configured separately. See [Weather: moved to cron](#weather-moved-to-cron) below.

### Data Sources

Data folder or connected data repository root: [DATA_SOURCE_ROOT]. Resolve every
`section11/` path below from that root, regardless of where this template is
copied. These file paths and heading IDs refer to the installed release, not the
agent workspace. If a required installed file is unavailable, ask for it.

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See Which interval data to use (`section11/SECTION_11.md#which-interval-data-to-use`).

| Source | URL/Path |
|--------|----------|
| Latest JSON | [URL to latest.json] |
| History JSON | [URL to history.json] |
| Archive folder | [URL to archive/] |

---

## Daily Checks

### Training & Wellness
- Fetch latest data from configured JSON source
- Look for patterns and trends over time, good and bad
- Flag anything per Section 11 protocol
- Reference goals from DOSSIER.md
- Share observations even if minor: athlete wants to hear your thinking

---

## Weekly Checks

### Background Analysis
- Run once per week between training weeks (suggested: Saturday 14:00–22:00 or Sunday 20:00 – Monday 10:00)
- Use latest.json for current status, history.json for longitudinal trends, intervals.json for structured session detail, archive/ for recent snapshots
- Compare current week vs previous weeks, current month vs previous months
- Track consistency patterns (sessions per week, missed days)
- Note long-term CTL trends (building, plateauing, declining)
- Identify recurring patterns (e.g., always tired on Mondays)
- Ask athlete about changes in sleep, travel, stress, or illness when you see unexplained shifts
- If any new patterns, open questions, or anomalies emerge, add them to `topics.md`

### Open Topics (when active topics exist)
- Read `topics.md`
- Pick 1 active topic and advance it with fresh data or new context
- Don't force progress. Skip if nothing new to add
- When a topic reaches conclusion, message athlete and move to Resolved
- New topics are seeded during weekly background analysis

---

## Weather: moved to cron

For planned rides with a route, read sync.py's route weather through `latest.json.data_overview` and the weather report. Neither heartbeat nor cron fetches a separate forecast for those rides.

A separate cron is optional for general/home-location weather when there is no route. Its timing and notification policy are the athlete's choice. An athlete may prefer "silence = not rideable"; that is a notification preference, not a Section 11 rule or a safety assessment.

Use the shared Point-weather location rule (`section11/SECTION_11.md#point-weather-location`): explicit current-chat location first, valid only for that conversation; otherwise `athlete_profile.location` in current `latest.json`, then the current official dossier's Home region only when that profile location is null/empty. Show the place and `(you said)`, `(from Intervals.icu)` or `(from dossier)` in the point-forecast output. Do not store or read a weather location in heartbeat configuration, or carry a chat travel override into a later cron run. If travel is indicated but unresolved, omit weather or ask. Geocode city-level text using `section11/examples/agentic/EXTERNAL_APIS.md#geocoding-for-point-weather`; ambiguity or failure means unavailable, never a guess.

---

## Notes

- Planned-route weather uses sync's brief/maps; an optional general/home-location cron must not duplicate it (see above)
- Background analysis window should fall between training weeks to avoid mid-week disruption
- Configure scheduling in your agent platform (cron, heartbeat system, etc.) to run checks within notification hours

**Note:** The heartbeat is fully opt-in and disabled by default. It must be explicitly configured by the user. When active, it only performs scheduled analysis (read training data → run protocol checks → write summaries/plans to your chosen location).

