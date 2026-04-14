# Heartbeat Configuration Template

Copy this file to your agent workspace as `HEARTBEAT.md` and fill in the bracketed values.

---

## Setup

| Setting | Value |
|---------|-------|
| Location | [CITY/AREA, e.g., "Klampenborg"] |
| Timezone | [TIMEZONE, e.g., "Europe/Copenhagen"] |
| Notification hours | [START]-[END], e.g., 09:00-22:30 |
| Notification channel | [CHANNEL, e.g., "telegram"] |
| Notification ID | [CHANNEL_ID] |

> Weather is configured separately — see [Weather — moved to cron](#weather--moved-to-cron) below.

### Data Sources

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
- Share observations even if minor — athlete wants to hear your thinking

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
- Don't force progress — skip if nothing new to add
- When a topic reaches conclusion, message athlete and move to Resolved
- New topics are seeded during weekly background analysis

---

## Weather — moved to cron

Weather checks are best handled by separate scheduled jobs (morning + evening), not the heartbeat. Only message the athlete if conditions are rideable. **Silence = not rideable.**

---

## Notes

- Weather is best handled by a separate scheduled check, not the heartbeat (see above)
- Background analysis window should fall between training weeks to avoid mid-week disruption
- Configure scheduling in your agent platform (cron, heartbeat system, etc.) to run checks within notification hours

**Note:** The heartbeat is fully opt-in and disabled by default. It must be explicitly configured by the user. When active, it only performs scheduled analysis (read training data → run protocol checks → write summaries/plans to your chosen location).

