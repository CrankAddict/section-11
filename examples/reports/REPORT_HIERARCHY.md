# Report Hierarchy Overview

Section 11-compliant AI coaching reports follow a layered structure. Each level builds on the one below it.

---

## Report Types & Length Norms

| Report Type | Trigger | Target Length | Purpose |
|-------------|---------|---------------|---------|
| **Pre-Workout** | Before each session | ~15-20 lines | Readiness check, Go/Modify/Skip |
| **Post-Workout** | After each session | ~25-30 lines | Session analysis, execution quality |
| **Weekly** | End of training week | ~35-45 lines | Compliance, trends, weekly fitness delta |
| **Block** | End of 3-5 week block | ~45-60 lines | Phase assessment, progression decision |
| **Season** | On-demand only | ~55-70 lines | Annual-arc trajectory, YoY metrics comparison |

---

## Information Flow Between Reports

```
Pre-Workout → Post-Workout → Weekly → Block → Season
    │              │             │         │       │
    │              │             │         │       └─ Annual arc + YoY metrics (on-demand)
    │              │             │         └─ Phase progression decision
    │              │             └─ Aggregates post-workout data
    │              └─ Quality metrics feed weekly detail
    └─ Readiness informs session execution
```

**Key principle:** Data flows upward. Each report level summarizes and contextualizes the level below.

- **Post-Workout** metrics (decoupling, VI, target compliance) appear in **Weekly** Quality Session Detail
- **Weekly** fitness deltas (CTL, ATL, TSB) appear week-by-week in **Block** Volume Progression
- **Section 11 Flags** surface at the **Weekly** level and are summarized with resolution in **Block** reports
- **Wellness trends** use week-over-week at Weekly level, block-over-block at Block level
- **Capability metrics** (durability, EF, TID drift) appear as one-liners in Pre/Post, get full treatment in Weekly/Block:
  - **Pre-Workout:** Durability 7d mean(X) + trend (one line). EF 7d mean(X) + trend (one line). TID 28d + drift as separate line, only if not "consistent"
  - **Post-Workout:** Per-session EF. Durability 7d/28d mean(X) + trend in weekly totals. EF 7d/28d mean(X) + trend in weekly totals. TID 28d classification + drift
  - **Weekly:** Durability subsection with mean(X) counts + high-drift count. EF subsection with mean(X) counts + trend. TID 7d + TID 28d on separate lines
  - **Block:** Durability by Week with mean(X) (trajectory across block). EF by Week with mean(X) (trajectory across block). TID 28d as block-scale classification. Per-week classification conditional (only when diverging from block TID)
  - **Season:** Capability metrics (durability, EF, HRRc, sustainability) intentionally absent in v1 — `weekly_180d` rows do not carry rolled-up capability means. Adding them requires a separate weekly capability rollup; parked for v2

---

## Consistency Rules

All report types share these formatting principles:

1. **Data first, prose for interpretation only** — structured line-by-line, not bullet summaries
2. **Scannable in 30 seconds** — most important info at the top
3. **Assessment labels in parentheses** — (good), (optimal), (flag) after metrics
4. **Directional arrows** — ↑/↓/→ for trends with threshold-based labels
5. **Section 11 flags surface immediately** — never deferred to a later report
6. **Capability metrics scale with report scope** — one-liner in pre/post, subsection in weekly, by-week breakdown in block
7. **Interpretation at the end** — 2-5 sentences of coaching interpretation

---

## Files

| File | Description |
|------|-------------|
| `PRE_WORKOUT_REPORT_TEMPLATE.md` | Pre-workout briefing template |
| `PRE_WORKOUT_REPORT_EXAMPLES.md` | 4 anonymized pre-workout examples |
| `POST_WORKOUT_REPORT_TEMPLATE.md` | Post-workout analysis template |
| `POST_WORKOUT_REPORT_EXAMPLES.md` | 4 anonymized post-workout examples |
| `WEEKLY_REPORT_TEMPLATE.md` | Weekly summary template |
| `WEEKLY_REPORT_EXAMPLES.md` | 2 anonymized weekly examples |
| `BLOCK_REPORT_TEMPLATE.md` | Block report template |
| `BLOCK_REPORT_EXAMPLES.md` | 2 anonymized block examples |
| `SEASON_REPORT_TEMPLATE.md` | Season report template |
| `SEASON_REPORT_EXAMPLES.md` | 2 synthetic season examples |
