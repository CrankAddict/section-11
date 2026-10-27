# 7-day Report Examples

Synthetic values only. Both examples end on Tuesday, independent of the configured week start. Example 1 renders every available template section. The synthetic dossier has no bottle statement, so its equivalents use the documented banana fallback.

## Example 1: mixed sports and plan evidence

Cadence endurance has no steps and a 3300-second plan; Park walk has no steps and a 1800-second plan. Both durations are within tolerance, but the walk receives no duration verdict. Synthetic hard-day coverage is complete on all four observed active dates. Valley endurance is a paired step plan without an assessment. The partly-followed ride has observed off-target steps.

The intensity values illustrate synthetic report_intensity blocks selecting cycling only; walking is excluded from main-sport shares. Power covers all three observed cycling sessions in the rolling week; the independent 28-day block has 14/14 covered sessions across four chunks. Fetch completeness remains unknown. The flagged session has a synthetic power/indoor/260 W zone_reference. These illustrations decode the file-level report intensity schema; counts do not imply exact covered dates.

```text
**7-day report: 8-14 Jul 2026**
Data updated: 14 Jul 15:30

Summary: Three rides and one walk maintained a steady training rhythm.

Phase: Base, week 3
Sessions: 4
Ride: 4h30m, 3 sessions, 225 TSS
Walk: 30m, 1 session, 10 TSS
Hours: 5h (prev 4.75h)
TSS: 235 (prev 220)
Plan: 1 partly followed
Planned without steps: 2

**Highlights**
⚠️ 10 Jul Stepped, step 2 below target

**Key session: ⚠️ 10 Jul Stepped**
Window: step 2, seconds 1801-3600
Target: 190 W for 30m
Actual: 176 W over 1799 seconds
Reason: step 2 below target

**Intensity (cycling, power, 1/1 week, 3/3 rides)**
Z1+Z2: 91% (prev 94%)
Z3: 6% (prev 4%)
Z4+: 3% (prev 2%)
TID 7d: Pyramidal

**TID 28d (cycling, power, 4/4 weeks, 14/14 rides)**
TID: Pyramidal

**Capability (cycling, 7-day avg, 28-day avg)**
Durability: 3.1%, N=2 (3.3%, N=8)
EF: 1.30, N=3 (1.28, N=10)
HRRc: 31 bpm, N=1 (32 bpm, N=4)

**Fitness**
CTL: 42.6 (prev 42.1)
ATL: 44.0
TSB: -1.4
Ramp rate: 0.5 over 7 days
ACWR: 0.92 (optimal)
Recovery Index: 0.93
Hard days: 1
Hard-day coverage: 4/4 active days

**Wellness (7-day avg, prev, 7/7 days)**
HRV: 63 ms (58-68), prev 62
RHR: 51 bpm (49-53), prev 52
Sleep: 7.50h (7.0-8.0), prev 7.25h
Sleep quality: 2.0/4 (2.1/4)

**Weight (7-day avg, prev)**
Weight: 68.2 kg (68.0-68.4), prev 68.1
Weigh-ins: 6

**Feel and RPE (7-day avg, prev, 3 sessions each)**
Feel: 2.0/5 (2.2/5)
RPE: 3.7/10 (3.8/10)

**Section 11 flags**
⚠️ Z3 in easy sessions
Session: 8 Jul Cadence
Z3 by power: 18m
Z3 by HR: 2m
Zones: power, from indoor FTP 260 W
Analysis: check the zone reference

**Fun facts (cycling, descriptive, 3/3 rides)**
Max power (1 s): 715 W (8 Jul Cadence)
Max HR: 176 bpm (12 Jul Valley)

Longest ride: 12 Jul Valley, 2h
Distance: 50 km (outdoor)
Distance ridden: 60 km (indoor)
Distance ridden: 50 km (outdoor)
Climbed: 600 m (outdoor)

**Peaks (8 Jul Cadence unless noted)**
5 s: 610 W
1 min: 350 W
5 min: 240 W (10 Jul Stepped)
20 min: 200 W (12 Jul Valley)
60 min: 175 W (12 Jul Valley)

Time in the saddle: 4h30m

Work: 3000 kJ
(energy of about 28.6 medium bananas)
Carbs used: 250 g
(about 9.3 medium bananas)
Most work in a day: 12 Jul
Work that day: 1400 kJ
Carbs that day: 120 g

**Interpretation**
Load: Load stayed close to the previous seven days and recovery observations held.

Quality: The stepped session's second window fell below target. The no-step ride stayed within its planned duration tolerance; the walk counts only in Plan participation.

Watch: Power and HR disagree on easy-session Z3, which supports checking the recorded zones but does not establish a cause.

Next: Keep the next easy session easy and review recovery before the longer ride.

**Next 7 days**
15 Jul: Ride 45m, Easy spin
18 Jul: Ride 1h45m, Lakeside
```

## Example 2: sparse paired sessions

Recovery spin is a paired step plan without an assessment. Recovery roll has no steps but no available plan name or planned duration, so it has no duration verdict. Sync marks Easy spin indoor; names never determine environment.

```text
**7-day report: 8-14 Jul 2026**
Data updated: 14 Jul 15:30

Summary: Two recorded rides retain plan intent with limited comparison data.

Sessions: 2
Ride: 40m, 2 sessions, 22 TSS
Hours: 0.67h
TSS: 22
Plan: 1 planned without steps

**Fun facts (cycling, descriptive)**
Longest ride: 9 Jul Easy spin, 20m
Distance: 8 km (indoor)
Distance ridden: 8 km (indoor)

Time in the saddle: 40m

**Interpretation**
Quality: Pairing identifies intent but does not establish execution quality.

Watch: Missing power and wellness observations prevent a readiness or capability conclusion.

Next: Obtain current recovery data before the next training decision.
```

Missing comparisons, zero climbing, unavailable peaks, absent equivalents and unplanned upcoming sessions are omitted. The sparse report has no Highlights or inferred success markers.

## Runner intensity fragment

For a synthetic period with running at 88% TSS and cycling at 12%, both sports qualify. Three running sessions supply HR and one ride supplies power, all within the rolling week. Separate buckets yield:

```
**Intensity (cycling, power, 1/1 week, 1/1 ride)**
Z1+Z2: 90%
Z3: 7%
Z4+: 3%
TID 7d: Pyramidal

**Intensity (running, HR, 1/1 week, 3/3 runs)**
Z1+Z2: 75%
Z3: 15%
Z4+: 10%
TID 7d: Pyramidal
```

If report_intensity is missing, state intensity unavailable when material; never reuse a cycling label or old all-sport/primary percentages. A present empty block remains empty. A selected sport without zones gets a short unavailable line, use a swimming heading and separate `Zones: unavailable` and `Coverage: 0/2 sessions` lines, stating that pace mapping is deferred.

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

## Deviating sets fragment

Independent synthetic detail, not part of the two reports above. The authoritative prescription identifies three main-work sets of eight 45-second bouts. Qualified per-bout evidence supplies the counts; set averages do not. Completion evidence confirms that set 3 stopped after rep 4, with reps 3-4 below target and reps 5-8 not ridden. A second session has its own failed plan marker. A separate zone flag without a plan marker adds no Highlight.

```
**Highlights**
⚠️ 13 Jul VO2, set 3 stopped
❌ 14 Jul Tempo, steps off

**Key session: ⚠️ 13 Jul VO2**
Set 1 (300 W): 8/8, 299 W avg
Set 2 (310 W): 8/8, 310 W avg
Set 3 (320 W): 2/8, 305 W avg
Reason: stopped after rep 4
Below target: reps 3-4, 290/288 W
Not ridden: reps 5-8
```
