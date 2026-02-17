# Athlete Training Dossier & Performance Roadmap

**Dossier Version:** v1.1  
**Protocol Compatibility:** Section 11 v11.5+  
**Date:** [YYYY-MM-DD]  
**Primary Source Systems:** Intervals.icu | [Other platforms]

This document serves as a reference template for endurance athletes using the deterministic AI-coaching framework defined in Section 11.

---

## Quick Start

1. Fill in your athlete profile (Section 1)
2. Document your equipment (Section 2)
3. Define your training schedule and goals (Section 3)
4. Enter your current performance metrics (Section 4)
5. Set up your nutrition/fueling protocol (Section 5)
6. Link this dossier to your JSON data mirror (see Section 11 for protocol)

---

## 1. Athlete Overview

### Athlete Profile

| Field | Value |
|-------|-------|
| Name | [Your name or alias] |
| Age | [Age] |
| Height | [cm] |
| Current Weight | [kg] |
| Target Weight | [kg] |
| Location | [City, Country] |

**Weigh-in Protocol:** [e.g., Once weekly, Friday morning, after bathroom, before food/drink]

### Medications & Supplements (Optional)

| Time | Items |
|------|-------|
| [Time] | [List medications/supplements] |
| [Time] | [List medications/supplements] |

### Sport Focus

| Type | Description |
|------|-------------|
| Primary | [e.g., Cycling performance (Endurance)] |
| Secondary | [e.g., Running, SkiErg, Walking] |

### Goals

| Goal | Target Date |
|------|-------------|
| [Primary goal] | [Year] |
| [Secondary goal] | [Year] |
| [Tertiary goal] | [Year] |

**Current Phase:** [e.g., Aerobic build + threshold development]  
**Training Style:** [e.g., High-volume polarized (~15h/week)]

---

## 2. Equipment & Environment

### Indoor Training Setup

| Component | Details |
|-----------|---------|
| Trainer/Bike | [Model] |
| Platform | [e.g., Zwift, TrainerRoad, Tacx App] |
| Cooling | [Fans, AC, etc.] |
| Sensors | [HRM, power meter, cadence] |
| Pedals | [Model] |

### Outdoor Setup

| Component | Details |
|-----------|---------|
| Bike | [Model, size] |
| Power Meter | [Model] |
| Head Unit | [Model] |
| HRM | [Model] |

### Other Modalities

| Modality | Equipment | Purpose |
|----------|-----------|---------|
| [e.g., SkiErg] | [Model] | [e.g., Upper-body aerobic] |
| [e.g., Running] | [Shoes, watch] | [e.g., Active recovery] |
| [e.g., Strength] | [Equipment] | [e.g., Core stability] |

### Environment

| Factor | Details |
|--------|---------|
| Indoor | [Description of training space, ventilation, temperature] |
| Outdoor | [Typical terrain, climate, temperature range] |
| Calibration | [Routine for power meter calibration] |

---

## 3. Training Schedule & Framework

### Weekly Volume Target

**Baseline:** [X] hours/week (± [Y] hours)  
**Peak phases:** Up to [Z] hours (requires RI ≥ 0.8, HRV within 10%)

### Normal Weekly Schedule

| Day | Primary Session | Duration | Secondary |
|-----|-----------------|----------|-----------|
| Sunday | [Workout type] | [Duration] | [Optional] |
| Monday | [Workout type] | [Duration] | [Optional] |
| Tuesday | [Workout type] | [Duration] | [Optional] |
| Wednesday | [Workout type] | [Duration] | [Optional] |
| Thursday | [Workout type] | [Duration] | [Optional] |
| Friday | [Workout type] | [Duration] | [Optional] |
| Saturday | [Workout type] | [Duration] | [Optional] |

### Session Details

| Session Type | Target Power/HR | Duration | Purpose |
|--------------|-----------------|----------|---------|
| VO₂Max | [W or % FTP] | [Duration] | [Purpose] |
| Endurance | [W or % FTP] | [Duration] | [Purpose] |
| Sweetspot | [W or % FTP] | [Duration] | [Purpose] |
| Long Ride | [W or % FTP] | [Duration] | [Purpose] |
| Recovery | [W or % FTP] | [Duration] | [Purpose] |

### Recovery Protocol

**Recovery Triggers (Auto-Deload):**
- HRV ↓ > 20% → [Response]
- RHR ↑ ≥ 5 bpm → [Response]
- Feel ≥ 4 → [Response]
- Two+ triggers → [Response]

**Feel Scale:**
| Score | Meaning |
|-------|---------|
| 1 | Excellent (fully recovered) |
| 2 | Good (normal fatigue) |
| 3 | Moderate (manageable tiredness) |
| 4 | Fatigued (reduced readiness, deload trigger) |
| 5 | Exhausted (complete rest required) |

### Performance Objectives

| Year | Phase | Focus | Primary KPI |
|------|-------|-------|-------------|
| [Year] | [Phase name] | [Focus area] | [Target metrics] |
| [Year] | [Phase name] | [Focus area] | [Target metrics] |
| [Year] | [Phase name] | [Focus area] | [Target metrics] |

---

## 4. Performance Metrics

### Current Power Zones

| Zone | % of FTP | Power (W) | Notes |
|------|----------|-----------|-------|
| Z1 | 0–55% | [Calculate] | Active Recovery |
| Z2 | 56–75% | [Calculate] | Endurance (Base) |
| Z3 | 76–90% | [Calculate] | Tempo |
| Z4 | 91–105% | [Calculate] | Threshold |
| Z5 | 106–120% | [Calculate] | VO₂max |
| Z6 | 121–150% | [Calculate] | Anaerobic |
| Z7 | 151%+ | [Calculate] | Neuromuscular |
| SS | 84–97% | [Calculate] | Sweetspot |

**Current FTP:** [W] (Indoor: [W])  
**Max HR:** [bpm]  
**Threshold HR:** [bpm]

### Current Fitness Markers

| Metric | Value | Notes |
|--------|-------|-------|
| FTP (Outdoor) | [W] | |
| FTP (Indoor) | [W] | Adjusted for indoor conditions |
| LT2 Power (MLSS) | [W] | ≈[%] of FTP |
| LT2 HR | [bpm] | |
| LT1 (AeT) | [W] | HR ≈[bpm] |
| VO₂max Interval Power | [W] | |
| Sweetspot Target | [W] | |
| Weekly Volume | [hours] | [TSS range] |

### Weight Tracking

**Protocol:** [Frequency, conditions]  
**Adjustment Control:** Weight adjustments only permitted during readiness-positive periods (DI ≥ 0.95, HR drift ≤ 3%, RI ≥ 0.8)

---

## 5. Nutrition / Fueling

### Training Fuel Recipe

```
[Your carb mix recipe]
```

**CHO per bottle:** [g]  
**Target absorption:** [g CHO/h]

### Recovery Drink Recipe

```
[Your recovery drink recipe]
```

### Fueling by Workout Type

| Workout Type | Duration | CHO Target | Setup |
|--------------|----------|------------|-------|
| Recovery / Z1–Z2 | < 1.5 h | [g/h] | [Description] |
| Endurance | 1.5–3 h | [g/h] | [Description] |
| Long Endurance | 3–6 h | [g/h] | [Description] |
| Threshold / SS | 1–2 h | [g/h] | [Description] |
| VO₂ / High Intensity | 1–1.5 h | [g/h] | [Description] |
| Race / Event | 4–6 h | [g/h] | [Description] |

### Hydration

**Target:** [ml/hour]  
**Sodium:** [mg/L] base, + [mg/h] additional for long/hot rides

---

## 6. Adaptation & Current Focus

### Current Adaptation Focus

- [ ] [Focus item 1]
- [ ] [Focus item 2]
- [ ] [Focus item 3]
- [ ] [Focus item 4]

### Next-Phase Options

[Description of upcoming phase transition criteria and options]

---

## 7. Outdoor Transition Plan (if applicable)

### Transition Timeline

| Month | Changes | Notes |
|-------|---------|-------|
| [Month] | [Transition step] | [Details] |
| [Month] | [Transition step] | [Details] |
| [Month] | [Transition step] | [Details] |

**General Rules:**
- Outdoor rides replace indoor 1:1
- HR < 85% of threshold = aerobic
- Use HR to guide intensity early season

---

## 8. Long-Term Performance Roadmap

### Primary Objective

[Your main goal with target time/performance]

### Progression Overview

| Year | Focus | FTP Target | W/kg Target | Key Metrics |
|------|-------|------------|-------------|-------------|
| [Year] | [Focus] | [W] | [W/kg] | [Metrics] |
| [Year] | [Focus] | [W] | [W/kg] | [Metrics] |
| [Year] | [Focus] | [W] | [W/kg] | [Metrics] |

### Event-Specific Targets (Optional)

| Event/Segment | Year | Target Time | Target Power |
|---------------|------|-------------|--------------|
| [Event] | [Year] | [Time] | [W] |
| [Event] | [Year] | [Time] | [W] |

---

## 9. Coach Notes

[Space for coach observations, athlete-specific considerations, or important reminders]

---

## 10. Operational & Data Integrity Log

### Training Timeline & Event Log

| Date | Event | Notes |
|------|-------|-------|
| [Date] | [Event] | [Details] |
| [Date] | [Event] | [Details] |

### Calibration & Data Log

| Date | Item | Action |
|------|------|--------|
| [Date] | [Equipment] | [Action taken] |
| [Date] | [Equipment] | [Action taken] |

---

## Data Mirror Configuration

### JSON Endpoint (for AI coaches)

**URL:** `https://raw.githubusercontent.com/[username]/[repo]/main/latest.json`

**Archive:** `https://github.com/[username]/[repo]/tree/main/archive`

This endpoint provides synchronized Intervals.icu metrics for deterministic AI parsing. See **Section 11** for the full AI Coach Guidance Protocol.

---

## Protocol Reference

This dossier follows the **Section 11 A/B AI Coach Guidance Protocol** for AI integration.

**Protocol Location:** [Link to your Section 11 document or repo]

---

## Changelog

### v1.0 ([Date])
- Initial dossier creation

