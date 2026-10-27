# Post-Workout Report Examples

For the updated report-source illustration, Polarization/TID lines below use fictional period-local report_intensity blocks selecting cycling, with four power-covered sessions in the seven-day window and sixteen across four 28-day chunks. These intensity values and coverage counts are synthetic and independent of the legacy session aggregates. Both blocks use compatible mappings and complete observed sessions; fetch completeness is unknown. Other legacy aggregates remain preserved. These illustrations decode the file-level report_intensity_schema; counts do not imply exact covered dates.

> Fictional examples showing standard post-workout report format.  
> See `POST_WORKOUT_REPORT_TEMPLATE.md` for field reference. Legacy examples do not supply recorded elevation, so Ascent is omitted. Missing matched-step data is stated explicitly; aggregate numbers are preserved. The fictional field excerpts below illustrate the new producer contract without inventing step actuals for those legacy reports.

The fictional scenarios retain their supplied aggregate measurements. For these display fixtures, omitted activity zones have zero seconds and each printed zone percentage is exact, so the three-band sums below are exact before rounding. Real reports aggregate raw zone seconds before rounding. The scenarios omit new fields that were not captured. Example 7 explicitly adds fictional qualified work-step evidence to demonstrate the structured Sweetspot rule. Their timestamps use explicitly labelled UTC fallback because no athlete timezone is supplied. The new-field excerpts are synthetic, including their temperature, elapsed time, W/kg and curve points; they are not Daniel's captured responses.

---

## Short-set compliance excerpts (synthetic)

`interval_data.plan_match` supplies timeline labels; `interval_data.compliance` summarizes gated Section 11 evidence from session_structure; `interval_data.icu_detected` is descriptive only. See [Which interval data to use](../../SECTION_11.md#which-interval-data-to-use).

These independent scenarios illustrate short compliance blocks, not a full report or athlete data. Each supported case has an exact captured prescription, matching current pairing and detail identity, three comparable sets of ten 30/15 work bouts, an authoritative 300 W target, established main-work roles and no essential secondary constraints. Every standard window has 29 observed seconds and every adherence window has 27 observed seconds unless stated otherwise. The accepted band is 297–315 W. All unlisted bout means are exactly 300 W. The fictional set averages below are separately supplied observations, never a way to derive the atomic counts. In the first two cases, qualified warm-up, recovery and cool-down windows independently confirm the non-main steps. Keep the remaining activity fields and Last 7 days in a complete report.

**One miss:** set 2/bout 6 has an unrounded adherence mean of 295.8 W; all work is complete. Set means alone cannot supply the count.

```text
Main work: completed
On target: 29/30 bouts (97%)
Sets
Set 1 (300 W): 10/10, 300 W avg
Set 2 (300 W): 9/10, 300 W avg
Set 3 (300 W): 10/10, 300 W avg
Reason: set 2/bout 6 −4.2 W, below band
Non-main steps: on plan
```

**Within-band increase:** set 3/bout 4 is 304 W, with all other bouts exactly at target and all work complete. This is adherence, not permission to progress.

```text
Main work: completed
On target: 30/30 bouts (100%)
Non-main steps: on plan
```

**Detail expired:** the retained set summary and authoritative plan still establish standard work-time completion, but no individual bout actuals remain. Set observations cannot reconstruct them.

```text
Main work: completed
Adherence: not evaluable
Reason: individual bout detail expired
```

**Incomplete main work:** the last bout has a 25-second standard span against the expected 29 seconds and a selected 3-second offset. Its four-second deficit exceeds the alignment allowance. Known means remain descriptive.

```text
Main work: incomplete
Set 3/bout 10: 4s standard deficit
Alignment allowance: 3s
Aggregate adherence: not evaluable
```

**Missing bout power:** a full standard span with only 27 observed seconds cannot establish completion even if its adherence window has 26/27 seconds. Pooled set coverage does not override this.

```text
Completion: not evaluable
Set 1/bout 1: low standard coverage
Adherence: not evaluable
```

## Duration-based compliance excerpts (synthetic)

These separate examples have exact paired prescriptions and qualified structure-version-6, evidence-marker-4 detail with established main-work roles and no essential secondary constraints. They do not change the set examples above. Completion always uses the standard window. Recovery length and repeat count do not select the evaluator or window.

**Single short step with long recovery:** a 30 s effort at 300 W followed by 90 s recovery has a complete 29 s standard window. Its adherence row has 27 observed seconds and 8100 J, so the mean is 300 W. This same exclusion applies to each effort in 8 × 30 s / 90 s and 6 × 40 s / 2 min when their mapping is supported.

```text
Main work: completed
Step (300 W): 1/1, 300 W avg
Prescribed: 30s
Standard window: 29s
Adherence window: 27s
```

**Duration boundary:** independent 60 s and 61 s efforts at 300 W both complete their standard windows. The 60 s effort uses 57 adherence seconds after two leading seconds and the final aligned second are excluded; the 61 s effort uses its 60 s standard window after only the first-second exclusion. With constant 300 W, each is on target. A clipped 61 s effort remains subject to the longer-step rule.

**Long compressed bouts:** three 90 s efforts with 30 s recoveries each have 89 standard and adherence seconds. Their unrounded means are 300 / 295.8 / 300 W against 300 W. The first retained second remains included even though the efforts form a compressed set.

```text
Main work: completed
On target: 2/3 bouts (67%)
Set 1 (300 W): 2/3, 299 W avg
Reason: bout 2 −4.2 W, below band
```

**Pyramid:** 40/30/20 s efforts at 300/310/320 W have complete 39/29/19 s standard windows. The first two use 37/27 s average-adherence windows with means equal to their targets. The 20 s sprint uses a best 6 s of 320 W within its standard window, whose mean is also 320 W. Its stored 18 s average window does not judge the sprint. Different durations/evaluators do not establish an aggregate.

```text
Main work: completed
40s (300 W): on target, 300 W avg
30s (310 W): on target, 310 W avg
20s sprint (320 W): on target
Sprint mean: 320 W (+0 W)
Best 6s: 320 W (+0 W)
Aggregate: not evaluable, mixed steps
```

## Sprint compliance excerpts (synthetic)

Each independent 10 s main-work sprint below has an authoritative 700 W target and a complete 9 s standard window and W = 3 s unless stated otherwise. Mapping and essential constraints are established; no ERG use is assumed. The threshold is 700 W exactly, with no lower tolerance or upper ceiling. Standard-window means and peaks are reported separately. These invented cases illustrate arithmetic, not calibration on recorded sprints.

**Reaches target despite a low mean:** six observed seconds at 600 W and three consecutive seconds at 702 W give a 634 W bout mean and 702 W best 3 s.

```text
Main work: completed
On target: 1/1 sprint
Mean delta: −66 W
Best 3s delta: +2 W
```

**Misses by one watt:** all nine observed seconds are 699 W. No lower tolerance applies.

```text
Main work: completed
On target: 0/1 sprint
Mean delta: −1 W
Best 3s delta: −1 W
Reason: best window below target
```

**Single-sample spike:** one interior second at 900 W among eight 525 W seconds gives a best 3 s of 650 W and a 566.7 W displayed mean. The spike does not meet the target.

```text
Main work: completed
On target: 0/1 sprint
Mean delta: −133.3 W
Best 3s delta: −50 W
Reason: best window below target
```

**Above target:** all nine seconds are 760 W. The high mean and peak are informational, with no sprint upper-band failure.

```text
Main work: completed
On target: 1/1 sprint
Mean delta: +60 W
Best 3s delta: +60 W
```

**Range target:** a 700–800 W sprint uses its 700 W lower bound, explicitly recorded as `sprint_target_w`. A mean and best 3 s of 900 W pass; the upper bound is not a ceiling. This sprint remains in any valid comparable atomic count.

```text
Main work: completed
On target: 1/1 sprint
Threshold: 700 W lower bound
Mean delta: +200 W
Best 3s delta: +200 W
```

**Insufficient observed time:** only two seconds at 702 W are observed. The peak is unavailable and standard coverage cannot establish completion.

```text
Completion: not evaluable
Observed mean delta: +2 W
Best 3s: unavailable
Adherence: not evaluable
Reason: <3 consecutive observed seconds
```

**Longer sprint window:** a prescribed 20 s sprint at 700 W uses W = 6 s. Three consecutive observed seconds at 800 W followed by sixteen at 500 W give a 547.4 W displayed standard mean and a best 6 s of 650 W. Its best 3 s is 800 W, but that shorter peak cannot supply this verdict. Completion remains established by the full 19 s standard window.

```text
Main work: completed
On target: 0/1 sprint
Mean delta: −152.6 W
Best 6s delta: −50 W
Reason: best window below target
```

**Disconnected observations:** a 20 s sprint with more than six observed seconds in total, but no continuous run longer than five seconds, has no best 6 s evidence. Report adherence not evaluable. Do not join the runs or reduce W to 3 s.

A prescribed 21 s effort instead uses its 19 s transition-excluded average and asymmetric band: constant 760 W against 700 W exceeds the 735 W upper bound and misses. Missing mapping or essential constraints remain limitations under either evaluator. The existing plan-match ±5% screen is unchanged; a mean-power disagreement there is not itself a sprint target miss.

## New-field excerpts (fictional, not full reports)

These independent synthetic records illustrate display values and branch/status wording. They do not revise the historical examples below. A production report includes the remaining applicable session fields and Last 7 days. Ascent values are the recorded display values, not calculated from route density or compared across sources.

```text
**Ride: Stepped endurance**
Indoor ride
Moving time: 45m
Total time: 47m
Planned: 45m

Distance: 22.00 km
Ascent: 0 m
Avg speed: 29.3 km/h
Temperature: 21.0 °C avg
Range: 20.0–23.0 °C

Power: 152 W avg (2.03 W/kg)
NP: 156 W
Max power: 420 W
Peaks
5 s: 390 W
1 min: 230 W
5 min: 190 W
20 min: 160 W
**Executed structure (paired windows)**
Mapping: followed
0:01–10:00: target 120 W, actual 119 W
10:01–30:00: target 180 W, actual 179 W
30:01–45:00: target 140 W, actual 139 W
Power coverage: 100%
Window agreement: all
Roles: unspecified
Adherence: not evaluable
Reason: main-work role unavailable

Work: 410 kJ

**Ride: Free road ride**
Outdoor ride
Moving time: 1h

Distance: 30.00 km
Ascent: 180 m
Avg speed: 30.0 km/h
Terrain: rolling (6 m/km)
Temperature: 12.0 °C avg
Range: 10.0–14.0 °C
Wind: breezy, 4.0 m/s
Gusts: up to 7.0 m/s

Climbs
12.0 km: 0.6 km at 3.8% (max 6.0%)

Power: 180 W avg
NP: 205 W
**Executed structure (descriptive thirds)**
Plan: unpaired
First 20m: 170 W
Middle 20m: 180 W
Last 20m: 190 W
Power coverage: 100%

**Morning walk**
Moving time: 30m

Distance: 2.50 km
Ascent: 45 m
Pace: 12:00 /km

**Indoor run**
Moving time: 30m

Distance: 3.10 mi
Ascent: 0 ft
Pace: 9:41 /mi (6.2 mph)
Temperature: 68.0 °F avg
Range: 66.0–70.0 °F

**Executed structure (descriptive thirds)**
Plan: unpaired
Power: unavailable

**Outdoor run**
Moving time: 40m

Distance: 6.00 km
Ascent: 70 m
Pace: 6:40 /km (9.0 km/h)

**Executed structure (descriptive thirds)**
Plan: unpaired
Power: unavailable
```

The same ascent rule applies to indoor walks and all ride/run types. When `display.elevation` is null, omit Ascent; a recorded zero remains visible. Walk/Hike omit Executed structure. Shortened or partly-followed windows must distinguish original planned amount from measured time, each agreement flag and any unobserved steps. A not-followed plan uses descriptive fallback and does not present projected step actuals as execution. A synthetic set descriptor `[8,30,10]` can be reported as “8 × 30 s, measured work 232 s, target 280 W, actual 279 W, match true”; it is not 232 seconds of continuous work.

## Decoupling detail excerpts (fictional, separate records)

These snippets illustrate source-supplied half values. Real reports omit the line when detail is unavailable. Decoupling and EF gates remain unchanged; neither a low VI nor a small half difference establishes formal adherence.

```text
Decoupling: 5.26%
Early → late: 180 → 180 W, HR 108 → 114

Decoupling: 2.22%
Early → late: 180 → 200 W
HR: 110 → 125
Plan changes power: no drift verdict

Decoupling: 13.91%
Early → late: 200 → 180 W
HR: 110 → 115
Power trend: falling
```

The first record is an unpaired 120-minute ride with VI 1.02, a 600 s warm-up and 60 s cool-down exclusion, and 15 s HR lag; those exclusions do not change its whole-ride eligibility. The second has qualified step targets changing across step-work halves; its raw value stays visible even if the whole ride passes the gate. The last has lower power and higher HR, which is adverse coupling rather than a power-change explanation. Bucket-derived work and coverage remain contextual estimates. These ratios illustrate arithmetic, not exact reconstruction of rounded real bucket data.

## Example 1: Clean Endurance Day (Multi-Session)

```
**Post-workout: Thursday 15 January**
Data updated: 15 Jan 14:22 UTC
Zone: UTC (fallback)

Summary: Completed 2h30m endurance ride and rowing as scheduled. Clean aerobic execution throughout.

**Ride: Endurance**
Indoor ride
Start: 09:30
Moving time: 2h30m
Planned: 2h30m

Distance: 76.42 km

Power: 155 W avg
NP: 156 W
Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable
IF: 0.57
Power Z1+Z2/Z3/Z4+: 100/0/0%
Session profile: Endurance
Variability Index: 1.01 (good)

HR: 118 avg, 131 max
HR Z1+Z2/Z3/Z4+: 100/0/0%
Cadence: 88 avg
Decoupling: 2.14%
EF: 1.32

Calories: 1396 kcal
Carbs used: 268 g
TSS: 82 (planned 78)
Feel: 2/5 (Good)
RPE: 3/10

**Rowing: Recovery Session**
Start: 12:45
Moving time: 15m

Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable

HR: 125 avg, 141 max
HR Z1+Z2/Z3/Z4+: 100/0/0%

Calories: 165 kcal
TSS: 10 (planned 10)

**Last 7 days**
Phase: Build Wk2

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 2.14% 7d mean(3)
Previous: 2.50% 28d mean(11)
Trend: stable
EF: 1.45 7d mean(4)
Previous: 1.42 28d mean(14)
Trend: stable
HRRc: 36 bpm 28d mean(5); 7d: no data
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: -4.85
CTL: 71.20
ATL: 76.05
Ramp rate: 0.52
ACWR: 1.07 (optimal)
Recovery Index: 0.92

Hours: 12h24m
TSS: 410

**Interpretation**

Quality: Planned bike duration was completed, but step-power adherence is unavailable. Decoupling 2.14% over 2h30m at VI 1.01 supports aerobic control.

Load: Rowing stayed in Z1+Z2 and TSB is -4.85.

Next: Review morning readiness before tomorrow's endurance ride and ski erg.

**Tomorrow**
Ride: Endurance 2h15m, 1h30m @173W
Ski erg: Z2 HR 10m
```

---

## Example 2: Multi-Sport Day (Short Ride + Bike + Ski erg + Walk)

```
**Post-workout: Wednesday 11 March**
Data updated: 11 Mar 18:02 UTC
Zone: UTC (fallback)

Summary: Tempo ride exceeded planned load; short ride, ski erg and walk were also logged.

**Ride: Training Session**
Outdoor ride
Start: 09:42
Moving time: 5m

Distance: 1.80 km
Terrain: rolling (12.4 m/km)

Power: 72 W avg
NP: 128 W
Executed structure: unavailable
Reason: no matched step detail
IF: 0.49

HR: 112 avg, 124 max

TSS: 2
Feel: 2/5 (Good)
RPE: 1/10

**Ride: Training Session**
Outdoor ride
Start: 10:05
Moving time: 2h12m
Planned: 2h

Distance: 58.37 km

Power: 142 W avg
NP: 162 W
Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable
IF: 0.66
Power Z1+Z2/Z3/Z4+: 66/23/11%
Session profile: Tempo
Variability Index: 1.14 (variable)

HR: 135 avg, 158 max
HR Z1+Z2/Z3/Z4+: 100/0/0%
Cadence: 92 avg
Decoupling: -4.12%

Calories: 1240 kcal
Carbs used: 258 g
TSS: 95 (planned 65)
Feel: 2/5 (Good)
RPE: 4/10
Effort response: neutral

**Ski erg**
Start: 13:28
Moving time: 12m
Planned: 10m

Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable

HR: 128 avg, 142 max
HR Z1+Z2/Z3/Z4+: 100/0/0%

Calories: 118 kcal
TSS: 6 (planned 8)

**Walk: Training Session**
Start: 15:10
Moving time: 38m

Distance: 3.40 km

HR: 82 avg, 98 max
HR Z1+Z2/Z3/Z4+: 100/0/0%

Calories: 156 kcal
TSS: 5

**Last 7 days**
Phase: Base Wk3

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 3.20% 7d mean(3)
Previous: 2.75% 28d mean(12)
Trend: stable
EF: 1.38 7d mean(4)
Previous: 1.42 28d mean(15)
Trend: stable
HRRc: 32 bpm 7d mean(2)
Previous: 31 bpm 28d mean(8)
Trend: stable
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: -3.75
CTL: 68.40
ATL: 72.15
Ramp rate: 0.85
ACWR: 1.04 (optimal)
Recovery Index: 0.94

Hours: 11h48m
TSS: 445

**Interpretation**

Quality: The main ride exceeded planned TSS (95 vs 65), with 23% power Z3 and HR fully in Z1+Z2. The available aggregate data does not establish terrain as the cause.

Watch: Decoupling -4.12% is not drift evidence at VI 1.14. The separate 5m ride has no explanatory activity note.

Load: Ski erg and walk were easy secondary sessions, with live ACWR 1.04.

Next: Use tomorrow morning's readiness before the planned threshold session.

**Tomorrow**
Ride: Threshold 1h15m, 3×10m @245W
```

---

## Example 3: Interval Session with Quality Check

```
**Post-workout: Saturday 17 January**
Data updated: 17 Jan 18:05 UTC
Zone: UTC (fallback)

Summary: Threshold session recorded at the planned total duration. Matched step-power data is unavailable.

**Ride: Threshold 3×12m**
Indoor ride
Start: 08:15
Moving time: 1h30m
Planned: 1h30m

Distance: 48.23 km

Power: 178 W avg
NP: 205 W
Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable
IF: 0.80
Power Z1+Z2/Z3/Z4+: 59/3/38%
Session profile: Threshold
Variability Index: 1.15

HR: 138 avg, 162 max
HR Z1+Z2/Z3/Z4+: 61/14/25%
Cadence: 85 avg
Decoupling: 3.82%
HRRc: 34 bpm

Calories: 962 kcal
Carbs used: 196 g
TSS: 95 (planned 90)
Feel: 3/5 (Normal)
RPE: 7/10
Effort response: negative

**Last 7 days**
Phase: Build Wk3

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 2.95% 7d mean(3)
Previous: 2.50% 28d mean(11)
Trend: stable
EF: 1.46 7d mean(4)
Previous: 1.43 28d mean(14)
Trend: stable
HRRc: 34 bpm 7d mean(1)
Previous: 36 bpm 28d mean(5)
Trend: stable
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: -11.40
CTL: 72.80
ATL: 84.20
Ramp rate: 0.78
ACWR: 1.16 (optimal)
Recovery Index: 0.88

Hours: 14h45m
TSS: 485

**Interpretation**

Quality: Whole-session power and Z3 at 3% cannot establish whether the three prescribed steps were met.

Load: Decoupling 3.82% is not interpretable at VI 1.15, while TSB -11.40 is build-load context.

Next: Review morning readiness before tomorrow's recovery spin.

```

---

## Example 4: Shortened Session (Modified)

```
**Post-workout: Tuesday 20 January**
Data updated: 20 Jan 12:48 UTC
Zone: UTC (fallback)

Summary: Endurance ride cut short at 1h30m of planned 2h30m due to knee discomfort. Ski erg skipped.

**Ride: Shortened endurance**
Indoor ride
Start: 10:02
Moving time: 1h30m
Planned: 2h30m

Distance: 45.14 km

Power: 148 W avg
NP: 149 W
Executed structure: unavailable
Reason: no matched step detail
Completion: ride shortened
Adherence: not evaluable
IF: 0.56
Power Z1+Z2/Z3/Z4+: 100/0/0%
Session profile: Endurance
Variability Index: 1.01 (good)

HR: 115 avg, 128 max
HR Z1+Z2/Z3/Z4+: 100/0/0%
Cadence: 86 avg
Decoupling: 1.92%
EF: 1.29

Calories: 800 kcal
Carbs used: 153 g
TSS: 47 (planned 78)

**Skipped workout: Ski erg Training Session**
Reason: knee discomfort after ride

**Last 7 days**
Phase: Base Wk4

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 1.92% 7d mean(2)
Previous: 2.40% 28d mean(10)
Trend: improving
EF: 1.41 7d mean(3)
Previous: 1.42 28d mean(12)
Trend: stable
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: +2.35
CTL: 70.50
ATL: 68.15
Ramp rate: -0.30
ACWR: 0.97 (optimal)
Recovery Index: 0.95

Hours: 4h15m
TSS: 132

**Interpretation**

Quality: The ride was shortened because of knee discomfort. Its completed 1h30m was steady, with decoupling 1.92% and VI 1.01.

Load: TSS 47 versus planned 78 leaves a lighter day than intended.

Next: Check whether the knee discomfort persists before deciding on tomorrow's session.

```

---

## Example 5: Rest Day (Active Recovery Walk)

```
**Post-workout: Thursday 22 January**
Data updated: 22 Jan 16:45 UTC
Zone: UTC (fallback)

Summary: Rest day walk in the rain. Low intensity, full recovery zone.

**Walk: Training Session**
Start: 14:30
Moving time: 1h

Distance: 5.10 km

HR: 78 avg, 96 max
HR Z1+Z2/Z3/Z4+: 100/0/0%

Calories: 210 kcal
TSS: 6

**Last 7 days**
Phase: Base Wk2

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 2.30% 7d mean(3)
Previous: 2.55% 28d mean(11)
Trend: stable
EF: 1.44 7d mean(4)
Previous: 1.43 28d mean(13)
Trend: stable
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: +0.85
CTL: 73.10
ATL: 72.25
Ramp rate: -1.20
ACWR: 0.82 (optimal)
Recovery Index: 0.91

Hours: 15h30m
TSS: 498

**Interpretation**

Quality: The walk stayed in Z1 and has no duration verdict.

Load: TSB is +0.85 after the current rolling load.

Next: Review morning readiness before tomorrow's planned intensity.

```

---

## Example 6: Long Endurance Ride with DFA a1 Drift Flag

Fictional schema-2 scenario: the full 4h12m recording has verified 1 Hz timing and passes endpoint coverage, sixth coverage and gap checks. `drift_quality.status` is `eligible`, reasons are empty and `interpretable` is true. The session structure confirms continuous easy/endurance work without hard blocks. Fuel and fluid intake were not recorded; "Carbs used" is estimated expenditure, not intake.

```
**Post-workout: Sunday 8 February**
Data updated: 8 Feb 16:30 UTC
Zone: UTC (fallback)

Summary: Long Z2 ride finished 12 minutes beyond plan, with an eligible negative DFA contrast between the original first and last thirds; review fueling, heat and fatigue context.

**Ride: Long endurance**
Outdoor ride
Start: 09:15
Moving time: 4h12m
Planned: 4h

Distance: 118.50 km
Terrain: rolling (8 m/km)

Power: 168 W avg
NP: 171 W
Executed structure: steady endurance
Plan-window mapping: unavailable
Adherence: not evaluable
IF: 0.71
Power Z1+Z2/Z3/Z4+: 96/4/0%
Session profile: Endurance
Variability Index: 1.02 (good)

HR: 132 avg, 154 max
HR Z1+Z2/Z3/Z4+: 98/2/0%
Cadence: 87 avg
Decoupling: 6.85%
EF: 1.30
HRRc: 28 bpm
DFA a1: 0.94 avg
**DFA bands (retained samples)**
Easy: 38%
Endurance: 52%
Tempo: 10%
Supra: 0%
Drift: -0.31 (eligible)

Calories: 2480 kcal
Carbs used: 412 g
TSS: 218 (planned 210)
Feel: 3/5 (Normal)
RPE: 6/10
Effort response: negative

**Last 7 days**
Phase: Base Wk4

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 4.50% 7d mean(3)
Previous: 3.20% 28d mean(13)
Trend: declining
EF: 1.36 7d mean(4)
Previous: 1.41 28d mean(15)
Trend: declining
HRRc: 30 bpm 7d mean(2)
Previous: 33 bpm 28d mean(9)
Trend: declining
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: -8.20
CTL: 78.40
ATL: 86.60
Ramp rate: 0.92
ACWR: 1.10 (optimal)
Recovery Index: 0.86

Hours: 13h05m
TSS: 528

**Interpretation**

Quality: The ride exceeded planned duration by 12 minutes and the supplied structure confirms steady easy/endurance work.

Watch: The eligible -0.31 DFA contrast warrants context review, not a diagnosis; selective loss can still bias it. Decoupling 6.85% and RPE 6 are additional observations.

Next: Review fuel/fluid intake, heat and accumulated fatigue before the next decision. Intake is unknown, and 412g estimated carbohydrate use cannot establish underfueling or justify a new target.

**Tomorrow**
Ride: Recovery 1h, Z1 only
```

---

## Example 7: Sweet Spot Session with Consonant DFA Reading

Fictional schema-2 scenario: 5100 original slots (85 recorded minutes), sufficient session data and passing timing/coverage/gap checks. The only drift reason is `short_session`; 3% supra does not trigger the >15% veto. This revised synthetic example adds an exact paired plan identifying four 10-minute work steps at 245 W, activity-applicable indoor FTP 272 W, and qualified plan_match_v2 actual means of 245 / 247 / 246 / 245 W, each over 599 measured seconds with 100% power coverage. Each is 90.1–90.8% FTP. Recovery/warm-up/cool-down roles are supplied by that fictional prescription, not inferred from lower power. Under the recording-time completion convention the four fully observed 599-second windows establish completion, and every mean is inside the asymmetric power band, so the compliance line reports 4/4 on target. Progression still requires its own gate.

```
**Post-workout: Tuesday 10 February**
Data updated: 10 Feb 11:45 UTC
Zone: UTC (fallback)

Summary: Sweet spot session recorded; DFA a1 describes the internal response to the intended intensity.

**Ride: Sweetspot 4×10m**
Indoor ride
Start: 09:00
Moving time: 1h25m
Planned: 1h25m

Distance: 42.85 km

Power: 195 W avg
NP: 215 W
**Executed structure (paired windows)**
Mapping: followed
Work: 4×10m @245W
Measured: 9m59s each
Means: 245 / 247 / 246 / 245 W
Power coverage: 100%
Roles: supplied by paired intent
Main work: completed
On target: 4/4 steps
Non-main steps: detail unavailable
IF: 0.79
Power Z1+Z2/Z3/Z4+: 50/8/42%
Session profile: Sweetspot
Work steps: 90.1–90.8% FTP
Activity FTP: 272 W
Variability Index: 1.10

HR: 142 avg, 158 max
HR Z1+Z2/Z3/Z4+: 58/22/20%
Cadence: 89 avg
Decoupling: 2.45%
HRRc: 32 bpm
DFA a1: 0.78 avg
**DFA bands (retained samples)**
Easy: 18%
Endurance: 35%
Tempo: 44%
Supra: 3%
Drift: +0.04 (descriptive_only)
Reason: short_session
Recording: under 90 minutes

Calories: 825 kcal
Carbs used: 168 g
TSS: 88 (planned 85)
Feel: 2/5 (Good)
RPE: 6/10
Effort response: neutral

**Last 7 days**
Phase: Build Wk2

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 2.80% 7d mean(2)
Previous: 2.95% 28d mean(12)
Trend: stable
EF: 1.48 7d mean(3)
Previous: 1.45 28d mean(14)
Trend: improving
HRRc: 33 bpm 7d mean(2)
Previous: 32 bpm 28d mean(8)
Trend: stable
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: -6.50
CTL: 76.20
ATL: 82.70
Ramp rate: 0.65
ACWR: 1.08 (optimal)
Recovery Index: 0.93

Hours: 8h12m
TSS: 295

**Interpretation**

Quality: Qualified work actuals support Sweetspot despite VI 1.10 and IF 0.79, with independently evaluated 4/4 work steps on target. DFA tempo share 44% describes the internal response.

Watch: Drift +0.04 is descriptive only because recording is under 90 minutes. A low supra share neither proves a structural cause nor supplies steady easy/endurance context.

Next: Review readiness before tomorrow's endurance session; these observations do not authorize progression.

**Tomorrow**
Ride: Endurance 2h, Z2 steady
```

---

## Example 8: Threshold Intervals with Positive Effort Response

```
**Post-workout: Tuesday 17 February**
Data updated: 17 Feb 10:30 UTC
Zone: UTC (fallback)

Summary: Post-deload threshold session recorded; RPE came in notably low for the IF achieved. Fitness/freshness tell.

**Ride: Threshold 4×10m**
Outdoor ride
Start: 08:30
Moving time: 1h30m
Planned: 1h30m

Distance: 47.20 km
Terrain: flat (3 m/km)

Power: 210 W avg
NP: 238 W
Executed structure: unavailable
Reason: no matched step detail
Adherence: not evaluable
IF: 0.88
Power Z1+Z2/Z3/Z4+: 38/5/57%
Session profile: Threshold
Variability Index: 1.13

HR: 148 avg, 168 max
HR Z1+Z2/Z3/Z4+: 40/26/34%
Cadence: 88 avg
Decoupling: 2.10%
HRRc: 38 bpm

Calories: 892 kcal
Carbs used: 182 g
TSS: 117 (planned 115)
Feel: 1/5 (Strong)
RPE: 5/10
Effort response: positive

**Last 7 days**
Phase: Build Wk1

**Intensity (cycling, power, 1/1 week, 4/4 rides)**
Z1+Z2: 90%
Z3: 3%
Z4+: 7%
TID 7d: Polarized
PI: 2.32

**Capability (cycling, 7d / 28d)**
Durability: 2.30% 7d mean(2)
Previous: 2.65% 28d mean(11)
Trend: improving
EF: 1.58 7d mean(3)
Previous: 1.50 28d mean(13)
Trend: improving
HRRc: 38 bpm 7d mean(2)
Previous: 34 bpm 28d mean(9)
Trend: improving
**TID 28d (cycling, power, 4/4 weeks, 16/16 rides)**
TID: Polarized
PI: 2.32
Drift: consistent

**Load (last 7 days)**

TSB: 3.20
CTL: 72.50
ATL: 69.30
Ramp rate: 0.45
ACWR: 0.95 (optimal)
Recovery Index: 1.08

Hours: 7h48m
TSS: 312

**Interpretation**

Quality: IF 0.88 with RPE 5 is below the 6–8 expectation band and supplies a positive effort-response observation. Positive TSB and improving HRRc are supporting context, not proof of a new capability.

Watch: Decoupling 2.10% is not interpretable at VI 1.13 and session EF is omitted. The improving period EF mean comes from other steady sessions.

Next: Review current readiness before tomorrow's endurance ride and look for agreement across later comparable threshold sessions.

**Tomorrow**
Ride: Endurance 2h, Z2 steady
```

---


## Synthetic power and HR fallback excerpt

Cycling qualifies from period totals. Three of four sessions provide power zones; the fourth has only five-band HR. One source per session yields separate partial blocks, with no mixed basis or duplicate contribution:

```text
**Intensity (cycling, power)**
Coverage: 1/1 week, 3/4 rides
Z1+Z2: 80%
Z3: 15%
Z4+: 5%

**Intensity (cycling, HR)**
Coverage: 1/1 week, 1/4 rides
Z1+Z2: 95%
Z3: 3%
Z4+: 2%

Observed rides: 4 across both bases
```

No drift label follows from these partial buckets. If zone seconds use a different clock from moving time, keep both durations and leave the ratio unavailable:

```text
HR zones: 65m observed
Moving time: 60m
Coverage ratio: unavailable
Reason: clocks not established
```

Never cap the ratio at 100% or assign current FTP to the period.

## Deviating sets with uncompleted reps (synthetic)

An independent paired plan has two sets of eight 40-second work bouts at 310 W, authoritative work roles and retained atomic detail. Set 1 completes all eight on target; set 2 has five ridden bouts, three on target and two below band at 301 W and 299 W. Explicit completion evidence identifies bouts 6-8 as not ridden. The supplied measured set means are 310 W and 306 W; qualified non-main windows are on plan. No aggregate adherence percentage is valid after incomplete main work.

```text
Main work: incomplete
Sets
Set 1 (310 W): 8/8, 310 W avg
Set 2 (310 W): 3/5 ridden, 306 W avg
Reason: set 2 bouts 4–5 below band
Bout 4: 301 W (−9 W)
Bout 5: 299 W (−11 W)
Not ridden: set 2 bouts 6–8
Non-main steps: on plan
```
