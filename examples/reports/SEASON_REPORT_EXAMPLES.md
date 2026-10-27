# Season Report Examples

Synthetic fixtures only. Both examples use Sunday-start completed calendar weeks; the current partial week is excluded. Numbers are invented, not athlete data.

## Example 1: cycles, a phase gap and current snapshot

Eight completed weeks run from 17 May through 11 July. The first three ACWR values are unknown; the remaining five are 0.75, 0.90, 1.10, 1.30 and 1.40. The fictional dossier has no stated bottle. The longest cycling row matches the season fact's ID, date and duration, supplying its own 72 km distance. In the sparse example Previous phase equals Phase and is omitted.

The intensity values illustrate synthetic report_intensity_season selecting cycling across eight completed Sunday-start weeks, with 24/24 observed power sessions. Current 28-day cycling has 14/14 sessions across four rolling chunks. Each matched month selects cycling independently using the same mapping and settings: June has 12/12 sessions over five touched weeks on each side. Fetch completeness is unknown; all-sport hours are not intensity weights. These illustrations decode the file-level report intensity schema; counts do not imply exact covered dates.

```text
**Season report: 17 May-11 Jul 2026**
Data updated: 14 Jul 15:30
History updated: 12 Jul 08:00

Summary: Eight completed weeks show consistent volume, with more training than last June.

**Position**
Season: Mid Season
Phase: Base, week 3
Previous phase: Deload

**Phases**
17 May-20 Jun: Build 4 weeks, Deload 1
21-27 Jun: no detected phase
28 Jun-11 Jul: Base 2 weeks

**Volume (8 completed weeks)**
Hours: 40h (avg 5 h/week)
TSS: 1880 (avg 235/week)
Longest ride: 28 Jun Meadow, 2h45m
Distance: 72 km (outdoor)
Longest week: 6.5h, week of 21 Jun

**Fitness**
CTL peak: 44.2, week of 21 Jun
CTL now: 42.6, 14 Jul
ACWR below 0.8: 1
ACWR 0.8 through 1.3: 3
ACWR above 1.3 through 1.5: 1
ACWR known: 5 of 8 weeks

**Intensity (cycling, power, 8/8 weeks, 24/24 rides)**
Z1+Z2: 92%
Z3: 5%
Z4+: 3%

**TID 28d (now, cycling, power, 4/4 weeks, 14/14 rides)**
TID: Pyramidal

**Hard days (8 completed weeks, avg/week)**
Hard days: 1.5
First half (17 May-13 Jun): 1.5
Second half (14 Jun-11 Jul): 1.5
Weeks with a hard day: 8 of 8

**June 2026 (June 2025 in brackets)**
Hours: 23h (20h)
Apr-Jun monthly avg hours: 21h (19h)
TSS: 1050 (900)
Apr-Jun monthly avg TSS: 980 (870)
CTL peak: 44.2 (40.5)
CTL end: 43.8 (39.9)
Hard days: avg 1.8/week (1.5/week)
Longest (cycling): 2.75h (2.5h)
HRV: avg 62 ms (59 ms)
RHR: avg 52 bpm (54 bpm)

**June intensity (cycling, power, 5/5 weeks, 12/12 rides each year)**
Z1+Z2: 90% (93%)
Z3: 6% (4%)
Z4+: 4% (3%)

**Notable**
Z3 above 5%: 3 of 8 completed weeks

**Fun facts (cycling, descriptive, 24/24 rides)**
Max power (1 s): 810 W (27 May Ridge)
Max HR: 181 bpm (27 May Ridge)

Distance ridden: 250 km (indoor)
Distance ridden: 530 km (outdoor)
Climbed: 700 m (indoor)
Climbed: 4300 m (outdoor)

**Peaks (27 May Ridge unless noted)**
5 s: 690 W
1 min: 380 W
5 min: 265 W (25 Jun Hill)
20 min: 225 W (28 Jun Meadow)
60 min: 200 W (28 Jun Meadow)

Time in the saddle: 37h

Work: 26000 kJ
(energy of about 247.6 medium bananas)
Carbs used: 2200 g
(about 81.5 medium bananas)
Most work in a day: 28 Jun
Work that day: 2100 kJ
Carbs that day: 180 g
Most work in a week: 21-27 Jun
Work that week: 4500 kJ
Carbs that week: 400 g

**Interpretation**
Load: Completed-week volume supports a larger training base, though three unknown ACWR weeks limit the load distribution summary.

Year on year: The matched June comparison shows more training and higher end-of-month CTL.

Watch: Z3 is a recurring pattern to review. Current TID is a separate 28-day observation and does not establish a Season-wide classification.

Next: Review current recovery and the planned phase before choosing the next cycle's load.
```

## Example 2: short history and partial power coverage

Two completed Sunday-start weeks are available. One ACWR value is 0.95; the other is unknown. There is no prior-year match. Only retained power and moving-time facts are supplied. This older history has no report_intensity_season block.

```text
**Season report: 28 Jun-11 Jul 2026**
Data updated: 14 Jul 15:30
History updated: 12 Jul 07:00

Summary: Two completed weeks are available for a limited Season view.

**Position**
Phase: Base, week 2

**Phases**
28 Jun-4 Jul: Base 1 week
5-11 Jul: no detected phase

**Volume (2 completed weeks)**
Hours: 8h (avg 4 h/week)
TSS: 320 (avg 160/week)

**Fitness**
ACWR 0.8 through 1.3: 1
ACWR above 1.3: none
ACWR known: 1 of 2 weeks

**Intensity**
Season zones: unavailable
Reason: no period intensity block

Fun facts: unavailable
Reason: no period sport selection

**Interpretation**
Load: The completed weeks support a volume summary, with only one known coupled ACWR value.

Watch: No matched prior-year month is available. Missing period selection prevents a Fun facts block.

Next: Obtain compatible history before deciding whether a longer-term load change is warranted.
```

Zero bins, empty Notable lines, absent equivalents and missing metrics are omitted. A phase gap is never bridged. Peaks live in Fun facts, not a separate Best efforts section.

## Synthetic seasonal selection and unmatched sports

In 24 completed weeks, cycling contributes 92% TSS/88% time with twenty 4.4-hour weeks. Four three-hour ski weeks supply 8% TSS/12% time and pass the guarded weekly-winner floor of 2.2 hours. Both sports are selected in report_intensity_season; current cycling primacy does not relabel the ski weeks. Every included observation contributes, even if its sport did not qualify in its own week.

```
**Intensity (cycling, power, 20/24 weeks, 60/60 rides, 20 active weeks)**
Z1+Z2: 90%
Z3: 7%
Z4+: 3%

**Intensity (Nordic skiing, HR, 4/24 weeks, 12/12 sessions, 4 active weeks)**
Z1+Z2: 85%
Z3: 10%
Z4+: 5%
```

A separate matched-month example has only cycling this year and only Nordic skiing last year. Show the independently selected union without pairing unlike sports:

```
**Month intensity (cycling, power, current: 4/4 weeks, 8/8 rides)**
Z1+Z2: 90% (prior unavailable)
Z3: 7% (prior unavailable)
Z4+: 3% (prior unavailable)

**Month intensity (Nordic skiing, HR, prior: 4/4 weeks, 8/8 sessions)**
Z1+Z2: unavailable (prior 85%)
Z3: unavailable (prior 10%)
Z4+: unavailable (prior 5%)
```

Missing sport evidence is not zero. With different mapping versions, show separate labelled observations and mark the comparison unavailable. Never add overlapping monthly tiers or classify Season from these distributions.

## Selected-sport fact fragments

Each independent synthetic fragment assumes its named sport is selected for this report's period and that the matching facts are compatible. Snow ascent has no observations. Rowing duration coverage is partial; a longest session's distance is its own distance. Season longest sessions remain in Volume.

```
**Fun facts (running, descriptive)**
Max HR: 172 bpm, 12 Jul, Park loop

Distance run: 18 km (outdoor)
Climbed: 160 m (outdoor)

Running time: 1h50m

**Fun facts (swimming, descriptive)**
Max HR: 158 bpm, 10 Jul, Lake swim
HR coverage: 2 of 3 sessions

Distance swum: 2 km (pool/other)
Distance swum: 1.8 km (open water)

Swimming moving time: 1h30m

**Fun facts (Nordic skiing, descriptive)**
Max HR: 165 bpm, 11 Jul, Steady ski

Distance skied: 12 km (snow)
Distance skied: 8 km (roller)
Distance skied: 10 km (indoor)
Climbed: 90 m (roller)

Nordic skiing time: 2h30m

**Fun facts (rowing, descriptive)**
Max HR: 162 bpm, 12 Jul, Steady row

Distance rowed: 24 km (indoor)
Indoor distance: 2 of 3 sessions
Distance rowed: 6 km (outdoor)

Rowing time: 2h30m
Time coverage: 3 of 4 sessions
```
