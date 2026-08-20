# Section 11 — Workout Reference Library

**Version:** 0.7  
**Companion to:** Section 11 B — AI Training Plan Protocol  
**Last updated:** 2026-08-20

---

## Purpose & Scope

This document is a **library of session templates for inspiration**, not a rigid prescription list. It provides structured workout formats that an AI coaching system can reference when designing sessions under Section 11 B.

**Templates are starting points. The AI must adapt structure, duration, intensity, and recovery to the individual athlete's current fitness, goals, phase, and constraints.** Copy-pasting a template without customization is the wrong approach — a good coach never prescribes the same workout the same way to every athlete.

**Section 11 decides *when* and *what type*. This document provides *how* — as a starting point.**

### Design Principles

- **Section 11 A readiness logic always has final say.** No template in this document overrides go/modify/skip decisions.
- **Zone references use the athlete's Intervals.icu zone configuration.** Power targets are expressed as zone ranges, not hardcoded %FTP values, because athlete zones are individually calibrated and update with fitness changes.
- **This is a living catalog.** Athletes and coaches should adapt, extend, or replace templates to match individual needs, equipment, and sport demands.
- **Templates are inspiration, not prescription.** The AI should use these as structural references, then adjust interval count, duration, rest periods, and intensity to match the athlete's current state. A Sweet Spot 3x15 might become 3x12 for a fatigued athlete or 3x18 for a fresh one approaching peak.
- **Optional/advanced templates are clearly marked.** Templates flagged as *(Optional)* or *(Advanced)* are not necessary for every athlete and should not be prescribed by default. The AI should only select these when the athlete's goals, phase, and readiness specifically warrant them.

---

## 1. Workout Type Catalog

Each entry includes: session name, target adaptation, zone targets, interval structure, work:rest guidance, total session duration range (excluding WU/CD), coaching notes, and selection criteria.

**Duration note:** All durations listed are work time only, excluding warm-up and cool-down. For scheduling purposes, add 15–25 min for WU-STD or WU-PROG and 10–15 min for CD-STD. Total session time = listed duration + WU + CD.

**Template metadata:** Each template includes a machine-readable YAML block with the following fields:
- `id` — stable template code, used in the `session_template` audit field (Section 11 B §6/§8)
- `domain` — adaptation category: `endurance`, `tempo`, `sweet_spot`, `threshold`, `vo2max`, `anaerobic`, `race_specific`, `strength_endurance`
- `is_hard_session` — `true` if the session counts toward the 48h spacing rule (§3.1) and takes a structured session slot per Section 11 B §4
- `work_minutes` — approximate work duration (midpoint of range, excludes WU/CD for structured sessions; includes ramp-in/ramp-out for endurance sessions)
- `est_total_minutes` — estimated total session time. For structured sessions (§1B–1F): includes WU/CD. For endurance sessions (§1A): same as `work_minutes` because the ramp-in/ramp-out is built into the ride, not a separate WU/CD

---

### 1A. Aerobic / Endurance (Z1–Z2)

**Target adaptation:** Aerobic base, fat oxidation, mitochondrial density, durability.

**Pacing note:** Endurance rides benefit from a built-in ramp rather than starting at full Z2 power immediately. Allow 10–15 min easing into target power at the start (low Z1 → Z2), and 10–15 min stepping down at the end (Z2 → low Z1). This is not a warm-up for a hard effort — it's simply good practice for transitioning smoothly into and out of aerobic work, reducing unnecessary early-session cardiovascular stress and promoting a clean finish.

#### AE-1: Steady-State Endurance (Short)
```yaml
id: AE-1
domain: endurance
is_hard_session: false
work_minutes: 75
est_total_minutes: 75
```
- **Zones:** Z2 (upper Z1 acceptable for recovery weeks)
- **Structure:** Continuous riding
- **Duration:** 60–90 min
- **Coaching notes:** Maintain consistent effort. Cadence 85–95 rpm. Heart rate should remain stable or drift minimally (<5 % across the session).
- **Select when:** Midweek aerobic maintenance, moderate fatigue, or limited time.

#### AE-2: Steady-State Endurance (Medium)
```yaml
id: AE-2
domain: endurance
is_hard_session: false
work_minutes: 120
est_total_minutes: 120
```
- **Zones:** Z2
- **Structure:** Continuous riding
- **Duration:** 90–150 min
- **Coaching notes:** Key session for building aerobic volume. Monitor cardiac drift — if HR drifts >8 % with stable power, flag durability concern.
- **Select when:** Standard endurance day in Base or Build phase.

#### AE-3: Long Durability Ride
```yaml
id: AE-3
domain: endurance
is_hard_session: false
work_minutes: 180
est_total_minutes: 180
```
- **Zones:** Z1–Z2 (predominantly Z2, Z1 for first 15–20 min)
- **Structure:** Continuous riding with optional Z2-upper efforts in final 30 min
- **Duration:** 150–240+ min
- **Coaching notes:** This is the weekly long ride per Section 11 B §4. Late-ride Z2-upper efforts build durability under fatigue. Fueling strategy critical beyond 2 h.
- **Select when:** Weekly long ride slot. Requires adequate recovery status (RI ≥ 0.8).

#### AE-4: Active Recovery
```yaml
id: AE-4
domain: endurance
is_hard_session: false
work_minutes: 45
est_total_minutes: 45
```
- **Zones:** Z1 only
- **Structure:** Continuous, very easy spinning
- **Duration:** 30–60 min
- **Coaching notes:** Truly easy. If the athlete finds it hard to stay in Z1, suggest reducing duration rather than increasing intensity. Can substitute with complete rest if RI < 0.7.
- **Select when:** Day after hard session, elevated fatigue, or high cumulative load.

#### AE-5: Cadence / Technique Focus
```yaml
id: AE-5
domain: endurance
is_hard_session: false
work_minutes: 65
est_total_minutes: 65
```
- **Zones:** Z1–Z2
- **Structure:** 4–6 × 5 min single-leg drills or high-cadence (100–110 rpm) intervals within Z2 power, with 3 min easy spinning between
- **Duration:** 60–75 min total
- **Coaching notes:** Focus is neuromuscular efficiency, not power output. Keep effort conversational.
- **Select when:** Base phase variety, or when pedalling efficiency metrics indicate room for improvement.

#### AE-6: Fast-Finish Endurance
```yaml
id: AE-6
domain: endurance
is_hard_session: true
work_minutes: 140
est_total_minutes: 140
```
- **Zones:** Z1–Z2 for first 60–120 min, steady Z3 for final 30–45 min
- **Structure:** Long continuous ride with a deliberate intensity increase in the final block
- **Duration:** 120–165 min total
- **Coaching notes:** The Z3 finish deliberately targets durability under accumulated fatigue — the athlete must sustain tempo-range power when glycogen is depleted and cardiac drift is present. This is a harder session than AE-3 and counts toward weekly Z3+ time in TID calculations. Fueling critical.
- **Select when:** Late Base and Build phase, especially for athletes preparing for gran fondos, long climbing events, or any event where the decisive effort comes under fatigue. Requires RI ≥ 0.8. **This session takes a hard session slot** — it replaces (not supplements) one of the week's structured sessions from §1B or §1C in the weekly pattern, to preserve Section 11 B intensity distribution constraints.

#### AE-7: Progressive Endurance
```yaml
id: AE-7
domain: endurance
is_hard_session: false
work_minutes: 120
est_total_minutes: 120
```
- **Zones:** Start mid-Z2, finish upper Z2/low Z3, stepping up every 30–45 min
- **Structure:** Continuous ride with 2–3 planned step-ups in power (e.g., 3 × 40 min at progressively higher Z2 targets)
- **Duration:** 90–150 min total
- **Coaching notes:** A gentler durability stimulus than AE-6. The progression is subtle — each step-up is small enough that the session stays aerobic throughout. Monitor HR:power ratio across steps to assess durability.
- **Select when:** When you want durability stress without committing to a Z3 fast finish — moderate readiness days, or as a stepping stone before introducing AE-6.

---

### 1B. Tempo / Sweet Spot / Threshold (Z3–Z4)

This category covers three related but distinct intensity domains. The AI should distinguish between them when selecting sessions:

- **Tempo (Z3):** Sustainable, moderate intensity. Lower recovery cost. Use for volume accumulation and as a stepping stone toward sweet spot.
- **Sweet Spot (upper Z3–lower Z4):** High training stimulus at manageable recovery cost. The default "hard day" format for most build phases.
- **Threshold/MLSS (mid–high Z4):** Work at or near functional threshold power. Higher stimulus and higher recovery cost than sweet spot. Use when specifically targeting FTP/MLSS adaptation.

**Target adaptation:** Lactate threshold elevation, sustained power, muscular endurance.

#### SS-1: Sustained Sweet Spot Blocks
```yaml
id: SS-1
domain: sweet_spot
is_hard_session: true
work_minutes: 65
est_total_minutes: 95
```
- **Zones:** Z4 (Sweet Spot — upper Z3 to lower Z4 depending on zone model)
- **Structure:** 2–3 × 15–20 min, with 5 min Z1 recovery between blocks
- **Duration:** 55–80 min of work
- **Coaching notes:** Classic sweet spot session. Power should be steady within each block. RPE 7–8/10. If athlete cannot hold target for the full interval, reduce duration rather than adding blocks.
- **Position note:** Can be executed in aero/TT position for athletes preparing for time trials — accumulating time at sweet spot in race position builds both metabolic and positional tolerance.
- **Select when:** Build phase structured session slot. Default sweet spot format.

#### SS-2: Progressive Sweet Spot
```yaml
id: SS-2
domain: sweet_spot
is_hard_session: true
work_minutes: 62
est_total_minutes: 92
```
- **Zones:** Z4
- **Structure:** 3 blocks with ascending duration: 12 min → 15 min → 20 min, with 5 min Z1 recovery between blocks
- **Duration:** 60–65 min of work
- **Coaching notes:** Ascending duration provides psychological pacing advantage. If the athlete fails the final block, session still has training value from first two. Useful for building confidence.
- **Select when:** Early Build phase, or when athlete is returning from a deload and rebuilding threshold tolerance.

#### SS-3: Over-Unders
```yaml
id: SS-3
domain: sweet_spot
is_hard_session: true
work_minutes: 52
est_total_minutes: 82
```
- **Zones:** Alternating Z4 (under) and low Z5 (over)
- **Structure:** 3–4 × 8–10 min blocks. Within each block: 2 min Z4 / 1 min low Z5, repeating. 5 min Z1 recovery between blocks.
- **Duration:** 45–60 min of work
- **Coaching notes:** Develops lactate clearance at threshold. The "over" segments should be uncomfortable but sustainable — if the athlete blows up, the overs are too high. Reduce over-segment intensity before reducing block count.
- **Select when:** Mid-to-late Build phase. Requires good threshold tolerance (athlete should be comfortable with SS-1 first).

#### SS-4: Tempo Intervals (Lower Intensity Variant)
```yaml
id: SS-4
domain: tempo
is_hard_session: true
work_minutes: 80
est_total_minutes: 110
```
- **Zones:** Z3
- **Structure:** 2–3 × 20–30 min, with 5 min Z1 recovery between blocks
- **Duration:** 60–100 min of work
- **Coaching notes:** For athletes building toward sweet spot who aren't ready for sustained Z4. Also suitable when readiness metrics suggest a moderate rather than hard day.
- **Select when:** Early Base/Build transition, or when Section 11 A readiness indicates "modify" rather than "go" for a structured day.

#### SS-5: Repeated Sweet Spot Intervals
```yaml
id: SS-5
domain: sweet_spot
is_hard_session: true
work_minutes: 55
est_total_minutes: 85
```
- **Zones:** Z4 (Sweet Spot)
- **Structure:** 4 × 10 min, with 5 min Z1 recovery between intervals
- **Duration:** ~55 min of work
- **Coaching notes:** More intervals at shorter duration than SS-1. The 10-minute blocks are long enough for sustained metabolic stimulus but short enough to maintain high power quality across all four efforts. This format accumulates comparable total time-in-zone to SS-1 while allowing better execution consistency — power variance between first and last interval should be minimal. If the athlete completes all 4 intervals with stable power and RPE, progress by extending interval duration (4×11, 4×12) before adding a 5th interval.
- **Select when:** Athletes who respond better to more frequent efforts with full recovery, or as an alternative to SS-1 when sustained 15–20 min blocks see power fade in later intervals. Also effective for indoor trainer sessions where psychological monotony of long blocks is a factor.

#### TH-1: Classic Threshold Blocks
```yaml
id: TH-1
domain: threshold
is_hard_session: true
work_minutes: 38
est_total_minutes: 70
```
- **Zones:** Mid–high Z4 (at or near MLSS/FTP)
- **Structure:** 2 × 20 min or 3 × 12 min, with 5–8 min Z1 recovery between blocks
- **Duration:** 36–40 min of work
- **Coaching notes:** True threshold work — harder than sweet spot, targeting the upper boundary of Z4. Power should be at the level the athlete can sustain for ~40–60 min in a time trial. RPE 8–9/10. If the athlete cannot complete the second block within 3 % of the first block's power, the target is too high. These sessions carry higher recovery cost than sweet spot — account for this in weekly load planning.
- **Position note:** For TT-focused athletes, executing in aero position at threshold is the gold-standard race-specificity session. Build to this gradually — start with SS-1 in aero before progressing to TH-1 in position.
- **Select when:** Mid-Build onward, once the athlete consistently completes SS-1 or SS-5. Use when the specific goal is FTP/MLSS elevation rather than general muscular endurance.

#### TH-2: Seiler-Style Long Intervals (4×8)
```yaml
id: TH-2
domain: threshold
is_hard_session: true
work_minutes: 36
est_total_minutes: 68
```
- **Zones:** High Z4 / low Z5 by power, targeting ~90–92 % HRmax by the final intervals
- **Structure:** 4–5 × 8 min, with 2 min Z1 recovery between intervals
- **Duration:** 32–40 min of work
- **Coaching notes:** Sits at the threshold/VO₂max border — these intervals are long enough and hard enough to drive significant cardiac output, while the power target is closer to threshold than classic VO₂max intervals. The short 2-minute recoveries are deliberate — the athlete should not be fully recovered before the next effort. HR will progressively climb across intervals; reaching 90–92 % HRmax in the final 1–2 intervals indicates correct intensity. This format provides combined VO₂ and threshold gains, making it extremely time-efficient.
- **Select when:** Mid-to-late Build phase when you want combined threshold and VO₂ adaptation without committing to full Z5 intervals. High value for athletes with limited weekly training time who need maximum stimulus from 2 hard sessions. Requires established threshold fitness (SS-1/SS-5 completed consistently).

---

### 1C. VO₂max (Z5)

**Target adaptation:** Maximal aerobic power, cardiac output, oxygen utilization.

#### VO2-1: Classic Long Intervals
```yaml
id: VO2-1
domain: vo2max
is_hard_session: true
work_minutes: 35
est_total_minutes: 70
```
- **Zones:** Z5
- **Structure:** 4–5 × 4 min, with 3–4 min Z1 recovery between intervals
- **Work:rest ratio:** ~1:1
- **Duration:** 30–40 min of work
- **Coaching notes:** The gold standard VO₂max format. Target is accumulating time at >90 % VO₂max — the recovery must be easy enough to allow full engagement on the next interval. If power drops >5 % across intervals, stop the session.
- **Select when:** Default VO₂max format for Build phase. Athlete should have ≥4 weeks of threshold work (SS-1/SS-2) before progressing here.

#### VO2-2: Short-Short Intervals (30/15 or 40/20)
```yaml
id: VO2-2
domain: vo2max
is_hard_session: true
work_minutes: 25
est_total_minutes: 60
```
- **Zones:** Z5–Z6 during work, Z1 during recovery
- **Structure:** 2–3 sets of 8–10 repetitions of 30 s on / 15 s off (or 40 s on / 20 s off). 5 min Z1 between sets.
- **Work:rest ratio:** 2:1
- **Duration:** 20–30 min of accumulated work
- **Coaching notes:** Leverages the VO₂max slow-component — oxygen uptake stays elevated during the brief recoveries, accumulating significant time at high VO₂. Perceptually more tolerable than long intervals for many athletes despite similar physiological stimulus. Power during "on" segments will be higher than VO2-1 targets.
- **Select when:** Alternative to VO2-1 when athlete reports difficulty sustaining long intervals, or for variety mid-block. Also effective for athletes with limited time.

#### VO2-3: Descending Rest Intervals
```yaml
id: VO2-3
domain: vo2max
is_hard_session: true
work_minutes: 25
est_total_minutes: 60
```
- **Zones:** Z5
- **Structure:** 5 × 3 min, with recovery durations: 3 min → 2.5 min → 2 min → 1.5 min between intervals
- **Duration:** ~25 min of work
- **Coaching notes:** Progressive fatigue accumulation targets the final intervals at genuine VO₂max. First 2–3 intervals may feel moderate — that's by design. If the athlete cannot complete the final interval within 5 % of target power, the session has still succeeded if they completed 4 of 5.
- **Select when:** Late Build or early Peak phase. Requires established VO₂max tolerance (athlete should have completed ≥3 sessions of VO2-1 or VO2-2).

#### VO2-4: Ascending Duration Intervals
```yaml
id: VO2-4
domain: vo2max
is_hard_session: true
work_minutes: 25
est_total_minutes: 60
```
- **Zones:** Z5
- **Structure:** 5 intervals with ascending duration: 2 min → 3 min → 4 min → 3 min → 2 min, with 3 min Z1 recovery between all
- **Duration:** ~25 min of work
- **Coaching notes:** The pyramid structure makes the session psychologically manageable — the longest effort is in the middle when the athlete is warmed into the session but not yet deeply fatigued. Good introductory format.
- **Select when:** Transitioning into VO₂max work from a threshold block, or for athletes new to Z5 intervals.

#### VO2-5: High-Volume Short-Short (30/15)
```yaml
id: VO2-5
domain: vo2max
is_hard_session: true
work_minutes: 20
est_total_minutes: 90
```
- **Zones:** Z5–Z6 during work, Z1 during recovery
- **Structure:** 3 sets × 13 repetitions of 30 s on / 15 s off. 5 min Z1 between sets.
- **Work:rest ratio:** 2:1
- **Duration:** ~19.5 min of accumulated work (29.25 min total set time)
- **Coaching notes:** A high-volume variant of VO2-2. The 13-rep sets are substantially more demanding than the 8–10 rep sets in VO2-2 — each set accumulates 6.5 min of Z5–Z6 work with only brief micro-recoveries. By the final reps of each set, the athlete should be operating at genuine VO₂max. The extended set duration also develops mental tolerance for sustained high-intensity discomfort. Power quality in the final set is the key indicator — if the athlete cannot maintain target power in set 3, reduce to 10–11 reps per set before reverting to VO2-2. Include an extended cool-down (~30 min Z1) to facilitate recovery.
- **Select when:** Progression from VO2-2 once the athlete consistently completes 3 × 10 at target power. Also suitable for athletes who have adapted to the short-short format and need increased stimulus without changing interval structure. Not for athletes new to VO₂max work — establish the format with VO2-2 first.

---

### 1D. Anaerobic / Neuromuscular (Z6–Z7)

**Target adaptation:** Anaerobic capacity, peak power, neuromuscular recruitment.

> **Note:** Most endurance athletes do not need dedicated anaerobic or neuromuscular sessions. These templates exist for athletes in Peak phase preparing for events with surging/attacking demands, or for athletes with identified weaknesses in short-duration power. When in doubt, prioritise VO₂max and threshold work.

#### AN-1: Short Power Repeats
```yaml
id: AN-1
domain: anaerobic
is_hard_session: true
work_minutes: 12
est_total_minutes: 50
```
- **Zones:** Z6
- **Structure:** 8–12 × 30 s, with 2.5–3 min Z1 recovery between efforts
- **Duration:** ~10–15 min of work
- **Coaching notes:** Full recovery between efforts is critical — these are about power quality, not accumulated fatigue. If power drops >10 % from first to last interval, reduce the number of repeats.
- **Select when:** Peak phase only. Event demands require repeated high-power surges (criterium, mountain stages with attacks).

#### AN-2: Sprint Intervals
```yaml
id: AN-2
domain: anaerobic
is_hard_session: true
work_minutes: 8
est_total_minutes: 70
```
- **Zones:** Z7 (maximal)
- **Structure:** 4–6 × 10–15 s all-out sprints, with 5 min Z1 recovery between efforts
- **Duration:** ~5–8 min of work (embedded in a longer Z1–Z2 ride)
- **Coaching notes:** True neuromuscular work — full rest, maximal recruitment. These should be done fresh, typically early in a session after warm-up. Total session including Z2 riding: 60–75 min.
- **Select when:** Rarely. Sprint-finish events, or to maintain neuromuscular recruitment during a Base phase. Maximum once per week.

#### AN-3: Progressive Sprint Sets
```yaml
id: AN-3
domain: anaerobic
is_hard_session: true
work_minutes: 3
est_total_minutes: 60
```
- **Zones:** Z7 (maximal)
- **Structure:** 3 sets × 5 × 10 s maximal sprints. 3 min Z1 recovery between reps, 5 min Z1 between sets. Power target ascends between sets (e.g., Set 1 at reference power, Sets 2–3 at reference +3–5 %).
- **Duration:** ~2.5 min of work, ~60 min total session with warm-up and Z1 riding
- **Coaching notes:** The set structure with ascending power is a deliberate progression — the athlete must produce their highest power when fatigued from the previous sets. This develops both neuromuscular capacity and the ability to sprint under cumulative fatigue, which is race-specific for attacking scenarios. The 3-minute between-rep recovery is enough for partial ATP-CP restoration but not full recovery, so power quality within each set reveals true repeatability. If power in Set 3 drops >10 % below Set 1 despite ascending targets, the athlete is over-reaching on the target — maintain Set 1 power across all sets before progressing. Include extended cool-down (~15–20 min Z1).
- **Select when:** Peak phase for athletes preparing for events requiring repeated accelerations (criteriums, road races with attacks). Progression from AN-2 once the athlete demonstrates consistent sprint quality across 6 single efforts. Maximum once per week.

---

### 1E. Mixed / Race-Specific

**Target adaptation:** Event-specific fitness, pacing, multi-system stress.

#### MIX-1: Variable Intensity Simulation
```yaml
id: MIX-1
domain: race_specific
is_hard_session: true
work_minutes: 105
est_total_minutes: 105
```
- **Zones:** Z2 base with programmed surges to Z4–Z5
- **Structure:** 90–120 min Z2 ride with 6–8 × 2–3 min surges to Z4–Z5 at irregular intervals (every 10–20 min). Recovery back to Z2 between surges (no Z1).
- **Coaching notes:** Simulates the variable demands of road racing or group rides. The key stimulus is repeated transitions from steady to hard and back. Z2 segments should feel genuinely comfortable — if they don't, reduce surge frequency.
- **Select when:** Mid-to-late Build or Peak phase. Athlete has established threshold and VO₂max fitness. Not for Base phase.

#### MIX-2: Race-Week Opener
```yaml
id: MIX-2
domain: race_specific
is_hard_session: false
work_minutes: 52
est_total_minutes: 52
```
- **Zones:** Z2 base with short Z5–Z6 openers
- **Structure:** 45–60 min easy Z2 ride with 3 × 1 min at Z5, 2 × 30 s at Z6. Full recovery (3–5 min Z2) between efforts.
- **Duration:** 45–60 min total
- **Coaching notes:** Activation session, not a training session. Primes neuromuscular and cardiovascular systems without generating meaningful fatigue. Should feel sharp and easy. Reference Section 11 A race-week protocol.
- **Select when:** 1–2 days before target event, per race-week protocol.

---

### 1F. Strength-Endurance — Low Cadence *(Optional)*

**Target adaptation:** Neuromuscular efficiency, torque production, type II fibre recruitment under sustained load.

> **Note:** These templates are optional. The evidence for low-cadence work improving endurance performance is mixed — some studies show neuromuscular efficiency gains, others show no advantage over normal-cadence work at the same power. These sessions trade some metabolic specificity for strength/torque development and should not crowd out normal-cadence structured work. Most useful for athletes targeting hilly courses or who identify muscular endurance on climbs as a limiter.

#### SE-1: Low-Cadence Tempo *(Optional)*
```yaml
id: SE-1
domain: strength_endurance
is_hard_session: true
work_minutes: 55
est_total_minutes: 85
```
- **Zones:** Z3
- **Structure:** 4–6 × 8 min at Z3, 50–60 rpm, with 4 min Z1 (normal cadence) between intervals
- **Duration:** 45–65 min of work
- **Coaching notes:** The low cadence forces higher torque per pedal stroke at the same power output, recruiting more type II muscle fibres. Knee stress is higher than normal-cadence work — any knee discomfort is an immediate stop signal. Keep upper body relaxed; the effort should feel muscular rather than cardiovascular.
- **Position note:** Particularly effective executed in seated climbing position (70–80 rpm range acceptable for climbing simulation). Useful for athletes preparing for long alpine-style climbs.
- **Select when:** Early-to-mid Base or Build phase for athletes targeting hilly events. Maximum once per week. Not a substitute for SS-1/SS-4 — use alongside, not instead of, normal-cadence threshold development.

#### SE-2: Low-Cadence Sweet Spot *(Optional/Advanced)*
```yaml
id: SE-2
domain: strength_endurance
is_hard_session: true
work_minutes: 45
est_total_minutes: 75
```
- **Zones:** Low Z4 (Sweet Spot)
- **Structure:** 3 × 10–12 min at low Z4, 55–65 rpm, with 5–6 min Z1 (normal cadence) between intervals
- **Duration:** 40–50 min of work
- **Coaching notes:** Combines the muscular demands of low-cadence work with sweet spot metabolic stress. More demanding than SE-1 on both muscular and cardiovascular systems. Only appropriate when the athlete has experience with both low-cadence work (SE-1) and sweet spot efforts (SS-1/SS-5) separately.
- **Select when:** Mid-Build phase for athletes with established base in both SE-1 and SS-1. Readiness must be full "go" — do not prescribe on "modify" days. Maximum once per week, and this replaces (not supplements) one of the week's structured sessions.

---

## 2. Warm-Up & Cool-Down Protocols

All structured sessions (§1B, 1C, 1D, 1E, 1F) require warm-up and cool-down. Endurance sessions (§1A) should use the ramp-in/ramp-out pattern described in the §1A pacing note — 10–15 min easing into target power at the start and stepping down at the end. This replaces a formal WU/CD and is recommended for all endurance rides regardless of duration.

### Standard Warm-Up (WU-STD)
**Duration:** 15–20 min  
**Structure:**
1. 5 min Z1 — easy spinning, gradually increase cadence
2. 5 min progressive Z1→Z2 — smooth power build
3. 2 × 1 min at Z3 with 1 min Z1 between — systems activation
4. 1 × 30 s at target session intensity — prime the effort
5. 2–3 min Z1 — settle before main set

### Progressive Step Warm-Up (WU-PROG)
**Duration:** 15–20 min  
**Structure:**
1. 5 min low Z1–Z2 — easy spinning
2. 5 min Z2 — steady aerobic effort
3. 5 min upper Z2/low Z3 — systems activation
4. 5 min Z1 — settle before main set (omit for VO₂max sessions to maintain activation)

**Coaching notes:** A structured 3-step power progression that smoothly ramps the cardiovascular and muscular systems. Each step is long enough to stabilise at the target intensity before moving up. The settling period at the end allows HR to drop before the main set begins. This format is particularly effective before sweet spot and threshold sessions where the athlete benefits from a gradual approach to working intensity.

### Abbreviated Warm-Up (WU-SHORT)
**Duration:** 10 min  
**Structure:**
1. 4 min Z1 — easy spinning
2. 3 min progressive Z1→Z2
3. 1 × 1 min at Z3
4. 1 × 30 s at target intensity
5. 1.5 min Z1

**Use when:** Time-constrained sessions. Not recommended before VO₂max or anaerobic work.

### Intensity-Specific Warm-Up Modifications
- **Before VO₂max sessions (VO2-1 through VO2-5):** Use WU-STD or WU-PROG (omitting the settling period) and extend to include 1 × 1 min at Z4 (threshold primer). Total WU: ~20–22 min.
- **Before anaerobic/sprint sessions (AN-1 through AN-3):** Use WU-STD or WU-PROG and add 2 × 10 s Z6 sprints with full recovery after activation. Total WU: ~22–25 min.

### Standard Cool-Down (CD-STD)
**Duration:** 10–15 min  
**Structure:**
1. 5 min progressive reduction from session intensity → Z2
2. 5–10 min Z1 easy spinning
3. Cadence: comfortable, no pressure

**Minimum cool-down:** 5 min Z1 spinning. Sessions should never end at high intensity with an abrupt stop.

**Extended cool-down note:** High-volume VO₂max sessions (VO2-5) and anaerobic sessions (AN-3) benefit from extended cool-downs of 20–30 min Z1 to facilitate recovery and parasympathetic reactivation.

---

## 3. Session Sequencing Rules

These rules govern the placement of sessions within a microcycle (training week). They supplement Section 11 B §4 (Session Composition Rules).

### 3.1 Minimum Spacing Between Hard Sessions
- **Hard session definition (zone ladder):** A day qualifies as hard if ANY of the following cumulative thresholds are met (per Seiler/Foster, matching sync.py's `is_hard_day` logic):
  - **Power ladder** (preferred, 5 rungs):
    - Z3+ ≥ 30 min (tempo and above, cumulative)
    - Z4+ ≥ 10 min (threshold and above)
    - Z5+ ≥ 5 min (VO₂max and above)
    - Z6+ ≥ 2 min (anaerobic and above)
    - Z7 ≥ 1 min (neuromuscular)
  - **HR fallback** (when no power zones available, 2 rungs — per Seiler 3-zone model):
    - Z4+ ≥ 10 min (sustained above LT2)
    - Z5+ ≥ 5 min (VO₂max)
  - HR zones are too wide and lagged for fine-grained classification. Short-duration rungs (Z6+/Z7) and the Z3 tempo trigger are invalid for HR due to cardiac lag and false-positive risk on steady-state runs. HR-classified hard days are flagged with `intensity_basis: "hr"` in daily tier output.
  - Higher zones need less time to qualify — 1 min of Z7 sprints is as "hard" as 30 min of Z3 tempo. Each template's YAML metadata (`is_hard_session: true/false`) reflects the power ladder.
- **Minimum gap:** 48 hours between hard sessions (i.e., at least one easy/rest day between).
- **Exception:** Back-to-back hard days permitted only when **TSB > 0 and RI ≥ 0.85** (per Section 11 B §4).

### 3.2 Ordering Logic
- **VO₂max before Sweet Spot/Threshold** when both occur in the same week and are closely spaced (e.g., consecutive days or with only one rest day between). When sessions are separated by 2+ recovery days (e.g., Tuesday VO₂max / Thursday SS, or the reverse), order matters less — adequate recovery between sessions neutralises the freshness advantage.
- **Long ride should not follow a VO₂max session** without at least one recovery day between. Sequencing: VO₂max → rest/easy → long ride, or long ride → rest/easy → VO₂max.
- **Sprint/anaerobic work (AN-1 through AN-3)** should be placed early in the week when freshness is highest, or at least 48 h before any other hard session.
- **Threshold sessions (TH-1, TH-2)** carry higher recovery cost than sweet spot — treat like VO₂max for sequencing purposes when placing alongside other hard sessions.
- **Strength-endurance sessions (SE-1, SE-2)** generate significant muscular fatigue. Do not place before VO₂max work or long rides.

### 3.3 Long Ride Placement
- Typically weekend (when training time is available).
- Should not be preceded by a hard session the day before unless the long ride is Z1-Z2 only with no late-ride efforts.
- If the athlete trains on a Tuesday/Thursday hard day pattern, the long ride fits naturally on Saturday or Sunday.
- **AE-6 (fast-finish)** counts as a hard session for spacing purposes due to the Z3 final block.

### 3.4 Non-Cycling Load Integration
- **Strength sessions:** Place on the same day as a hard cycling session (after cycling) or on an easy/rest day. Do not place strength the day before a VO₂max session.
- **Alternative cardio (SkiErg, running, etc.):** Treat as equivalent zone stress — a Z2 SkiErg session counts toward weekly Z2 volume. A high-intensity alternative session counts as a hard day for sequencing purposes.
- **Load accounting:** Non-cycling sessions should be reflected in weekly TSS totals (use Intervals.icu's cross-sport load tracking). Section 11 A's ACWR and load management rules apply to total load, not cycling-only load.

### 3.5 Example Weekly Patterns

> These are illustrations, not prescriptions. Section 11 readiness logic always has final say.

**Build Phase — Standard Pattern:**

| Day | Session | Notes |
|-----|---------|-------|
| Mon | Rest or AE-4 | Recovery from weekend long ride |
| Tue | VO2-1 or VO2-5 | Primary hard session — freshest weekday |
| Wed | AE-1 or AE-4 | Easy recovery |
| Thu | SS-5 or TH-1 | Secondary hard session |
| Fri | Rest or AE-4 | Pre-long-ride recovery |
| Sat | AE-3 or AE-6 | Long durability ride (AE-6 if fast-finish week) |
| Sun | AE-1 or Rest | Easy spin or full rest |

**Base Phase — Standard Pattern:**

| Day | Session | Notes |
|-----|---------|-------|
| Mon | Rest | Full rest |
| Tue | SS-4 or AE-5 | Moderate structured work or technique |
| Wed | AE-1 | Steady endurance |
| Thu | SS-1 or SS-5 | Primary sweet spot session |
| Fri | AE-4 or Rest | Recovery |
| Sat | AE-3 | Long ride |
| Sun | AE-1 | Easy endurance |

---

## 4. Block Periodisation Sketches

These are guideline patterns for mesocycle (block) structure. Section 11 A's phase detection is reactive by design — these sketches inform planning but do not override detected phase state.

### 4.1 Build:Deload Ratios

- **Standard:** 3:1 (three progressive weeks, one deload week)
- **High-responder / younger athlete:** 4:1 may be tolerated if RI remains ≥ 0.8 throughout
- **Master athlete / high-stress periods:** 2:1 is appropriate
- **Selection guidance:** Default to 3:1. Move to 2:1 if Section 11 A triggers regression/deload criteria before week 3. Move to 4:1 only if the athlete consistently shows RI ≥ 0.85 and positive HRV trend at week 3.

### 4.2 Volume Trajectory Across a Block

- **Week 1:** Baseline volume (~95–100 % of target)
- **Week 2:** Moderate increase (~100–105 %)
- **Week 3:** Peak load (~105–110 %)
- **Deload week:** Reduce to ~60–70 % of peak week volume. Maintain 1 short structured session at reduced duration but similar intensity (keeps top-end fitness without load).

**Deload session modifications:** When prescribing the deload-week structured session, reduce interval count or duration while maintaining target zone:
- Sweet Spot: SS-5 at 2×10 min (instead of 4×10), or SS-1 at 1×15 min
- VO₂max: VO2-2 at 2×6 reps (instead of 3×10), or VO2-1 at 3×3 min
- Threshold: TH-1 at 1×15 min (instead of 2×20)
- Long ride: Replace AE-3 with AE-2 (cap at 90–120 min)
- All other sessions: AE-1 or AE-4 only

Volume changes must remain within Section 11 B §2 tolerance (±10 % of validated baseline). If baseline is 15 h, peak week should not exceed ~16.5 h without meeting expansion criteria.

### 4.3 Phase-to-Phase Transitions

- **Base → Build:** Introduce first VO₂max session (VO2-4 or VO2-1 at reduced volume). Replace one tempo session (SS-4) with sweet spot (SS-1/SS-5). Optionally introduce TH-2 as a combined stimulus.
- **Build → Peak:** Reduce total volume by ~10–15 %. Increase proportion of race-specific work (MIX-1). Maintain intensity but reduce session count. Introduce AN-3 if event demands sprint repeatability.
- **Peak → Taper:** Follow Section 11 A race-week protocol. Reference MIX-2 for openers. Note: race-week taper has its own day-by-day decision tree (D-7 through D-0) with event-type-specific TSB targets and opener timing that override the standard deload patterns in §4.2. Always defer to the race-week protocol when it is active.
- **Any phase → Recovery:** Triggered by Section 11 A regression rules. All sessions drop to Z1–Z2 only (AE-1, AE-4). Duration reduced to 50–60 % of baseline. Minimum 5 days before reassessing.

### 4.4 Adaptation Timelines
- **Aerobic base adaptations:** 4–8 weeks of consistent Z2 volume before measurable changes in efficiency/durability.
- **Threshold/sweet spot gains:** 3–6 weeks of structured threshold work to see FTP movement.
- **VO₂max response:** 2–4 weeks of dedicated VO₂max intervals for measurable improvement, but only if aerobic base is established.
- **Implication:** Don't abandon a stimulus too early. If the athlete is responding (power stable, RPE decreasing, or power increasing at same RPE), continue the current block structure.

---

## 5. Interval Format Selection Guide

When Section 11 determines a structured session is needed, use this guide to select the specific format.

### 5.1 Decision Matrix

| Situation | Recommended Format | Rationale |
|-----------|-------------------|-----------|
| First VO₂max session of a block | VO2-4 (pyramid) | Psychologically manageable introduction |
| Established VO₂max fitness | VO2-1 (classic 4×4) | Maximum time at VO₂max |
| Athlete struggles with long intervals | VO2-2 (short-short) | Equivalent stimulus, better tolerance |
| Progressed beyond VO2-2 | VO2-5 (high-volume 30/15) | Increased stimulus, same format |
| Late Build / early Peak | VO2-3 (descending rest) | Progressive overload on recovery capacity |
| First sweet spot work of season | SS-4 (tempo) or SS-2 (progressive) | Build tolerance before sustained blocks |
| Established sweet spot fitness | SS-1 or SS-5 (sustained blocks) | Standard stimulus, choose based on athlete preference |
| Targeting FTP/MLSS specifically | TH-1 (threshold blocks) | Direct threshold stimulus |
| Combined threshold + VO₂ gains | TH-2 (Seiler 4×8) | Dual adaptation, time-efficient |
| Preparing for variable-pace events | SS-3 (over-unders) → MIX-1 | Clearance capacity, then race simulation |
| Time-constrained (<75 min total) | VO2-2, VO2-5, or SS-5 | High stimulus density |
| "Modify" readiness (not full "go") | SS-4 (tempo) or AE-7 (progressive) | Reduce intensity, maintain structure |
| Durability focus under fatigue | AE-6 (fast-finish) | Z3 work when fatigued |
| Hilly event preparation | SE-1 (low-cadence tempo) | Torque development *(optional)* |
| Race-week activation | MIX-2 (opener) | Prime without fatigue |
| Peak phase sprint demands | AN-3 (progressive sprint sets) | Repeated sprint under fatigue |

### 5.2 Progression Within a Format

Before changing to a new format, progress within the current one.

**Precedence:** The ordering below is the last resort. A template's own progression note governs which progression variable changes and in what order where one exists; failing that, the applicable Section 11 A progression pathway governs — §*1 for endurance, or the VO₂max or Sweet Spot rules in §*2. Use the generic ordering below only when neither defines an order. Section 11 A's readiness, safety, response, one-variable and regression gates always apply regardless.

At every tier, the selected progression variable must remain compatible with the template's target adaptation and non-negotiable execution constraints. Do not apply a generic vector that changes the nature of the session — for example, shortening recovery where full recovery is required, increasing intensity in an already-maximal effort, or converting technique/specificity work into generic load progression. If no compatible progression vector is defined, repeat or hold; do not invent one. Format changes remain governed by §5.3.

- **Duration first:** Add 1 interval or extend intervals by 1 min (e.g., 4×4 → 5×4, or 3×15 → 3×18)
- **Recovery second:** Reduce rest by 15–30 s (e.g., 4×4 with 4 min rest → 4×4 with 3.5 min rest)
- **Intensity last:** Only increase target zone if the athlete consistently completes sessions with power above the lower bound of the target zone

**Progression gates:** Apply Section 11 A's progression pathway rules. Only one vector changes per week unless dual-pathway criteria are met.

**Format-specific progression examples:**
- VO2-2 (3×10) → VO2-5 (3×13): rep count progression within the short-short format
- SS-5 (4×10) → SS-5 (4×12) → SS-1 (3×15) → SS-1 (2×20): duration progression across sweet spot formats
- AN-2 (6 singles) → AN-3 (3×5 sets): volume and structure progression within anaerobic work
- SS-1 → TH-1: intensity progression from sweet spot to threshold (only when FTP elevation is the specific target)

### 5.3 When to Change Formats

- Athlete completes the top-end variant of current format consistently (e.g., 6×4 min at Z5 with 3 min rest) → move to a new format or shift training focus.
- Athlete shows plateau in RPE and power response across ≥2 weeks at the same format → introduce variation.
- Phase transition → new phase may call for different adaptation targets (see §4.3).

### 5.4 Time-Crunch Truncation Rules

When the athlete has less time than the prescribed session requires, apply these rules in order. **Never increase intensity to compensate for lost time.**

1. **Cut cool-down first.** Reduce CD-STD to the 5 min minimum (Z1 spinning). Do not skip entirely.
2. **Shorten warm-up second.** Switch from WU-STD/WU-PROG to WU-SHORT. Do not skip warm-up before Z4+ work.
3. **Reduce interval count third.** Remove the last interval or set (e.g., 4×10 → 3×10, 3 sets → 2 sets). Maintain full interval duration and recovery for remaining efforts.
4. **Shorten endurance portions last.** For sessions with Z1–Z2 base riding (MIX-1, AE-3, AN-2 embedded rides), reduce the Z1–Z2 time. Keep the structured work intact.
5. **If total available time < 45 min:** Substitute with a time-efficient template (VO2-2, SS-5) or convert to AE-1 (short endurance). Do not attempt to compress a 90-min session into 40 min.
6. **If total available time < 30 min:** AE-4 (active recovery) or rest. A 25-min rushed structured session has negligible training value and elevated injury risk.

---

## 6. Adaptation & Customisation Notes

### 6.1 How to Modify This Document

This document is designed to be forked and edited. Athletes and coaches should:

- **Add sport-specific sessions:** Running intervals, swimming sets, SkiErg formats, etc. Use the same template structure (name, zones, structure, duration, coaching notes, selection criteria).
- **Adjust durations and volumes:** The templates assume a trained endurance athlete with ~12–16 h/week available. Scale durations proportionally for lower-volume athletes.
- **Replace zone references:** If not using Intervals.icu zones, map to your preferred zone model. The key is consistency — all templates should reference the same zone system.
- **Add personal favourites:** If an athlete has sessions that work well for them, document them here using the template format for AI reference.

### 6.2 Sport-Specific Considerations

The catalog above is cycling-focused. For multi-sport or alternative-sport athletes:

- **Running:** Impact stress means recovery demands differ. Hard running sessions need more spacing than hard cycling sessions. Long runs generate more muscular fatigue per hour than long rides.
- **Multi-sport:** Brick sessions (e.g., bike → run) count as a single hard session for sequencing purposes. Total weekly hard session count should not increase just because multiple sports are involved.
- **Indoor training (smart trainer, SkiErg, etc.):** Sessions may require duration reduction (~80–90 % of outdoor equivalent) due to higher sustained effort and thermal stress.

### 6.3 Limitations

- This document does not replace a qualified human coach for complex situations (return from injury, chronic illness, multi-peak season planning).
- Templates assume a healthy, injury-free athlete. Medical clearance and individual contraindications are outside the scope of this document.
- Nutritional, sleep, and lifestyle factors significantly affect training response but are not prescribed here.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-02-24 | Initial draft — workout catalog, WU/CD, sequencing, block sketches, selection guide |
| 0.2.0 | 2026-02-24 | Added: TH-1/TH-2 (threshold), AE-6/AE-7 (durability), SE-1/SE-2 (strength-endurance), SS-5 (repeated intervals), VO2-5 (high-volume 30/15), AN-3 (progressive sprints), WU-PROG (progressive warm-up). Restructured 1B header to distinguish tempo/sweet spot/threshold. Added position notes. Updated decision matrix and sequencing rules. |
| 0.3.0 | 2026-02-24 | Fixed dates (2025→2026). Added deload session modification rules (§4.2). Added total session duration note to catalog header. Clarified §3.2 VO₂max/SS ordering applies to close spacing, not across full week. Added race-week protocol cross-reference in §4.3. |
| 0.4.0 | 2026-02-25 | Added time-crunch truncation rules (§5.4). Clarified AE-6 takes a hard session slot. |
| 0.5.0 | 2026-02-25 | Added machine-readable YAML metadata to all 26 templates (id, domain, is_hard_session, work_minutes, est_total_minutes). Updated catalog header with metadata schema description. |
| 0.6.0 | 2026-02-28 | Hard-session classification split into the five-rung power ladder and two-rung HR fallback, with HR-classified hard days identified by `intensity_basis: "hr"`. (History row backfilled 2026-08-20; header had already read 0.6.) |
| 0.7.0 | 2026-08-20 | §5.2 precedence clarified: a template's own progression note governs which progression variable changes and in what order; failing that the applicable Section 11 A progression pathway (§*1 for endurance, or the VO₂max or Sweet Spot rules in §*2); the generic duration/recovery/intensity ordering applies only when neither defines an order. Section 11 A gates unaffected. |

---

*End of Workout Reference Library*
