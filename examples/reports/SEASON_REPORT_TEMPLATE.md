# Season Report Template

**Structure only — no data. Replace `[placeholders]` with actual values.**

**Data Freshness:** Every numeric value in a report must come from a current read of its source JSON file. Do not carry forward values from earlier reports or earlier in the conversation — re-read before quoting.

**Display Units:** For distance / elevation / weight / height / position / speed, quote `display.*` fields from the source JSON — they're pre-converted to the athlete's Intervals.icu preferences. Use canonical metric (`*_km`, `*_m`, `*_kg`) only for calculations. W/kg, kJ, IF, % are universal physics units, not pref-dependent. See SECTION_11.md §Display Unit Semantics.

**Trigger:** On-demand only. Generated when the athlete asks for a season-scale view. No automatic cadence.

**Span:** Trailing 12 months ending at `metadata.last_updated` (or `history.generated_at` if reading from `history.json` directly).

**YoY Anchor Month:** Use the **last fully completed calendar month** prior to `metadata.last_updated`. If `last_updated` is `2026-04-28`, anchor month is `2026-03`, and the prior-year match is `2025-03`. The current calendar month is excluded from YoY comparison until it completes — partial-month-vs-full-month would systematically distort every delta. The 3-month rolling band uses anchor + prior 2 completed months on each side.

**Aggregation Rule:** Section 3 (Current Season Trajectory) uses **completed weeks only** — `weekly_180d[:-1]`. The last row is always the in-progress current week with partial hours, partial TSS, partial hard_days, partial ACWR, and `phase_detected: null`. Including it distorts every aggregate. The current-week phase is appended to the trajectory string (Section 2) for narrative completeness via `derived_metrics.phase_detection.phase`, but does not feed any numeric aggregate.

---

## Template Structure

```
Season Report — [span_start] → [span_end]
Generated: [snapshot_date]
Annual position: [seasonal_context] · [phase] · week [N] of phase

Annual Position:
  Current phase: [phase] (week [N])
  Previous phase: [previous_phase]
  Phase trajectory (180d): [run-length encoding, e.g. Recovery×2 → Base×8 → Build×5 → current Build×3]
  Seasonal expectation: [text reference to SECTION_11.md Benchmark Index seasonal table]

Current Season Trajectory (180d):
  Volume: [XXX]h total / [XXXXX] TSS total | [XX.X]h/wk avg / [XXX] TSS/wk avg
  CTL: peak [XX.X] (week of [date]) → current [XX.X]
  ACWR week-bucket counts: [N] weeks <0.8 / [N] weeks 0.8–1.3 / [N] weeks 1.3–1.5 / [N] weeks >1.5
  TID 180d: [XX]% Z1+Z2 / [X]% Z3 / [X]% Z4+ — [classification: polarized/pyramidal/threshold-heavy/mixed]
  Hard-day density: avg [X.X]/wk | first half [X.X]/wk → second half [X.X]/wk [↑/↓/→]
  Longest ride: [X.X]h (week of [date])
  Longest week: [X.X]h (week of [date])
  Quality session count: [N] weeks with ≥1 hard day

Year-over-Year Comparison (anchor: last completed month [YYYY-MM]; current vs prior year, calendar-month matched):
  Anchor month: [YYYY-MM] (last completed)
  Total hours: [XX.X]h vs [XX.X]h ([+/-X.X], [+/-X]%) | 3mo: [XX.X] vs [XX.X]
  Total TSS: [XXXX] vs [XXXX] ([+/-X], [+/-X]%) | 3mo: [XXXX] vs [XXXX]
  CTL peak: [XX.X] vs [XX.X] ([+/-X.X])
  CTL end: [XX.X] vs [XX.X] ([+/-X.X])
  Z1+Z2: [XX]% vs [XX]% ([+/-X]pp)
  Z3: [X]% vs [X]% ([+/-X]pp)
  Z4+: [X]% vs [X]% ([+/-X]pp)
  Hard-day density: [X.X]/wk vs [X.X]/wk ([+/-X.X])
  Longest ride: [X.X]h vs [X.X]h ([+/-X.X])
  Avg HRV: [XX] ms vs [XX] ms ([+/-X])
  Avg RHR: [XX] bpm vs [XX] bpm ([+/-X])
  [If 2y or 3y same-month adds material context: 1 line per material delta]

Notable Patterns:
  FTP timeline (in window): [date — type — value], [date — type — value], …
  Data gaps: [period — N days missing], … (or "None")
  A-races completed: [date — name], … (or "None in window")
  Next A-race: [date — name — D-XX] (or "None scheduled")
  Deviations: [one line max — e.g. "Z3 grey zone in 7 of 26 weeks", or "None notable"]

Interpretation:
[2-4 sentences — current trajectory read in season context, YoY headline, forward note
referencing seasonal expectation if a clear one applies. No phase claims about
prior years (see Notes).]
```

---

## Field Definitions

| Field | Source | Notes |
|-------|--------|-------|
| **span_start / span_end** | `metadata.last_updated` (or `history.generated_at`) — span = trailing 12 months ending at this date | Span uses calendar months for clean YoY anchoring |
| **Annual position (header)** | `derived_metrics.seasonal_context` + `derived_metrics.phase_detection.{phase, phase_duration_weeks}` | One-line summary; full breakdown follows in Annual Position section |
| **Current phase / Previous phase** | `derived_metrics.phase_detection.{phase, previous_phase, phase_duration_weeks}` | Use the structured `phase_detection` object, not the top-level `phase_detected` shortcut |
| **Phase trajectory (180d)** | Run-length encoding of `weekly_180d[*].phase_detected` | If the most-recent row has `phase_detected: null` (incomplete current week), append current phase from `derived_metrics.phase_detection.phase` rather than dropping the row. Skip duplicate appends |
| **Seasonal expectation** | Cross-reference to SECTION_11.md Benchmark Index seasonal table, anchored on calendar month | Text reference only — no numeric assertion |
| **Volume** | Sum `weekly_180d[:-1][*].total_hours` and `total_tss`; derive per-week averages from the same completed-week row set. `summaries.180d` may be used only if verified to exclude the in-progress week | Headline annual-arc metric. `summaries.180d` does not carry `total_*` and its `weeks_tracked` is not guaranteed to exclude the current partial week — derive directly from the completed weekly rows by default |
| **CTL peak / current** | `max(weekly_180d[:-1][*].ctl_end)` for completed-week peak, `current_status.fitness.ctl` for current | Peak uses completed weeks — conservative. Current is the live snapshot, separate path |
| **ACWR week-bucket counts** | Count of `weekly_180d[:-1][*].acwr` in each band: `<0.8`, `0.8–1.3`, `1.3–1.5`, `>1.5` | Distribution view. In-progress week's ACWR is partial — exclude |
| **TID 180d** | Aggregate from `weekly_180d[:-1][*].{z1_z2_pct, z3_pct, z4_plus_pct}` weighted by week `total_hours` (time-budget, not load-budget) | Zone distribution is fundamentally a time metric — TSS-weighting would systematically deflate Z1+Z2 share. Classification follows existing Seiler TID conventions |
| **Hard-day density** | `weekly_180d[:-1][*].hard_days` mean across window, plus first-half vs second-half drift | Drift catches season-long progression or accumulation. Halves split the completed-weeks list |
| **Longest ride / Longest week** | `max(weekly_180d[:-1][*].longest_ride_hours)` and `max(weekly_180d[:-1][*].total_hours)` | Annotate with the week each occurred. Current week is partial — exclude formally even though it would lose anyway |
| **Quality session count** | Count of `weekly_180d[:-1][*]` rows where `hard_days >= 1` | Consistency proxy across completed weeks |
| **YoY anchor month** | Last fully completed calendar month prior to `metadata.last_updated`. If `last_updated` is `2026-04-28`, anchor is `2026-03` | Excludes in-progress current month from comparison. Partial-month-vs-full-month would systematically distort every delta |
| **YoY metric lookup** | Match by `month` string across the union of `monthly_1y`, `monthly_2y`, `monthly_3y` | These are rolling-trailing arrays, not year-bucketed. Look up `month == "YYYY-MM"` wherever it lives |
| **YoY 3mo rolling band** | Mean of matched + prior 2 matched months in each year | Damps single-month noise. Skip the band if any of the three months is missing — do not average over 2-of-3 |
| **YoY material 2y/3y line** | Render an extra 2y or 3y line only when delta meets material threshold (see Material Threshold below) | Default is current-vs-last-year only |
| **FTP timeline** | `ftp_timeline[*]` filtered to span | Date, type (test/auto-update), value |
| **Data gaps** | `data_gaps[*]` within span | Period and `days_missing` |
| **A-races completed** | `race_calendar.all_races[*]` filtered to span where priority == "A" | Only A-races; B/C surface in Block reports |
| **Next A-race** | `race_calendar.next_race` if priority == "A" | Date, name, D-XX countdown |
| **Deviations** | One line max — count-based observation derived from `weekly_180d` flags | Examples: grey-zone week count, deload-shortfall count. If nothing notable, write "None notable" |
| **Interpretation** | 2-4 sentences synthesizing trajectory + YoY + notable patterns | No phase claims about prior years (see Notes) |

---

## Assessment Labels

### Phase Trajectory Run-Length Notation
| Pattern | Format |
|---------|--------|
| Run of same phase | `Phase×N` |
| Phase change | ` → ` separator |
| Current incomplete week (phase null on last row) | Append `current Phase×M` from `phase_detection.phase` |
| Final stretch in current phase | `current ` prefix on the trailing run |

Example: `Recovery×2 → Base×8 → Build×5 → current Build×3` reads as: 2 weeks Recovery, 8 weeks Base, 5 weeks Build, currently 3 weeks into another Build run.

### YoY Material Threshold (for surfacing 2y/3y lines)
| Metric | Material when delta is |
|--------|------------------------|
| Hours / TSS | ≥15% |
| CTL peak / CTL end | ≥3 points |
| TID component (Z1+Z2 / Z3 / Z4+) | ≥5 percentage points |
| Other (HRV, RHR, density, longest ride) | Not material on their own — only surface if they reinforce one of the above |

If 2y or 3y data missing for the matched month, skip that comparison silently — do not render `n/a`. The default current-vs-last-year line already reports `n/a — no prior data` when prior year is missing.

### Direction Arrows
Same conventions as Block report — `↑` improving, `↓` declining, `→` stable, applied to hard-day density first-half vs second-half drift.

---

## Notes

- **Phase narrative is scoped to ≤180d.** All phase references in this report draw from `weekly_180d[*].phase_detected` or `derived_metrics.phase_detection`. As of v3.110, `monthly_*y[*].dominant_phase` is derived via modal aggregation of overlapping `weekly_180d[*].phase_detected` values (most-frequent label wins; TSS is tie-break only) — same vocabulary as `_detect_phase_v2`. It is **null for any month older than ~6 months** because no weekly rows overlap that window. The YoY section therefore remains **metrics-only**: no phase labels for prior years, by structural necessity rather than rule. Do not synthesize phase labels for older months from CTL/zone shapes; if `dominant_phase` is null, render no phase claim.
- **Capability trajectory is per-week from v3.110.** Each `weekly_180d` row carries `durability_mean`/`_qualifying`, `ef_mean`/`_qualifying`, `hrrc_mean`/`_qualifying`. Gating mirrors `derived_metrics.capability` (VI ≤ 1.05, ≥ 90min for durability; cycling types + ≥ 20min for EF; HRRc > 0). N≥1 emits a mean — use `*_qualifying` to calibrate render confidence (a single-session mean is a real observation, not an estimate). Sustainability and DFA a1 remain present-moment only in `derived_metrics.capability`.
- **Goal audit is fully deferred.** v1 is descriptive only. There is intentionally no goal section, no header, no placeholder. v2 will introduce planned-vs-actual comparison once the data path (race_calendar, dossier-stated season targets) is clean.
- **YoY arrays are rolling-trailing, not year-bucketed.** `monthly_1y`, `monthly_2y`, `monthly_3y` are deeper rolling windows that may be sparse for newly-onboarded athletes. Always match by calendar `month` string, never by array position. If matched month not present in any tier, render `n/a — no prior data` and move on. Do not infer.
- **Material threshold surfaces 2y/3y selectively.** Default display is current vs last year only. 2y or 3y lines appear only when the delta meets the threshold and the comparison adds genuine context. Three-year tables every time defeat the report's purpose — keep it ruthless.
- **Length norm 55–70 lines.** Longer than Block (45–60) because the annual arc needs trajectory + YoY space. Shorter would force tighter aggregation than the data supports. Hold the line.
- **Cadence: on-demand only.** Seasons aren't crisp boundaries. No automatic generation, no calendar trigger.
- **Notable Patterns is small by design.** FTP events, data gaps, A-races, plus one deviations line. Resist expanding — durability-temp artifacts and AAS escalation history are Block-scope or out of scope for v1.
- **Interpretation stays interpretive.** 2-4 sentences. Trajectory read, YoY headline, forward note. No numeric restatement of what's already in the data sections above.

## Formatting Rule

- **Durations:** Use `_formatted` fields from JSON where they exist on the source object. `weekly_180d[*]` rows currently expose `longest_ride_hours` (decimal, no `_formatted` sibling). Render decimal hours with a trailing `h` (e.g. `4.5h`); do not invent a formatted variant. For `total_training_formatted` and similar fields on other JSON objects, use the formatted form when present.
