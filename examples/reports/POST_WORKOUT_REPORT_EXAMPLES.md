# Post-Workout Report Examples

> Anonymized examples showing standard post-workout report format.  
> See `POST_WORKOUT_REPORT_TEMPLATE.md` for field reference.

---

## Example 1: Clean Endurance Day (Multi-Session)

```
Data (last_updated UTC: 2026-01-15T14:22:08)

Completed 2h30m endurance ride and rowing as scheduled. Clean aerobic execution throughout.

Completed workout: VirtualRide Endurance - Wednesday
Start time: 09:30:15
Duration: 2h30m (planned 2h30m)
Distance: 76.4 km
Power: 155 W avg / 156 W NP
Power zones: 12% Zone 1, 88% Zone 2
Grey Zone (Z3): 0%
Quality (Z4+): 0%
Session profile: Endurance
HR: 118 avg / 131 max
HR zones: 100% Zone 1
Cadence: 88 avg
Decoupling: 2.14% (good)
EF: 1.32
Variability Index: 1.01 (good)
Calories: 1396 kcal
Carbs used: 268 g
TSS: 82 (planned 78)
Feel: 2/5 (Good)
RPE: 3/10

Completed workout: VirtualRowing Recovery Session
Start time: 12:45:00
Duration: 15m
HR: 125 avg / 141 max
HR zones: 68% Zone 1, 32% Zone 2
Calories: 165 kcal
TSS: 10 (planned 10)

Weekly totals (rolling 7d):
Phase: Build Wk2
Polarization: Z1+Z2 97%, Z3 1%, Z4+ 3%
Durability: 2.14% 7d mean(3) / 2.50% 28d mean(11) (stable)
EF: 1.45 7d mean(4) / 1.42 28d mean(14) (stable)
HRRc: 36 bpm 28d mean(5) — 7d: no data
TID 28d: Polarized (PI: 3.18) — drift: consistent
TSB: -4.85
CTL: 71.20
ATL: 76.05
Ramp rate: 0.52
ACWR: 1.07 (optimal)
Recovery Index: 0.92
Hours: 12h24m
TSS: 410

Interpretation:
Both sessions compliant with plan. Bike decoupling 2.14% over 2h30m shows solid aerobic control.
Rowing stayed in Z1-Z2 as prescribed. Load tracking well — TSB manageable heading into Thursday.

Tomorrow: Endurance 2h15m, 1h30m @173W + SkiErg 10m Z2 HR
```

---

## Example 2: Multi-Sport Day (Short Ride + Bike + SkiErg + Walk)

```
Data (last_updated UTC: 2026-03-11T18:02:14)

Tempo ride overshot planned load due to terrain; short ride, SkiErg, and walk also logged.

Completed workout: Ride Training Session
Start time: 09:42:18
Duration: 5m
Distance: 1.8 km
Power: 72 W avg / 128 W NP
HR: 112 avg / 124 max
TSS: 2
Feel: 2/5 (Good)
RPE: 1/10

Completed workout: Ride Training Session
Start time: 10:05:33
Duration: 2h12m (planned 2h00m)
Distance: 58.4 km
Power: 142 W avg / 162 W NP
Power zones: 30% Zone 1, 36% Zone 2
Grey Zone (Z3): 23%
Quality (Z4+): 11%
Session profile: Tempo
HR: 135 avg / 158 max
HR zones: 84% Zone 1, 16% Zone 2
Cadence: 92 avg
Decoupling: -4.12% (good)
EF: 1.20
Variability Index: 1.14 (variable)
Calories: 1240 kcal
Carbs used: 258 g
TSS: 95 (planned 65)
Feel: 2/5 (Good)
RPE: 4/10

Completed workout: VirtualSki SkiErg
Start time: 13:28:00
Duration: 12m (planned 10m)
HR: 128 avg / 142 max
HR zones: 65% Zone 1, 35% Zone 2
Calories: 118 kcal
TSS: 6 (planned 8)

Completed workout: Walk Training Session
Start time: 15:10:22
Duration: 38m
Distance: 3.4 km
HR: 82 avg / 98 max
HR zones: 100% Zone 1
Calories: 156 kcal
TSS: 5

Weekly totals (rolling 7d):
Phase: Base Wk3
Polarization: Z1+Z2 88%, Z3 7%, Z4+ 5% — Polarized (PI: 1.85)
Durability: 3.20% 7d mean(3) / 2.75% 28d mean(12) (stable)
EF: 1.38 7d mean(4) / 1.42 28d mean(15) (stable)
HRRc: 32 bpm 7d mean(2) / 31 bpm 28d mean(8) (stable)
TID 28d: Polarized (PI: 2.42) — drift: consistent
TSB: -3.75
CTL: 68.40
ATL: 72.15
Ramp rate: 0.85
ACWR: 1.04 (optimal)
Recovery Index: 0.94
Hours: 11h48m
TSS: 445

Interpretation:
Main ride overshot planned TSS (95 vs 65) due to terrain variability — VI 1.14 and 23% grey zone
confirm the outdoor premium — but HR stayed fully in Z1-Z2 and negative decoupling (-4.12%) shows
aerobic response was clean. Short 5m ride logged separately; no `description` or `chat_notes`
attached, reported as-is. SkiErg and walk executed as easy secondary sessions. Load tracking
normally at ACWR 1.04.

Tomorrow: Threshold 1h15m, 3×10m @245W
```

---

## Example 3: Interval Session with Quality Check

```
Data (last_updated UTC: 2026-01-17T18:05:33)

Completed threshold intervals as scheduled. Power targets hit, HR response appropriate.

Completed workout: VirtualRide 3x12min Threshold - Friday
Start time: 08:15:42
Duration: 1h30m (planned 1h30m)
Distance: 48.2 km
Power: 178 W avg / 205 W NP
Power zones: 28% Zone 1, 31% Zone 2
Grey Zone (Z3): 3%
Quality (Z4+): 37%
Session profile: Threshold
HR: 138 avg / 162 max
HR zones: 32% Zone 1, 29% Zone 2, 14% Zone 3, 25% Zone 4
Cadence: 85 avg
Decoupling: 3.82% (good)
EF: 1.49
HRRc: 34 bpm
Variability Index: 1.15
Calories: 962 kcal
Carbs used: 196 g
TSS: 95 (planned 90)
Feel: 3/5 (Normal)
RPE: 7/10

Weekly totals (rolling 7d):
Phase: Build Wk3
Polarization: Z1+Z2 84%, Z3 2%, Z4+ 13%
Durability: 2.95% 7d mean(3) / 2.50% 28d mean(11) (stable)
EF: 1.46 7d mean(4) / 1.43 28d mean(14) (stable)
HRRc: 34 bpm 7d mean(1) / 36 bpm 28d mean(5) (stable)
TID 28d: Polarized (PI: 3.10) — drift: consistent
TSB: -11.40
CTL: 72.80
ATL: 84.20
Ramp rate: 0.78
ACWR: 1.16 (optimal)
Recovery Index: 0.88
Hours: 14h45m
TSS: 485

Interpretation:
Interval targets met — all three efforts within ±3W of prescribed power. Z3 at 3% is
from warm-up/cool-down transitions, not drift. Decoupling 3.82% across interval session is
acceptable. TSB at -11.40 reflects build week loading. Recovery spin tomorrow. 🔄
```

---

## Example 4: Shortened Session (Modified)

```
Data (last_updated UTC: 2026-01-20T12:48:55)

Endurance ride cut short at 1h30m of planned 2h30m due to knee discomfort. SkiErg skipped.

Completed workout: VirtualRide Endurance - Monday (modified)
Start time: 10:02:18
Duration: 1h30m (planned 2h30m)
Distance: 45.1 km
Power: 148 W avg / 149 W NP
Power zones: 19% Zone 1, 81% Zone 2
Grey Zone (Z3): 0%
Quality (Z4+): 0%
Session profile: Endurance
HR: 115 avg / 128 max
HR zones: 100% Zone 1
Cadence: 86 avg
Decoupling: 1.92% (good)
EF: 1.29
Variability Index: 1.01 (good)
Calories: 800 kcal
Carbs used: 153 g
TSS: 47 (planned 78)

Skipped workout: VirtualSki Training Session
Reason: Precautionary — knee discomfort from ride

Weekly totals (rolling 7d):
Phase: Base Wk4
Polarization: Z1+Z2 98%, Z3 0%, Z4+ 2%
Durability: 1.92% 7d mean(2) / 2.40% 28d mean(10) (improving)
EF: 1.41 7d mean(3) / 1.42 28d mean(12) (stable)
TID 28d: Polarized (PI: 3.15) — drift: consistent
TSB: +2.35
CTL: 70.50
ATL: 68.15
Ramp rate: -0.30
ACWR: 0.97 (optimal)
Recovery Index: 0.95
Hours: 4h15m
TSS: 132

Interpretation:
Session cut short — right call given the knee discomfort. Aerobic quality during the 1h30m
was excellent (decoupling 1.92%, VI 1.00). TSS 47 vs planned 78 means a lighter day than
intended. Monitor knee before tomorrow's session. If persistent, consider swapping to
upper-body only. 🩹
```

---

## Example 5: Rest Day (Active Recovery Walk)

```
Data (last_updated UTC: 2026-01-22T16:45:12)

Rest day walk in the rain. Low intensity, full recovery zone.

Completed workout: Walk Training Session
Start time: 14:30:08
Duration: 1h
Distance: 5.1 km
HR: 78 avg / 96 max
HR zones: 100% Zone 1
Calories: 210 kcal
TSS: 6

Weekly totals (rolling 7d):
Phase: Base Wk2
Polarization: Z1+Z2 97%, Z3 0%, Z4+ 3%
Durability: 2.30% 7d mean(3) / 2.55% 28d mean(11) (stable)
EF: 1.44 7d mean(4) / 1.43 28d mean(13) (stable)
TID 28d: Polarized (PI: 3.22) — drift: consistent
TSB: +0.85
CTL: 73.10
ATL: 72.25
Ramp rate: -1.20
ACWR: 0.82 (optimal)
Recovery Index: 0.91
Hours: 15h30m
TSS: 498

Interpretation:
Easy recovery walk, entirely in Z1 as expected on a rest day. TSB positive at +0.85 —
recovering well heading into tomorrow's interval session. Braved the rain at 4°C too. 🌧️
```

---

## Example 6: Long Endurance Ride with DFA a1 Drift Flag

```
Data (last_updated UTC: 2026-02-08T16:30:00)

Long Z2 ride completed at planned duration but DFA a1 drifted negative across the second half — fueling/heat signal worth noting.

Completed workout: Ride Long Endurance - Saturday
Start time: 09:15:00
Duration: 4h12m (planned 4h00m)
Distance: 118.5 km
Power: 168 W avg / 174 W NP
Power zones: 18% Zone 1, 78% Zone 2
Grey Zone (Z3): 4%
Quality (Z4+): 0%
Session profile: Endurance
HR: 132 avg / 154 max
HR zones: 62% Zone 1, 36% Zone 2, 2% Zone 3
Cadence: 87 avg
Decoupling: 6.85% (watch)
EF: 1.32
HRRc: 28 bpm
Variability Index: 1.06 (good)
DFA a1: 0.94 avg, 38% Z2/52% transition/10% SS/0% above LT2 (drift -0.31, interpretable)
Calories: 2480 kcal
Carbs used: 412 g
TSS: 218 (planned 210)
Feel: 3/5 (Normal)
RPE: 6/10

Weekly totals (rolling 7d):
Phase: Base Wk4
Polarization: Z1+Z2 92%, Z3 5%, Z4+ 3%
Durability: 4.50% 7d mean(3) / 3.20% 28d mean(13) (declining)
EF: 1.36 7d mean(4) / 1.41 28d mean(15) (declining)
HRRc: 30 bpm 7d mean(2) / 33 bpm 28d mean(9) (declining)
TID 28d: Polarized (PI: 2.95) — drift: consistent
TSB: -8.20
CTL: 78.40
ATL: 86.60
Ramp rate: 0.92
ACWR: 1.10 (optimal)
Recovery Index: 0.86
Hours: 13h05m
TSS: 528

Interpretation:
Duration and external load on plan, but multiple internal signals point to a costly session.
DFA a1 averaged 0.94 with 52% of the ride in the transition band (0.75–1.0) rather than the
expected >75% above 1.0 for a Z2 ride — internal intensity ran higher than prescribed
external power. The drift of -0.31 across the session is interpretable (no time above LT2 to
distort it) and crosses the threshold for fueling/heat/fatigue cross-reference per DFA a1
Protocol §Session Interpretation. Decoupling 6.85% and HRRc dropping to 28 bpm reinforce the
same picture. Carbs in (412g, ~98g/h) were on the lower bound for a 4h+ ride at this
intensity — raise to 110–120g/h on the next long ride and see if DFA holds. Easy day tomorrow
regardless. 🥵

Tomorrow: Recovery 1h, Z1 only
```

---

## Example 7: Sweet Spot Session with Consonant DFA Reading

```
Data (last_updated UTC: 2026-02-10T11:45:00)

Sweet spot intervals on plan; DFA a1 confirms internal intensity matched the prescription.

Completed workout: VirtualRide 4x10min Sweetspot - Tuesday
Start time: 09:00:00
Duration: 1h25m (planned 1h25m)
Distance: 42.8 km
Power: 195 W avg / 215 W NP
Power zones: 22% Zone 1, 28% Zone 2
Grey Zone (Z3): 8%
Quality (Z4+): 42%
Session profile: Sweetspot
HR: 142 avg / 158 max
HR zones: 25% Zone 1, 33% Zone 2, 22% Zone 3, 20% Zone 4
Cadence: 89 avg
Decoupling: 2.45% (good)
EF: 1.51
HRRc: 32 bpm
Variability Index: 1.10
DFA a1: 0.78 avg, 18% Z2/35% transition/44% SS/3% above LT2 (drift +0.04, structural)
Calories: 825 kcal
Carbs used: 168 g
TSS: 88 (planned 85)
Feel: 2/5 (Good)
RPE: 6/10

Weekly totals (rolling 7d):
Phase: Build Wk2
Polarization: Z1+Z2 81%, Z3 6%, Z4+ 13%
Durability: 2.80% 7d mean(2) / 2.95% 28d mean(12) (stable)
EF: 1.48 7d mean(3) / 1.45 28d mean(14) (improving)
HRRc: 33 bpm 7d mean(2) / 32 bpm 28d mean(8) (stable)
TID 28d: Polarized (PI: 3.05) — drift: consistent
TSB: -6.50
CTL: 76.20
ATL: 82.70
Ramp rate: 0.65
ACWR: 1.08 (optimal)
Recovery Index: 0.93
Hours: 8h12m
TSS: 295

Interpretation:
Clean sweet spot session. Power on target across all four intervals, DFA a1 sat predominantly
in the 0.5–0.75 transition_lt2 band (44%) where sweet spot work should land per the protocol
threshold mapping — internal intensity matched prescription. Drift was slightly positive but
flagged structural (work above LT2 present), so no autonomic drift signal. Decoupling 2.45%
and stable HRRc round out a session that did exactly what it was meant to do.

Tomorrow: Endurance 2h, Z2 steady
```

---
