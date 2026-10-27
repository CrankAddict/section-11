# 28-day Report Examples

Synthetic fixtures only. The four supplied chunks are newest first in JSON and displayed oldest first. Chunk 1 agrees with 7_DAY_REPORT_EXAMPLES.md. The fictional dossier states in prose: "Each training bottle contains 60 g carbohydrate." This is sufficient bottle evidence without a table.

## Example 1: four rolling chunks

Intensity illustrates synthetic period-local report_intensity blocks selecting cycling in each chunk and the whole 28-day window. Walks remain below selection thresholds. Cycling has 4, 4, 3 and 3 covered sessions in chronological chunks, 14 in total. Fetch completeness is unknown. The flagged activity has a synthetic power/outdoor/270 W zone_reference. All twelve checked activities are rides, including three partly-followed sessions on 18 June, 25 June and 10 July; walks are participation only. Hard-day coverage is complete on observed active dates in each chunk. Capability means retain all eligible observations; wellness on the second chunk has only six observed days. The 28 June tempo illustration supplies plan_changes_power. These illustrations decode the file-level report intensity schema; counts do not imply exact covered dates.

```text
**28-day report: 17 Jun-14 Jul 2026**
Data updated: 14 Jul 15:30

Summary: The most recent two chunks carry less load than the first two.

Phase: Base, week 3

**Totals**
Ride: 20h45m, 14 sessions, 995 TSS
Walk: 1h30m, 3 sessions, 30 TSS
Total: 22.25h, 17 sessions, 1025 TSS

**Plan**
Rides: 12 of 14 planned
Walks: 3 of 3 planned
Checked: 9 of 12 followed
Step detail: last 14 days
Older results: last captured

**Fitness (start of period -> now)**
CTL: 41.8 -> 42.6 (+0.8)
ATL: 46.0 -> 44.0 (-2.0)
TSB: -4.2 -> -1.4 (+2.8)

**Week by week (oldest first, 7-day avg for means, Durability/EF cycling)**
Weeks: 17 Jun, 24 Jun, 1 Jul, 8 Jul
Hours: 6h, 6.5h, 4.75h, 5h
TSS: 270, 300, 220, 235
CTL: 43.2, 43.8, 42.1, 42.6
Hard days: 2, 2, 1, 1
Hard-day coverage: complete
Durability: 3.6, 3.4, 3.1, 3.1%
EF: 1.25, 1.27, 1.29, 1.30
HRRc: 33, 32, 32, 31 bpm
HRV: 61, 62, 62, 63 ms
RHR: 53, 52, 52, 51 bpm
Sleep: 7.00h, 7.25h, 7.25h, 7.50h
HRV/RHR/Sleep N (24 Jun): 6/7 days

**Weekly intensity (cycling, power, 4/4 weeks, 14/14 rides)**
Z1+Z2: 89, 86, 94, 91%
Z3: 7, 10, 4, 6%
Z4+: 4, 4, 2, 3%

**Wellness (28-day avg)**
HRV: 62 ms
RHR: 52 bpm
Sleep: 7.25h
HRV/RHR/Sleep coverage: 27/28 days
Sleep quality: 2.1/4
Sleep quality coverage: 25/28 days
Weight latest: 68.0 kg (14 Jul)
Weight avg: 68.1 kg
Weigh-ins: 22
Weight trend: +0.08 kg/week
Feel: 2.1/5
RPE: 3.9/10
Feel/RPE coverage: 11 sessions

**Intensity (cycling, power, 4/4 weeks, 14/14 rides)**
Z1+Z2: 90%
Z3: 7%
Z4+: 3%
TID 28d: Pyramidal

**Highlights**
⚠️ 18 Jun Intervals, steps off
⚠️ 25 Jun Hill, steps off
⚠️ 10 Jul Stepped, step 2 below target

**Key session: ⚠️ 10 Jul Stepped**
Target: step 2, 190 W for 30m
Actual: 176 W over 1799 seconds
Reason: step 2 below target

**Key observations**
Long ride: 28 Jun Meadow, 2h45m
VI: 1.03
Tempo 21 Jun: 3.8%
Tempo 28 Jun: 3.4% (plan changes power)

**Best efforts (cycling, prev 28 days)**
5 s: 670 W, 25 Jun (700 W)
1 min: 370 W, 25 Jun (380 W)
5 min: 265 W, 25 Jun (260 W)
20 min: 225 W, 28 Jun (219 W)
60 min: 200 W, 28 Jun (198 W)
HR 20 min: 158 bpm (160 bpm)
Shift: Short efforts were lower and sustained efforts were slightly higher.

**DFA a1 (cycling, 28-day avg, descriptive)**
DFA a1: 1.18
Drift: -0.04
Drift coverage: 3 eligible sessions
Sufficient sessions: 4
Coverage: retained summaries only
Easy-state guard: 138 bpm
Guard coverage: 3 eligible sessions
Indoor guard: 151 W, N=3

**Section 11 flags**
⚠️ Z3 in easy sessions
Session: 28 Jun Meadow
Z3 by power: 36m
Z3 by HR: 3m
Zones: power, from outdoor FTP 270 W
Analysis: check the zone reference

**Fun facts (cycling, descriptive, 14/14 rides)**
Max power (1 s): 780 W (25 Jun Hill)
Max HR: 179 bpm (25 Jun Hill)

Longest ride: 28 Jun Meadow, 2h45m
Distance: 72 km (outdoor)
Distance ridden: 180 km (indoor)
Distance ridden: 330 km (outdoor)
Climbed: 350 m (indoor)
Climbed: 2600 m (outdoor)

Time in the saddle: 20h45m

**Equivalents (your 60 g bottles)**
Work: 14000 kJ
(energy of about 58.3 bottles)
Carbs used: 1200 g
(about 20.0 bottles)
Most work in a day: 28 Jun
Work that day: 2100 kJ
Carbs that day: 180 g
Most work in a week: 24-30 Jun
Work that week: 4500 kJ
Carbs that week: 400 g

**Interpretation**
Load: Volume fell in the latter two chunks while EF and wellness observations held.

Quality: Nine of twelve checked rides followed the plan. The two older misses retain last-captured assessments; the recent stepped session's second window was below target.

Watch: The power-only hard day and HR disagreement support a zone check, not a proven cause or intentional intensity. The 28 June tempo value carries a changing-power plan and supplies no drift verdict; limited DFA coverage supports no threshold change.

Next: Review recovery and the zone reference before deciding whether to raise the next block's load.
```

## Example 2: sparse data

Only the shown observations exist. The two middle chunks have supplied zero hours/TSS and unavailable capability/wellness; their positions remain in each populated series. A supplied zero is an observed subtotal, not proof of rest or complete retrieval. Paired structured plans without step assessments do not acquire duration-only verdicts.

```text
**28-day report: 17 Jun-14 Jul 2026**
Data updated: 14 Jul 15:30

Summary: The export contains limited observations for the rolling window.

**Totals**
Ride: 1.67h, 5 sessions, 62 TSS
Total: 1.67h, 5 sessions, 62 TSS

**Plan**
Rides: 5 of 5 planned ✅

**Week by week (oldest first, 7-day avg for means)**
Weeks: 17 Jun, 24 Jun, 1 Jul, 8 Jul
Hours: 1h, 0h, 0h, 0.67h
TSS: 40, 0, 0, 22
EF: 1.20, unavailable, unavailable, 1.23
HRV: 60, unavailable, unavailable, 61 ms
HRV N (17 Jun): 2/7 days
HRV N (8 Jul): 1/7 days

**Wellness (28-day avg)**
HRV: 60.3 ms
HRV coverage: 3/28 days

**Interpretation**
Quality: Five sessions were paired to plans across the window.

Watch: Pairing alone does not establish execution quality, and the sparse observations do not support a continuous training trend.

Next: Obtain the missing observations before choosing a load change.
```

When LT1/LT2 estimates are absent, their rows are absent. An eligible easy-state guard remains visible independently of threshold confidence; a null drift estimate is never displayed as zero.

## Synthetic ski holiday and indoor ski fragment

For 28 September to 25 October, cycling supplies 75% TSS/60% time and Nordic skiing 25%/40%. Nordic skiing combines four outdoor Nordic ski sessions and one indoor ski session in the 5-11 October chunk, all using the same five-band HR mapping. Cycling has eight power sessions in the other three chunks. The independently selected whole-period lines are:

**Intensity fragment**

```
**Intensity (cycling, power, 3/4 weeks, 8/8 rides, 3 active weeks)**
Z1+Z2: 90%
Z3: 7%
Z4+: 3%

**Intensity (Nordic skiing, HR, 1/4 weeks, 5/5 sessions, 1 active week)**
Z1+Z2: 85%
Z3: 10%
Z4+: 5%
```

These describe observed sessions; activity-fetch completeness is unknown. If a sixth ski session lacks zones, show 5/6 and partial coverage without a whole-period drift claim. Keep a separate power or incompatible HR-mapping bucket if one occurs; never label the line mixed.

## Selected-sport fact fragments

Each independent synthetic fragment assumes its named sport is selected for this report's period and that the matching facts are compatible. Snow ascent has no observations. Rowing duration coverage is partial; a longest session's distance is its own distance. Season longest sessions remain in Volume.

```
**Fun facts (running, descriptive)**
Max HR: 172 bpm, 12 Jul, Park loop

Longest run: Park loop, 12 Jul, 1h,
10 km (outdoor)
Distance run: 18 km (outdoor)
Climbed: 160 m (outdoor)

Running time: 1h50m

**Fun facts (swimming, descriptive)**
Max HR: 158 bpm, 10 Jul, Lake swim
HR coverage: 2 of 3 sessions

Longest swim: Lake swim, 10 Jul, 40m,
1.8 km (open water)
Distance swum: 2 km (pool/other)
Distance swum: 1.8 km (open water)

Swimming moving time: 1h30m

**Fun facts (Nordic skiing, descriptive)**
Max HR: 165 bpm, 11 Jul, Steady ski

Longest Nordic session: Snow loop,
12 Jul, 1h, 12 km (snow)
Distance skied: 12 km (snow)
Distance skied: 8 km (roller)
Distance skied: 10 km (indoor)
Climbed: 90 m (roller)

Nordic skiing time: 2h30m

**Fun facts (rowing, descriptive)**
Max HR: 162 bpm, 12 Jul, Steady row

Longest row: Steady row, 12 Jul, 1h,
12 km (indoor)
Longest coverage: 3 of 4 sessions
Distance rowed: 24 km (indoor)
Indoor distance: 2 of 3 sessions
Distance rowed: 6 km (outdoor)

Rowing time: 2h30m
Time coverage: 3 of 4 sessions
```
