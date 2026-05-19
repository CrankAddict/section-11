# Season Report Examples

Two synthetic, anonymized examples demonstrating the Season Report tier. Both render the trailing-12-month annual arc with YoY metrics-only comparison, per v1 design.

**Anchor convention:** YoY anchor is the **last fully completed calendar month** prior to `metadata.last_updated`. Snapshot date `2026-04-28` → anchor month `2026-03`. The current calendar month (April 2026) is excluded from YoY because partial-month-vs-full-month comparison would distort every delta.

**Aggregation convention:** All 180d aggregates use completed weeks only — `weekly_180d[:-1]`. The in-progress current week carries partial hours, partial TSS, partial hard_days, partial ACWR, and `phase_detected: null`; including it would distort the season summary. The current week's phase is appended to the trajectory string for narrative completeness only.

**Example 1** — Mid-Build cyclist, multi-year data, demonstrates material 2y line surfacing.
**Example 2** — Sparse prior-year data (newly-tracked athlete), demonstrates `n/a — no prior data` rendering.

---

## Example 1 — Mid-Build, multi-year athlete

```
Season Report — 2025-04-28 → 2026-04-28
Generated: 2026-04-28
Annual position: Late Base / Build · Build · week 3 of phase

Annual Position:
  Current phase: Build (week 3)
  Previous phase: Base
  Phase trajectory (180d): Recovery×2 → Base×9 → Build×4 → Recovery×1 → current Build×3
  Seasonal expectation: Late Base / Build — consistent with April expectations on the
    Northern Hemisphere arc (see SECTION_11.md Benchmark Index seasonal table).
    Race season opens within 2 months; CTL trajectory should peak during this Build
    or a single subsequent Build before the taper window for the A-race.

Current Season Trajectory (180d, completed weeks):
  Volume: 211.6h total / 14380 TSS total | 8.5h/wk avg / 575 TSS/wk avg | 25 weeks tracked
  CTL: peak 78.2 (week of 2026-03-23) → current 76.4
  ACWR week-bucket counts: 0 weeks <0.8 / 17 weeks 0.8–1.3 / 6 weeks 1.3–1.5 / 2 weeks >1.5
  TID 180d (time-weighted): 81% Z1+Z2 / 4% Z3 / 15% Z4+ — polarized
  Hard-day density: avg 1.8/wk | first half 1.6/wk → second half 2.0/wk ↑
  Longest ride: 4.5h (week of 2026-04-13)
  Longest week: 12.8h (week of 2026-03-30)
  Quality session count: 23 weeks with ≥1 hard day (92% of completed weeks)

Year-over-Year Comparison (anchor: 2026-03 last completed; current vs prior year, calendar-month matched):
  Anchor month: 2026-03 (last completed)
  Total hours: 41.2h vs 34.6h (+6.6, +19%) | 3mo: 39.4 vs 32.8
  Total TSS: 2820 vs 2330 (+490, +21%) | 3mo: 2680 vs 2240
  CTL peak: 78.2 vs 76.8 (+1.4)
    2y: 78.2 vs 68.4 (+9.8) — material delta vs two years prior
  CTL end: 76.4 vs 74.1 (+2.3)
  Z1+Z2: 80% vs 76% (+4pp)
  Z3: 4% vs 9% (-5pp)
  Z4+: 16% vs 15% (+1pp)
  Hard-day density: 1.9/wk vs 1.5/wk (+0.4)
  Longest ride: 4.2h vs 3.8h (+0.4)
  Avg HRV: 64 ms vs 61 ms (+3)
  Avg RHR: 48 bpm vs 50 bpm (-2)

Notable Patterns:
  FTP timeline (in window): 2025-06-14 — test — 248W, 2025-08-22 — auto-update — 252W,
    2025-11-02 — auto-update — 256W, 2026-02-18 — test — 264W
  Data gaps: 2025-08-04 → 2025-08-12 — 8 days missing (travel)
  A-races completed: 2025-09-07 — Regional Gran Fondo
  Next A-race: 2026-06-21 — Alpine Classic — D-54
  Deviations: ACWR breached 1.5 in 2 of 25 completed weeks (both during late-March CTL push)

Interpretation:
This season is tracking ahead of last year on every load axis — +19% volume, +21% TSS,
hard-day density up by ~1 session every 2-3 weeks, polarization cleaner with Z3 grey
zone roughly halved (9% → 4%). The 1y CTL peak delta is small (+1.4) because last
season also peaked strongly in March, but the 2y comparison shows a +9.8 jump versus
two springs ago — the structural fitness ceiling has clearly moved. Current CTL is 1.8
below peak which fits a deload-then-rebuild rhythm; with 54 days to the A-race the
remaining build window is sufficient. Focus over the next 3–4 weeks shifts to race-
specific intensity before the taper window opens, and the two ACWR>1.5 weeks should
not be repeated inside the final pre-taper block.
```

---

## Example 2 — Newly-tracked athlete, sparse prior-year

```
Season Report — 2025-04-28 → 2026-04-28
Generated: 2026-04-28
Annual position: Spring base-building · Base · week 6 of phase

Annual Position:
  Current phase: Base (week 6)
  Previous phase: Recovery
  Phase trajectory (180d): Recovery×3 → Base×6 → current Base×6
  Seasonal expectation: Late Base — consistent with April expectations on the
    Northern Hemisphere arc (see SECTION_11.md Benchmark Index seasonal table).
    No A-race scheduled, so phase progression is open — current trajectory could
    extend Base or transition to Build per athlete preference and event targets.

Current Season Trajectory (180d, completed weeks):
  Volume: 138.4h total / 8680 TSS total | 5.5h/wk avg / 347 TSS/wk avg | 25 weeks tracked
  CTL: peak 52.1 (week of 2026-04-20) → current 51.8
  ACWR week-bucket counts: 2 weeks <0.8 / 20 weeks 0.8–1.3 / 3 weeks 1.3–1.5 / 0 weeks >1.5
  TID 180d (time-weighted): 86% Z1+Z2 / 6% Z3 / 8% Z4+ — pyramidal
  Hard-day density: avg 1.1/wk | first half 0.9/wk → second half 1.3/wk ↑
  Longest ride: 3.2h (week of 2026-04-06)
  Longest week: 8.4h (week of 2026-04-20)
  Quality session count: 17 weeks with ≥1 hard day (68% of completed weeks)

Year-over-Year Comparison (anchor: 2026-03 last completed; current vs prior year, calendar-month matched):
  Anchor month: 2026-03 (last completed)
  Total hours: 26.8h vs n/a — no prior data
  Total TSS: 1640 vs n/a — no prior data
  CTL peak: 49.4 vs n/a — no prior data
  CTL end: 48.9 vs n/a — no prior data
  Z1+Z2: 86% vs n/a — no prior data
  Z3: 6% vs n/a — no prior data
  Z4+: 8% vs n/a — no prior data
  Hard-day density: 1.2/wk vs n/a — no prior data
  Longest ride: 2.8h vs n/a — no prior data
  Avg HRV: 58 ms vs n/a — no prior data
  Avg RHR: 54 bpm vs n/a — no prior data

Notable Patterns:
  FTP timeline (in window): 2025-11-22 — test — 218W, 2026-03-08 — auto-update — 226W
  Data gaps: None in window
  A-races completed: None in window
  Next A-race: None scheduled
  Deviations: Z3 grey zone in 7 of 25 completed weeks (28% of weeks above the 5% target);
    Hard-day density rising consistently into second half (0.9 → 1.3/wk)

Interpretation:
First full year of tracked data, so YoY comparison is unavailable across the board —
the n/a column is not a missing-data warning, it's the design-correct rendering for a
new athlete and will populate next April. Within the 180d window, trajectory is
constructive: CTL has built steadily to 52.1 with no ACWR>1.5 weeks, hard-day density
is rising naturally into the second half (0.9 → 1.3/wk), and TID is broadly pyramidal.
The 28% grey-zone-week rate is the single pattern worth attention — worth checking
whether those weeks cluster around specific session types (tempo/SST creep) or
particular phases. With no A-race scheduled, the Base extension or Build transition
decision is available; either is supportable from current load and wellness context.
```

---

## Notes on these examples

- Both are synthetic. Numbers are coherent within each example but do not represent any real athlete.
- **Anchor month** in both examples is `2026-03` — the last completed calendar month before the `2026-04-28` snapshot. The current calendar month is excluded from YoY by design.
- **Aggregates** in both examples are computed over completed weeks only (25 weeks tracked, with the 26th week in progress and excluded). This is reflected in line-item counts ("23 weeks with ≥1 hard day", "17 weeks with ≥1 hard day") and in the ACWR bucket totals summing to 25.
- **TID aggregation** in both examples is time-weighted (by `total_hours`), not TSS-weighted. The "(time-weighted)" suffix on the TID line makes the aggregation explicit.
- **Example 1** demonstrates the conditional 2y line: the 1y CTL peak delta is small (+1.4, below the 3-point material threshold) but the 2y delta is +9.8 (well above), so a 2y line surfaces under that single metric only. No 2y line surfaces for hours, TSS, TID, or other metrics where the 1y comparison already conveys the story.
- **Example 2** demonstrates the sparse case: prior-year cells render `n/a — no prior data`. The YoY block stays in place rather than being suppressed — the empty comparison is itself signal.
- **Neither example renders a phase claim about prior years.** This is by design — see template Notes.
- **Capability metrics (durability, EF, sustainability)** are not rendered. These require a `weekly_180d` capability rollup that does not yet exist.
- **Length:** Example 1 is 53 content lines, Example 2 is 51. Both sit comfortably within the 55–70 norm when the full template chrome (header lines, blank lines, section breaks) is counted in the rendered report.
