# Report Hierarchy Overview

Section 11-compliant AI coaching reports follow a layered structure. Each level builds on the one below it.

---

## Report Types & Length Norms

| Report Type | Trigger | Target Length | Purpose |
|-------------|---------|---------------|---------|
| **Pre-Workout** | Before each session | Verdict and signal count first; Today/weather; Readiness, Load, Intensity, Last 7 days | Readiness check with two-sentence verdict and unchanged decision gates |
| **Post-Workout** | After each session | Summary, short facts and deviating sets; three-band zones, Peaks and Last 7 days | Session analysis, execution quality |
| **7-day** | On request, ending today | Highlights and short facts with labelled Interpretation | Rolling load, plan matches, capability and next seven days |
| **28-day** | On request, ending today | One Week by week block with four values per metric | Rolling progression, plan matches and capability context |
| **Season** | On demand | Completed-week aggregates and matched-month comparisons | Season trajectory and YoY context |
| **Weather** | On request only | One fact per labelled line; conditions Summary under Period; unrouted rides one per line; short fallback-band blocks | Five-day route forecast/outlook and practical preparation |

---

## Information Flow Between Reports

Pre-workout informs preparation; post-workout describes completed sessions. The 7-day report summarizes today plus six local dates. The 28-day report consumes four supplied rolling chunks; its newest chunk equals the 7-day window. Season uses completed configured calendar weeks, so its boundaries differ from rolling reports.

Each report reads current source data; it never aggregates earlier AI reports.

**Weather is a parallel planning report**, sourced directly from matching current route-weather briefs, not aggregated from completed sessions. It covers all relevant rides in the next five days and may inform the same-day pre-workout block. It does not replace readiness, infer a Go decision, reschedule training or promote an outlook into section-level certainty. Missing/stale/disabled data stay explicit. Read and show accessible matching PNG pages directly after report text in session/page order; never describe an unseen image. Expand into band detail only for missing/unreadable pages, JSON-only access or partial briefs, reading forecast `bands` directly rather than aggregating raw sections, one short labelled block per band after Feels like. Use separate labelled identity/weather facts, including Moving time and Total time, and an assumed-start question on its own line. Passed starts keep Start, the passed Planned time and the question on three separate lines. Strongest gusts at and dominant wind effect by distance require supported band locations; omit them when unsupported. Wind effect estimates air resistance relative to calm air: Headwind adds it, Tailwind reduces it, Crosswind is roughly neutral (can slightly help or hinder), and Calm requires 0 m/s. Use supplied 80°/110° classes under the weather template's coverage and tie rules. Add blank lines before optional Prepare and material Note lines. Separate blocks with blank lines; no middle-dot separators or hyphen continuation lines. Weather clocks use local HH:MM unless a differing zone or UTC fallback needs a label. Always check expiry. End report text with one linked line, "Weather data by Open-Meteo, CC BY 4.0.", without a transformation note or separate GeoNames line. Maps and data labels remain unchanged.

When no planned ride has a usable route within 120 h, use the [template's explicit no-route case](WEATHER_REPORT_TEMPLATE.md#no-planned-ride-has-a-usable-route-within-120-h), including the ride list and GPX/TCX hint. Only actual fetch capability plus a location resolved under the [shared point-weather rule](../../SECTION_11.md#point-weather-location) allows a separate **Weather at home** block with labelled Place and Time lines; it never substitutes for route weather inside a ride block. Always show the place and source: current-chat statement first `(you said)`, then current `athlete_profile.location` `(from Intervals.icu)`, then dossier Home region `(from dossier)` only when the profile location is null/empty. Without fetch capability, say "A home forecast isn't available in this setup." No planned rides at all gets the single no-rides line, with the home block optional under the same capability/location and planned-day gates.

For fallback data, the single final attribution uses the actual provider name: "Weather data by MET Norway, CC BY 4.0." Name and link both providers on that line only when separate report blocks use both.

- **7-day:** Highlights, deviating key-session windows, period-local selected-sport Intensity blocks, durability/EF/HRRc means with N, current load and recovery without Acute/Chronic, and Wellness with Feel/RPE.
- **28-day:** one Week by week block from four supplied chunks, full 28-day wellness and DFA, pairing counts, checked plan results, Highlights, Best efforts and labelled Interpretation ending in Next. Per-week N appears only when partial; tempo decoupling values each retain their plan changes power mark. Preserve 14-day step detail; no ceilings or separate progression section.
- **Season:** completed-week volume, CTL and coupled ACWR coverage, producer report_intensity_season distributions weighted by zone seconds, separately labelled current 28-day TID and calendar-matched YoY. Decode the file's report_intensity_schema, resolving each month's block from the first containing tier in monthly_1y/2y/3y order. Each period selects its own sports; compare only matching sport/basis/mapping and retain coverage. No invented prior-year phase labels. All report intensity follows [Report intensity source](../../SECTION_11.md#report-intensity-source); missing new blocks are unavailable and legacy all-sport fields remain context only.
- **Fun facts:** all three use period-selected cycling, running, swimming, Nordic skiing and rowing immediately before Interpretation. Read cycling from fun_facts and the other four from sport_fun_facts; missing/incompatible selection is unavailable. Preserve observed partial values with coverage, freshness and attribution. Biggest week belongs only in 28-day/Season; power, work and equivalents remain cycling-only. Equivalents are illustrative and never fueling advice.
- **Plan status:** not_assessed remains distinct in source data but is never a count category. Reports distinguish pairing from checked execution, with marker-first Highlights and duration checks for paired no-step sessions except Walk/Hike. Walk/hike participation stays in Plan only, with no duration markers or checked execution. A broad plan match is not formal adherence.
- **Preservation:** post-workout Last 7 days retains rolling scope and CTL, ATL, TSB, Ramp rate, Hours, TSS plus existing conditional context. History week_start, phase detection, planned-week features and ordinary training-block concepts retain their meanings.

---

## Consistency Rules

Common formatting and content rules live only in [Shared report layout](../../SECTION_11.md#shared-report-layout). Read that section with the chosen template. All reports apply its short data lines, naturally wrapping labelled paragraphs, marker-first Highlights, selected-sport blocks and coverage placement. Their templates retain the exact source, eligibility and omission rules. Season keeps one line per phase cycle, a one-fact-per-line year comparison, the longest ride once in Volume and Previous phase only when different.

---

## Files

| File | Description |
|------|-------------|
| `PRE_WORKOUT_REPORT_TEMPLATE.md` | Pre-workout briefing template |
| `PRE_WORKOUT_REPORT_EXAMPLES.md` | Pre-workout examples |
| `POST_WORKOUT_REPORT_TEMPLATE.md` | Post-workout analysis template |
| `POST_WORKOUT_REPORT_EXAMPLES.md` | Post-workout examples |
| `7_DAY_REPORT_TEMPLATE.md` | 7-day report template |
| `7_DAY_REPORT_EXAMPLES.md` | 2 synthetic 7-day examples |
| `28_DAY_REPORT_TEMPLATE.md` | 28-day report template |
| `28_DAY_REPORT_EXAMPLES.md` | Synthetic 28-day and conditional DFA examples |
| `SEASON_REPORT_TEMPLATE.md` | Season report template |
| `SEASON_REPORT_EXAMPLES.md` | 2 synthetic season examples |
| `WEATHER_REPORT_TEMPLATE.md` | On-request five-day route-weather report |
| `WEATHER_REPORT_EXAMPLES.md` | Synthetic forecast, outlook, partial and unavailable examples |
