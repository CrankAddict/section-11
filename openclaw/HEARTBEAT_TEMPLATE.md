# Heartbeat Configuration Template

Copy this file to your workspace as `HEARTBEAT.md` and fill in the bracketed values.

---

## Setup

| Setting | Value |
|---------|-------|
| Location | [CITY/AREA, e.g., "Aalborg Øst"] |
| Timezone | [TIMEZONE, e.g., "Europe/Copenhagen"] |
| Notification hours | [START]-[END], e.g., 09:00-22:30 |
| Notification channel | [CHANNEL, e.g., "telegram"] |
| Notification ID | [CHANNEL_ID] |

### Weather Thresholds

| Condition | Threshold |
|-----------|-----------|
| Valid riding hours | [START]-[END], e.g., 08:00-17:00 |
| Min temperature | [MIN_TEMP]°C, e.g., 13 |
| Max wind speed | [MAX_WIND] m/s, e.g., 12 |
| Max rain chance | [MAX_RAIN]%, e.g., 30 |

### Data Sources

| Source | URL/Path |
|--------|----------|
| Latest JSON | [URL to latest.json] |
| Archive folder | [URL to archive/] |
| Long-term history | [Local path, optional] |

---

## Daily Checks

### Training & Wellness
- Fetch latest data from configured JSON source
- Look for patterns and trends over time, good and bad
- Flag anything per Section 11 protocol
- Reference goals from DOSSIER.md
- Share observations even if minor — athlete wants to hear your thinking

### Weather (notify only when conditions are good)
- Check configured location for next 24-48h
- Only consider valid riding hours window
- Use yr.no (primary), local met service as backup
- Use local hourly forecast in m/s and °C
- If multiple good windows exist, mention the best 2-3h block
- **If conditions don't meet thresholds, don't mention weather at all**

---

## Weekly Checks

### Background Analysis
- Run once per week between training weeks (suggested: Saturday 14:00 – Sunday 10:00)
- Compare current week vs previous weeks, current month vs previous months
- Track consistency patterns (sessions per week, missed days)
- Note long-term CTL trends (building, plateauing, declining)
- Identify recurring patterns (e.g., always tired on Mondays)
- Ask athlete about changes in sleep, travel, stress, or illness when you see unexplained shifts

### Sports Science
- Check for new research relevant to athlete's training or Section 11 protocol
- Sources to check: PubMed, Google Scholar, SportRxiv
- Trusted venues: MSSE, SJMSS, JAP, J Physiol, BJSM, EJAP, IJSPP, Frontiers in Physiology, Endure IQ, Mysportscience
- **Do NOT auto-apply findings** — surface papers for athlete review only
- Only treat ideas as guidance if athlete later adds them to SECTION_11.md
- Max 3 papers per week, each with:
  - 1-2 sentence summary
  - Why it might matter
  - Source/venue + link

---

## Self-Scheduling

After each heartbeat:
1. If current time (in configured timezone) is outside notification hours, skip checks — just reschedule
2. Delete any existing heartbeat job
3. Pick a random hour within notification window and random minute 00-59
4. If that time is <1 hour away or past end of window today → use tomorrow
5. Schedule next heartbeat

---

## Notes

- Randomized timing prevents predictable patterns
- Weather silence when conditions are bad reduces noise
- Sports science findings require explicit athlete approval before adoption
- Background analysis window should fall between training weeks to avoid mid-week disruption
