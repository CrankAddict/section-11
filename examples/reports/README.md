# Report Examples

Reference templates and examples for Section 11-compliant AI coaching reports.

---

## Output Format Guidelines

AI systems should structure athlete reports consistently.  
See templates and examples below for annotated reference.

**Pre-Workout Reports must include:**
- Readiness assessment (HRV, RHR, Sleep vs baselines)
- Load context (TSB, ACWR, Load/Recovery, Monotony if elevated)
- Capability snapshot (Durability 7d mean + trend; TID drift if not consistent)
- Today's planned workout (or rest day + next session preview)
- Go/Modify/Skip recommendation with rationale

**Post-Workout Reports must include:**
- One-line session summary
- Completed session metrics (power, HR, zones, decoupling, VI, TSS vs planned)
- Plan compliance assessment
- Weekly running totals (polarization, durability 7d/28d + trend, TID 28d + drift, CTL, ATL, TSB, ACWR, hours, TSS)
- Interpretation (2-4 sentences: compliance, key quality observations, load context, recovery note)

**Weekly Reports must include:**
- Session breakdown with compliance status (✅/⚠️/❌)
- Quality session detail (top 2-3 intensity sessions: target vs actual, decoupling, VI)
- Polarization with Grey Zone and Quality tracking, plus TID 7d and TID 28d with drift status
- Durability subsection (7d/28d mean(X) counts, trend, high-drift count)
- Fitness deltas (CTL, ATL, TSB start → end with Δ)
- ACWR with acute/chronic components shown
- Wellness trends with directional arrows and threshold labels
- Section 11 flags (surfaced immediately, not deferred to block)

**Block Reports must include:**
- Week-by-week volume progression with CTL trajectory
- Compliance with reasons for misses/modifications
- Key performance markers with target comparison
- Polarization by week (catches grey zone creep), plus TID 28d as block-scale classification
- Durability by week (catches aerobic efficiency regression across the block)
- Wellness block-over-block comparison with assessment labels
- Phase Progression Check (criteria met Y/N, recommendation, rationale)
- Next block plan with specific targets

See `POST_WORKOUT_REPORT_TEMPLATE.md` for field reference and rounding conventions.  
See `REPORT_HIERARCHY.md` for how data flows between report levels.

---

## Files

| File | Description |
|------|-------------|
| [REPORT_HIERARCHY.md](REPORT_HIERARCHY.md) | Overview of all report types, length norms, and data flow |
| [PRE_WORKOUT_REPORT_TEMPLATE.md](PRE_WORKOUT_REPORT_TEMPLATE.md) | Template structure for pre-workout briefings (no data) |
| [PRE_WORKOUT_REPORT_EXAMPLES.md](PRE_WORKOUT_REPORT_EXAMPLES.md) | 4 anonymized example pre-workout reports |
| [POST_WORKOUT_REPORT_TEMPLATE.md](POST_WORKOUT_REPORT_TEMPLATE.md) | Template structure for post-workout analysis (no data) |
| [POST_WORKOUT_REPORT_EXAMPLES.md](POST_WORKOUT_REPORT_EXAMPLES.md) | 4 anonymized example post-workout reports |
| [WEEKLY_REPORT_TEMPLATE.md](WEEKLY_REPORT_TEMPLATE.md) | Template structure for weekly summaries (no data) |
| [WEEKLY_REPORT_EXAMPLES.md](WEEKLY_REPORT_EXAMPLES.md) | 2 anonymized example weekly reports |
| [BLOCK_REPORT_TEMPLATE.md](BLOCK_REPORT_TEMPLATE.md) | Template structure for block reports (no data) |
| [BLOCK_REPORT_EXAMPLES.md](BLOCK_REPORT_EXAMPLES.md) | 2 anonymized example block reports |

---

## Report Types

### Pre-Workout Briefing (~15-20 lines)
Generated **before** a planned session. Includes:
- Weather and coach note (optional, if location known)
- Current readiness (HRV, RHR, Sleep vs baselines)
- Load context (TSB, ACWR, Load/Recovery, Monotony if > 2.3)
- Capability snapshot (Durability 7d mean + trend; TID drift if not consistent)
- Planned workout summary (target power/HR, duration, TSS)
- Go/Modify/Skip recommendation with rationale

### Post-Workout Analysis (~25-30 lines)
Generated **after** a completed session. Includes:
- Execution summary (actual vs planned)
- Key metrics (power, HR, decoupling, VI, carbs)
- Zone distribution (Grey Zone and Quality tracking)
- Load impact (updated CTL, ATL, TSB, weekly totals)
- Capability update (Durability 7d/28d + trend, TID 28d + drift in weekly totals)
- Coaching interpretation

### Weekly Summary (~35-45 lines)
Generated **end of training week** (Saturday or Sunday morning). Includes:
- Session breakdown with compliance status for every day
- Quality session detail for top 2-3 intensity sessions
- Polarization (Z1+Z2, Grey Zone, Quality) with TID 7d and TID 28d + drift status
- Durability subsection (7d/28d mean(X) counts, trend, high-drift count)
- Fitness deltas with ramp rate and ACWR breakdown
- Wellness trends with week-over-week comparison and directional labels
- Section 11 flags triggered during the week
- Next week preview with any planned modifications

### Block Report (~45-60 lines)
Generated **end of each 3-5 week block**. Includes:
- Week-by-week volume and CTL progression
- Compliance summary with reasons for modifications
- Performance marker tracking (sweetspot, VO2max, decoupling trends)
- Polarization by week to catch grey zone creep, plus TID 28d as block-scale classification
- Durability by week to catch aerobic efficiency regression across the block
- Wellness block-over-block comparison with assessment labels
- Phase Progression Check with explicit criteria evaluation
- Next block plan with targets and key changes

---

## Brevity Rule

These templates follow Section 11's brevity principle:
- **Normal metrics:** Brief (2-3 sentence interpretation + key data)
- **Threshold breach:** Detailed (full analysis with recommendations)
- **Rest day:** Minimal (confirm recovery status, preview next session)
- **Athlete asks "why":** Deep dive on specific area

---

## Conditional Fields

Some fields appear only when relevant:
- **Weather:** Include if athlete location is available via profile or memory
- **Monotony:** Include only if > 2.3; omit entirely when normal
- **Load/Recovery tolerance note:** Include only when within 0.2 of threshold
- **Coach notes** (brief contextual tips) are encouraged to humanize recommendations
- **Quality Session Detail (weekly):** Cap at 2-3 key sessions; if 4+ hard days, prioritize most notable

---

## Notes

- All examples use anonymized/placeholder data; replace with actual values from your JSON feed
- Zone percentages round to nearest whole number (see rounding convention in POST_WORKOUT_REPORT_TEMPLATE.md)
- Data flows upward between reports: post-workout → weekly → block (see REPORT_HIERARCHY.md)
- Section 11 flags surface at the weekly level and are summarized with resolution in block reports
