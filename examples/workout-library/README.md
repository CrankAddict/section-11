# Workout Reference Library

Companion document to **Section 11 B: AI Training Plan Protocol**.

## What This Is

A catalog of structured workout templates that AI coaching systems can select from when prescribing sessions. It provides the *how*; Section 11 provides the *when* and *why*.

## Relationship to Section 11

```
Section 11 A (Readiness) → determines go/modify/skip and adaptation target
Section 11 B (Plan Rules) → constrains session type, load, and distribution
Workout Reference Library → provides the actual session template
Section 11 C (Validation) → audits the result
```

Section 11 B §8 defines the formal interface between the plan protocol and this library.

## Not the Saved Workouts Mirror

Two different things are called a library. This folder is the **Workout Reference Library**: the normative catalogue of session templates that Section 11 designs plans from, shared by every athlete using the protocol.

`saved_workouts.json` is the **Saved Workouts Mirror**: a read-only snapshot of one athlete's own saved workouts in Intervals.icu. It is an inventory and retrieval source, not a design authority. A saved workout may be prescribed only after verifying that its structure implements an applicable template here or a permitted variant; a matching adaptation label alone is not enough. See [Saved Workouts Mirror](../json-examples/README.md#saved-workouts-mirror).

## Contents

**`WORKOUT_REFERENCE.md`**: The full library, containing:

1. **Workout Type Catalog**: 26 session templates across 6 adaptation categories (Endurance, Tempo/Sweet Spot/Threshold, VO₂max, Anaerobic, Race-Specific, Strength-Endurance)
2. **Warm-Up & Cool-Down Protocols**: Standard, progressive, abbreviated, and intensity-specific variants
3. **Session Sequencing Rules**: Spacing, ordering, and non-cycling integration
4. **Block Periodisation Sketches**: Build:deload ratios, volume trajectories, phase transitions
5. **Interval Format Selection Guide**: Decision matrix, progression logic, format change criteria
6. **Adaptation & Customisation Notes**: How to modify for your needs

## Customisation

This document is designed to be forked. You can:

- Add sport-specific sessions (running, swimming, SkiErg)
- Adjust durations for your available training time
- Replace templates with sessions that work for you
- Map to a different zone model if not using Intervals.icu

As long as your sessions follow the template format (name, zones, structure, duration, coaching notes, selection criteria), the AI coaching system can reference them.

## From Template to Intervals.icu Workout

The templates here describe sessions conceptually (zones, structure, duration), not in Intervals.icu syntax. When a template is written out as a raw Intervals.icu workout description, Section 11's house style is to put any optional workout step text, such as "Recovery", after the step's executable details, as in `- 5m 55% Recovery`. This is a style preference, not a required grammar: text before a step, after it, or in another placement that reads clearly remains valid. For the syntax itself, see [Intervals.icu Workout Syntax](../agentic/README.md#intervalsicu-workout-syntax).

## Version

Current: **0.5.0**
