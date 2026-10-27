# Report Examples

Reference templates and examples for Section 11-compliant AI coaching reports.

---

## Output Format Guidelines

Read [Shared report layout](../../SECTION_11.md#shared-report-layout) with the chosen template. The protocol owns common layout/content rules; templates own report-specific order, sources and gates; examples demonstrate synthetic output.

Every period intensity line uses its own report_intensity block decoded with report_intensity_schema, with a block per selected sport and actual power/HR basis/mapping, complete coverage in the heading and partial coverage on its own line. Use compatible report_intensity_comparison with its coverage limits; resolve explicit rolling refs with parent dates and monthly blocks by first occurrence across the ordered tiers; unresolved or old history is unavailable. Per-activity zones and zone_reference retain their meanings. See [Report intensity source](../../SECTION_11.md#report-intensity-source).

**Pre-workout reports:** After the dated header and Data updated, show Go/Modify/Skip, the supplied signal count and a two-sentence Verdict first. Follow with each Today session and its weather, then labelled Readiness, Load, selected-sport Intensity and Last 7 days. Only explicitly indoor sessions skip weather because of setting; a missing route is not indoor. Rides/runs retain full blocks. Walk/Hike uses a home-weather line within 40 characters; rain replaces dry and moves wind/gusts to a second short line. Preserve home place/source/time-window context and every display/capability gate. A walk/hike route attachment adds a short supplied reason such as Route forecast: rides only, never route-weather claims. Preserve every template field, conditional, source and readiness gate.

**Post-workout reports:** Lead with a labelled Summary after the dated header, then one block per activity ID. Deviating sets have one target/count/average line each, a short miss reason and a supported non-main-step confirmation; distinguish not-ridden reps from below-target reps. Power and HR each have one three-band Z1+Z2 / Z3 / Z4+ line, replacing separate Grey Zone and Quality data lines. Peaks has one supplied duration per line. No Planned line for Walk/Hike; omit session EF unless 0 < VI ≤ 1.05. Last 7 days keeps CTL, ATL, TSB, Ramp rate, Hours and TSS with existing conditional capability/intensity/load context. Label Interpretation paragraphs and end with Next; preserve every Tomorrow session.

Duration displays round to whole minutes while eligibility gates retain exact duration_formatted. Preserve the template's activity IDs, recorded ascent, missing-value, source, compliance, decoupling, DFA and descriptive-peak rules.

**7-day reports** cover today plus six local dates: summary, sport totals and readable Plan counts, Highlights, deviating Key session detail, selected-sport Intensity, capability averages, Fitness, full Wellness including Feel/RPE, flags, Fun facts, labelled Interpretation and Next 7 days. Fitness omits Acute/Chronic; Monotony/Strain appear only when flagged. No planned TSS, not-assessed category or power-curve block.

**28-day reports** show Totals, Plan, Fitness start -> now, one Week by week block with four comma-separated values per metric (oldest first), full 28-day Wellness, selected-sport Intensity, Highlights and deviating Key sessions, Best efforts, DFA, flags, Fun facts and labelled Interpretation ending in Next. Per-week N appears only for partial weeks. Each tempo decoupling value keeps its own plan changes power mark. Preserve 14-day step detail and current calendar-week Phase; no ceilings or separate progression section.

**Season reports** use completed configured calendar weeks: Position (Previous phase only when different), one line per phase cycle, Volume with the longest ride and its own distance once, Fitness with coupled ACWR known coverage, selected-sport Intensity, matched-month YoY one fact per line, non-empty Notable, Fun facts and labelled Interpretation ending in Next. Cycling Fun facts omits its duplicate longest ride.

All three use the shared phone-first layout, complete coverage in headings and explicit partial-coverage lines. Highlights includes every warning/failure plan marker, with no full session list or walk/hike duration markers. Fun facts precede Interpretation for each period-selected eligible sport; power, work and equivalents remain cycling-only. Peaks appear in 7-day/Season fun facts; Most work in a week appears only in 28-day/Season. Equivalents retain their dossier bottle or documented banana basis, breaking a long fact at a meaningful point.

Permanent request aliases: "weekly report" means 7-day report; "block report" means 28-day report. The four old template/example paths remain managed pointers until the first release after 31 December 2026. Update personal instructions to the new filenames. The configured week start still controls history, Season, phase and planned-week features.

See `POST_WORKOUT_REPORT_TEMPLATE.md` for field reference and rounding conventions.  
See `REPORT_HIERARCHY.md` for how data flows between report levels.

**Weather Reports are on request only:** cover all relevant planned outdoor rides in the next five days using matching current route-weather briefs. Use the route name followed by separate Date, Distance and Ascent lines. Give Start, Moving time, Total time, Wind, Gusts, Rain, Temperature and Feels like one labelled line each. Strongest gusts at and the dominant wind effect by distance require the template's supplied-band evidence; omit unsupported claims. Relative to calm air, Headwind estimates added air resistance, Tailwind reduced resistance and Crosswind roughly neutral effect (can slightly help or hinder); Calm requires 0 m/s. Use the producer's 80°/110° classes with the existing coverage, location and tie rules. Put the assumed-start question on its own line, followed by a blank line. Separate identity, facts, maps and rides with blank lines, including before optional Prepare and material Note lines. Use no middle-dot separators or hyphen continuation lines. Weather times use local HH:MM, adding a zone only when different from the athlete's or a UTC fallback; maps/data retain zones. Check expiry even when omitted from text; preserve outlook uncertainty. End report text with one linked line, "Weather data by Open-Meteo, CC BY 4.0." No transformation note, safety tagline, GeoNames line or fetched timestamp belongs in report text; PNG footers stay unchanged. Use a conditions-only Summary under Period instead of Comparison, a labelled Coach note paragraph and one unrouted ride per line. Passed starts use separate Start, Planned-has-passed and question lines. Read and show accessible matching PNG pages directly after report text in session/page order; never describe an unseen map. Only JSON-only, partial or missing/unreadable-map paths add forecast band detail after Feels like, one short labelled block per supplied `bands` entry, never aggregated from raw sections. Pre-workout rides/runs retain full blocks; non-indoor walks/hikes use the template's short home lines with unchanged source/capability gates. Only outdoor rides qualify for route forecasts. No forecast report data or maps when route weather is disabled.

**When no planned ride has a usable route within 120 h**, use the [template's explicit no-route case](WEATHER_REPORT_TEMPLATE.md#no-planned-ride-has-a-usable-route-within-120-h): clear message, ride list and GPX/TCX hint. Only an AI with actual weather-fetch capability and a location resolved under the [shared point-weather rule](../../SECTION_11.md#point-weather-location) may add a separate **Weather at home** block with Place/source and Time lines, never route detail or a replacement inside a ride block. Without fetch capability, say "A home forecast isn't available in this setup." No planned rides at all gets a single no-rides line; the optional home block follows the template's same gates and planned-day rule.

---

For fallback data, the single final attribution names the actual provider: "Weather data by MET Norway, CC BY 4.0." Name both providers on that same line only when separate report blocks use both. Link each provider and the licence.

## Files

| File | Description |
|------|-------------|
| [Shared report layout](../../SECTION_11.md#shared-report-layout) | Common rules for facts, paragraphs, highlights and coverage |
| [REPORT_HIERARCHY.md](REPORT_HIERARCHY.md) | Overview of all report types, length norms, and data flow |
| [PRE_WORKOUT_REPORT_TEMPLATE.md](PRE_WORKOUT_REPORT_TEMPLATE.md) | Template structure for pre-workout briefings (no data) |
| [PRE_WORKOUT_REPORT_EXAMPLES.md](PRE_WORKOUT_REPORT_EXAMPLES.md) | Fictional route, rest-day, indoor, multi-session and outdoor-run examples |
| [POST_WORKOUT_REPORT_TEMPLATE.md](POST_WORKOUT_REPORT_TEMPLATE.md) | Template structure for post-workout analysis (no data) |
| [POST_WORKOUT_REPORT_EXAMPLES.md](POST_WORKOUT_REPORT_EXAMPLES.md) | 8 post-workout scenarios plus synthetic new-field excerpts |
| [7_DAY_REPORT_TEMPLATE.md](7_DAY_REPORT_TEMPLATE.md) | Template structure for 7-day reports (no data) |
| [7_DAY_REPORT_EXAMPLES.md](7_DAY_REPORT_EXAMPLES.md) | 2 synthetic example 7-day reports |
| [28_DAY_REPORT_TEMPLATE.md](28_DAY_REPORT_TEMPLATE.md) | Template structure for 28-day reports (no data) |
| [28_DAY_REPORT_EXAMPLES.md](28_DAY_REPORT_EXAMPLES.md) | 2 synthetic example 28-day reports |
| [SEASON_REPORT_TEMPLATE.md](SEASON_REPORT_TEMPLATE.md) | Template structure for season reports (no data) |
| [SEASON_REPORT_EXAMPLES.md](SEASON_REPORT_EXAMPLES.md) | Synthetic season examples |
| [WEATHER_REPORT_TEMPLATE.md](WEATHER_REPORT_TEMPLATE.md) | On-request five-day planned-route weather |
| [WEATHER_REPORT_EXAMPLES.md](WEATHER_REPORT_EXAMPLES.md) | Synthetic forecast, outlook and missing-data examples |

---

## Report Types

### Pre-Workout Briefing

Generated before a planned session. Follow [PRE_WORKOUT_REPORT_TEMPLATE.md](PRE_WORKOUT_REPORT_TEMPLATE.md) for the opening verdict, session/weather order, labelled supporting blocks and Same-Day Continuation replacement.

### Post-Workout Analysis

Generated after completed sessions. Follow [POST_WORKOUT_REPORT_TEMPLATE.md](POST_WORKOUT_REPORT_TEMPLATE.md) for sets, three-band activity zones, Peaks, Last 7 days, labelled Interpretation and the complete field gates.

### 7-day report

Generated on request for a rolling seven-date window. Follow [7_DAY_REPORT_TEMPLATE.md](7_DAY_REPORT_TEMPLATE.md) and its complete/sparse synthetic examples.

### 28-day report

Generated on request from four supplied rolling chunks. Follow [28_DAY_REPORT_TEMPLATE.md](28_DAY_REPORT_TEMPLATE.md); its examples preserve the DFA comparison and diagnostic cases.

### Season report

Generated on request from completed calendar weeks with separately labelled current snapshot context and calendar-matched YoY. Follow [SEASON_REPORT_TEMPLATE.md](SEASON_REPORT_TEMPLATE.md) and [SEASON_REPORT_EXAMPLES.md](SEASON_REPORT_EXAMPLES.md).

---

## Brevity Rule

These templates follow Section 11's brevity principle:
- **Normal metrics:** Brief labelled paragraphs and key data; the pre-workout verdict is two sentences
- **Threshold breach:** Detailed (full analysis with recommendations)
- **Rest day:** Minimal (confirm recovery status, preview next session)
- **Athlete asks "why":** Deep dive on specific area

---

## Conditional Fields

Some fields appear only when relevant:
- **Weather:** Route data for an eligible outdoor ride takes precedence over any home location for that ride's weather. Walk/Hike stays short home point weather even with an attachment. For point forecasts use an explicit current-chat statement first `(you said)`, then `athlete_profile.location` in current `latest.json` `(from Intervals.icu)`, then the current official dossier's Home region `(from dossier)` only when the profile location is null/empty. Show the place and source under the [shared rule](../../SECTION_11.md#point-weather-location). Chat overrides last only for that conversation, never from memory or earlier chats; heartbeat configuration is not a weather-location source. If something indicates the athlete is elsewhere and the location is unresolved, omit weather or ask. City-level text needs [geocoding](../agentic/EXTERNAL_APIS.md#geocoding-for-point-weather); ambiguity or failure means unavailable with the reason. If all three sources lack a location, say "A home forecast isn't available: no home location. Add your city/country to your Intervals.icu athlete profile, or a Home region in your dossier."
- **Monotony:** Include only if > 2.3; omit entirely when normal
- **Load/Recovery tolerance note:** Include only when within 0.2 of threshold
- **Coach notes** (brief contextual tips) are encouraged to humanize recommendations
- **Key session detail (7-day):** Cap at 2-3 sessions; if 4+ hard days, prioritize most notable

---

## Example width check

The offline docs check scans every fenced report and fragment in all six period, session and weather example files. Data lines, marker-first session lines and unlabelled fact continuations must be at most 40 Unicode characters. Blank lines and standalone bold headings are structural. Only paragraphs beginning with Summary, Load, Quality, Watch, Next, Year on year, Shift, Verdict or Coach note followed by a colon are running text: keep each on one source line and separate it with a blank line so the reader wraps it naturally. Arbitrary prose, a colon-free line or a different fence label is not an exemption. The same checks cover complete reports and every later fragment, including weather fallback bands. No new narrative label exemption is needed: Verdict and Coach note are already explicit.

## Notes

- Worked report text uses anonymized/placeholder data; replace with actual values from your JSON feed
- Zone percentages round to nearest whole number (see rounding convention in POST_WORKOUT_REPORT_TEMPLATE.md)
- Reports read current source data at their own scope; see REPORT_HIERARCHY.md for rolling versus calendar windows.
- Flags surface immediately in the 7-day report and retain documented resolution in the 28-day report.
