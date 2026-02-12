# Section 11 — AI Coaching Protocol

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

An open protocol for deterministic, auditable AI-powered endurance coaching. Built for athletes who want AI coaches that follow science, not speculation.

---

## What Is This?

**Section 11** is a structured framework that enables AI systems (ChatGPT, Claude, Gemini, etc.) to provide evidence-based endurance training advice with full auditability and deterministic reasoning.

Most AI coaching today is inconsistent — the same question gets different answers, recommendations aren't grounded in your actual data, and there's no way to verify the reasoning. This protocol fixes that.

### Core Principles

- **Deterministic** — Same inputs produce same outputs, every time
- **Auditable** — Every recommendation cites specific data and frameworks
- **Evidence-based** — Grounded in 15+ peer-reviewed endurance science models
- **Athlete-controlled** — Your data, your thresholds, your goals

---

## What's Included

| File | Description |
|------|-------------|
| [SECTION_11.md](SECTION_11.md) | Complete protocol: AI Coach Guidance (11 A), Training Plan Protocol (11 B), Validation Protocol (11 C) |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Blank athlete dossier template — fill in your own data |
| [examples/](examples/) | JSON sync setup, report templates, README template, example files |
| [changelog.json](changelog.json) | Version tracking — consumed by sync.py for update notifications |
| [LICENSE](LICENSE) | CC BY-NC 4.0 — free for personal use, attribution required |

---

## Quick Start

### 1. Create Your Dossier

Copy `DOSSIER_TEMPLATE.md` and fill in your:
- Athlete profile (age, weight, goals)
- Equipment setup
- Current FTP, HR zones, fitness markers
- Training schedule and targets
- Nutrition/fueling protocol

### 2. Set Up Your Data Mirror (Optional but Recommended)

For best results, create a JSON endpoint with your current Intervals.icu data:

```
https://raw.githubusercontent.com/[USERNAME]/[REPO]/main/latest.json
https://raw.githubusercontent.com/[USERNAME]/[REPO]/main/history.json
```

This allows AI coaches to access your real-time metrics (CTL, ATL, TSB, HRV, recent activities) and longitudinal training history without manual input each session.

See [examples/](examples/) for setup guides.

### 3. Configure Your AI Platform

**Copy-paste instructions for your Project/Space:**
```
# AI Coach Instructions

You are my endurance cycling coach. Follow Section 11 protocol strictly.

## MANDATORY FIRST ACTIONS (every training question):
1. Note today's date
2. Fetch JSON: https://raw.githubusercontent.com/[you]/[repo]/main/latest.json (append ?date= with today's date to ensure fresh data)
3. Fetch history: https://raw.githubusercontent.com/[you]/[repo]/main/history.json (for longitudinal context)
4. If activities don't match today's date, re-fetch before concluding no data exists
5. Match activities to current date
6. Then respond

Do NOT ask me for data — fetch it yourself.

## SOURCE HIERARCHY:
1. **JSON data** — Current metrics from latest.json (FETCH FIRST) + longitudinal data from history.json
2. **Section 11 protocol** (attached) — Coaching rules, thresholds, metric hierarchy
3. **Dossier** — Athlete profile, zones, goals
4. **Report templates** — Fetch from https://github.com/CrankAddict/section-11/tree/main/examples/reports if not attached

Do NOT search web for training advice. Section 11 is the authority.

## OUTPUT FORMAT:
No citations, no source markers, no parenthetical references. Raw data and analysis only.

**Post-workout reports** use structured line-by-line format per session (not bullets). Flow:
1. Data timestamp
2. One-line summary
3. Session block(s) — one per activity, line-by-line:
   Activity type & name, start time, duration (actual vs planned), distance, power (avg/NP), power zones (%), Grey Zone (Z3) %, Quality (Z4+) %, HR (avg/max), HR zones (%), cadence, decoupling (with label), Variability Index (with label), calories (kcal), carbs used (g), TSS (actual vs planned)
4. Weekly totals: Polarization, TSB, CTL, ATL, Ramp rate, ACWR, Hours, TSS
5. Overall: Coach note (2–4 sentences — compliance, quality observations, load context, recovery note)

Omit fields only if data unavailable for that activity type.

**Pre-workout reports** must include: readiness (HRV, RHR, Sleep vs baselines), load context (TSB, ACWR, Monotony if > 2.3), today's planned workout, Go/Modify/Skip recommendation.

See Section 11 → Communication Style and Output Format Guidelines for full rules.

## RULES:
- Follow Section 11 validation checklist (Step 0: Data Source Fetch)
- No virtual math — use only fetched values
- TSB −10 to −30 is typically normal — don't recommend recovery unless other triggers present
- Metric hierarchy: Tier 1 (RI, HRV, RHR, Feel) → Tier 2 (Stress Tolerance, Load-Recovery Ratio, ACWR) → Tier 3 (diagnostics)
- Brief when metrics are normal. Detailed when thresholds are breached or I ask "why"

## DOCUMENTS ATTACHED:
- DOSSIER.md — Profile, zones, goals
- SECTION_11.md — AI coaching protocol (includes validation, metric hierarchy, report format guidelines)
```

**Replace `[USERNAME]/[REPO]` with your actual GitHub data mirror path.**

### 4. Upload Files

Upload these files to your AI platform's knowledge base:

| File | Purpose |
|------|---------|
| `SECTION_11.md` | The coaching protocol (required) |
| `DOSSIER.md` | Your athlete profile (required) |

---

## Platform-Specific Setup

### ChatGPT (Projects)
1. Create a Project
2. Add instructions to Project settings
3. Upload SECTION_11.md and DOSSIER.md to "Project Files"
4. Browsing is enabled by default on Plus/Team

### ChatGPT (CustomGPT)
1. Create GPT → Configure
2. Paste instructions in "Instructions" field
3. Upload files under "Knowledge"
4. Enable "Web Browsing" in Capabilities

### Claude (Projects)
1. Create a Project
2. Add instructions to "Project Instructions"
3. Upload SECTION_11.md and DOSSIER.md to "Project Knowledge"
4. Enable "Web search" in settings (required for JSON fetch)

### Grok
1. Create Project
2. Add instructions to Project configuration
3. Upload files to "Sources"

### Mistral (Le Chat)
1. Create New Project
2. Add instructions and upload files
3. Web access is available

### Gemini (Gems)
1. Create Gem
2. Paste instructions + Section 11 content in instructions field
3. Upload dossier or paste contents

### OpenClaw (formerly ClawdBot/MoltBot)
Section 11 works well with [OpenClaw](https://github.com/openclaw/openclaw). The combination of OpenClaw's persistent memory + autonomous execution + Section 11's structured validation makes for a capable coaching setup.

---

## Testing Your Setup

After configuration, test with:

> "How was today's workout?"

**Good response includes:**
- ✅ Fetched both latest.json and history.json automatically (no asking for it)
- ✅ Session summary with all fields (type, start time, duration, power, HR, TSS, cadence, decoupling, zones, carbs, energy)
- ✅ Training load context (TSB, CTL, ATL, weekly totals)
- ✅ Brief interpretation
- ✅ No "(GitHub)" or URL citations
- ✅ No emojis
- ✅ No false recovery warnings for normal TSB (-10 to -30)

**Bad response:**
- ❌ "I don't have access to your data, please provide..."
- ❌ Missing session fields
- ❌ "(GitHub)" citations throughout
- ❌ "Your TSB is -23, consider recovery" (when no other triggers present)

---

## Troubleshooting

### AI asks for data instead of fetching
- Verify web search/browsing is enabled for your platform
- Check your JSON URL is correct and publicly accessible

### Data still appears stale after cache-bust
- Try a fresh conversation (some platforms cache per-session)
- Manually append a different query param: `...latest.json?v=2`

### Sync workflow not updating JSON
- Check GitHub Actions ran successfully
- Verify Intervals.icu API key is valid
- See [examples/json-auto-sync/SETUP.md](examples/json-auto-sync/SETUP.md)

---

## How It Works

### Section 11 A — AI Coach Guidance Protocol

Defines behavioral rules for AI coaches:

- **No virtual math** — AI must use your actual logged values, not estimates
- **Explicit data requests** — If data is missing, AI asks rather than assumes
- **Tolerance compliance** — Recommendations stay within ±3W / ±1bpm / ±1% variance
- **Framework citations** — Every recommendation references specific science
- **11-point validation checklist** — AI self-validates before responding (Step 0–10)

### Section 11 B — AI Training Plan Protocol

Defines rules for AI systems generating or modifying training plans:

- Phase alignment with macro-cycle
- Volume ceiling validation (±10% of baseline)
- Intensity distribution control (80/20 polarization)
- Session composition rules
- Audit metadata requirements

### Section 11 C — AI Validation Protocol

Standardized metadata schema for audit trails:

```json
{
  "validation_metadata": {
    "data_source_fetched": true,
    "json_fetch_status": "success",
    "protocol_version": "11.1",
    "checklist_passed": [0, 1, 2, 3, 4, 5, 6, "6b", 7, 8, 9, 10],
    "checklist_failed": [],
    "data_timestamp": "2026-01-23T10:02:07Z",
    "data_age_hours": 2.3,
    "confidence": "high",
    "missing_inputs": [],
    "frameworks_cited": ["Seiler 80/20", "Gabbett ACWR"]
  }
}
```

### Scientific Foundations

The protocol integrates 15+ validated endurance science frameworks:

| Framework | Application |
|-----------|-------------|
| Seiler's 80/20 Polarized Training | Intensity distribution |
| Gabbett's ACWR (2016) | Load progression, injury prevention |
| Banister's Impulse-Response | CTL/ATL/TSB dynamics |
| Foster's Monotony & Strain | Overuse detection |
| Issurin's Block Periodization | Phase structure |
| Coggan's Power-Duration Model | Efficiency tracking |
| San Millán's Zone 2 Model | Metabolic health |
| Skiba's Critical Power Model | Fatigue prediction |
| And more... | See Section 11 for full list |

---

## Key Features

### Rolling Phase Logic

Training blocks adapt dynamically based on real data:

```
Base → Build → Peak → Taper → Recovery
```

Phase transitions are triggered by actual metrics (TSB trend, ACWR, RI), not fixed calendar dates.

### Readiness Thresholds

Automatic load adjustment based on recovery status:

| Trigger | Response |
|---------|----------|
| HRV ↓ >20% | Easy day / deload |
| RHR ↑ ≥5 bpm | Flag fatigue/illness |
| Feel ≥4/5 | Reduce volume 30-40% |
| RI <0.6 | Mandatory deload |

### Progression Triggers

Green-light criteria for safe load increases:

- Durability Index ≥0.97 for 3+ long rides
- HR drift <3% in aerobic sessions
- Recovery Index ≥0.85 (7-day mean)
- ACWR within 0.8–1.3
- Feel ≤3/5

---

## Data Integration

### Intervals.icu (Recommended)

The protocol is designed to work with [Intervals.icu](https://intervals.icu) as the primary data source. Set up a JSON mirror that syncs your:

- Fitness metrics (CTL, ATL, TSB, Ramp Rate)
- Recent activities (power, HR, duration, TSS)
- Wellness data (HRV, RHR, sleep, feel)
- Zone distributions
- Planned workouts

### Derived Metrics

The sync script pre-calculates Section 11-compliant metrics so AI doesn't need to compute them:

| Metric | Description |
|--------|-------------|
| ACWR | Acute:Chronic Workload Ratio (0.8–1.3 optimal) |
| Recovery Index | HRV/RHR composite (>1.0 = good recovery) |
| Monotony / Strain | Training variability (Foster) |
| Grey Zone % | Z3 time — minimize in polarized training |
| Quality Intensity % | Z4+ time — target ~20% |
| Polarisation Index | Easy time ratio — target ~0.80 |
| Benchmark Index | 8-week FTP progression (indoor/outdoor) |
| Phase Detected | Auto-detected training phase |

### FTP History Tracking

The script maintains `ftp_history.json` to track indoor and outdoor FTP changes over time, enabling Benchmark Index calculation for long-term progression analysis.

### Longitudinal History

The script generates `history.json` with tiered granularity for trend analysis:

| Tier | Granularity | Range |
|------|-------------|-------|
| `daily_90d` | Day-by-day | Last 90 days |
| `weekly_180d` | Week-by-week | Last 180 days |
| `monthly_1y/2y/3y` | Month-by-month | Up to 3 years |

Includes period summaries, FTP timeline, and data gap detection. Provide both `latest.json` and `history.json` to your AI coach for the most complete analysis.

### Update Notifications

The sync script automatically checks for upstream protocol updates. When a new version of Section 11 is released, a GitHub Issue is created in your data repo with a summary of changes.

### Other Platforms

Also compatible with:
- Any platform that exports structured training data

### Data Hierarchy

When sources conflict, trust order is:

1. Intervals.icu (primary)
2. JSON Mirror (Tier-1 verified)
3. Athlete-provided values (<7 days old)
4. Dossier baselines (fallback)

---

## Example Use Cases

### Daily Check-In
> "How was today's workout?"

### Weekly Review
> "Analyze my last 7 days against my targets. What's my compliance rate? Any red flags?"

### Progression Decision
> "Have I met the green-light criteria for extending my Friday long ride to 5 hours?"

### Session Analysis
> "Here's my workout file. Did I hit my intervals within tolerance? What does the HR drift tell us?"

---

## Limitations

- **AI still makes mistakes** — This protocol reduces errors but doesn't eliminate them
- **Not a replacement for human coaches** — Best used alongside professional guidance for serious athletes
- **Requires honest data** — Garbage in, garbage out
- **No medical advice** — Consult professionals for health concerns

---

## Contributing

This is an open protocol. Contributions welcome:

- **Bug reports** — Found an inconsistency? Open an issue
- **Framework additions** — Know a validated model that should be included? Propose it
- **Translation** — Help make this accessible in other languages
- **Integration guides** — Built a tool that uses this? Share it

---

## License

This work is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).

**You can:**
- Use it for personal training
- Share and adapt it
- Build non-commercial tools with it

**You must:**
- Give appropriate credit
- Link to the license
- Indicate if changes were made

**You cannot:**
- Use it for commercial purposes without permission

**Commercial licensing:** Contact crankaddict69@proton.me

---

## Acknowledgments

- **[David Tinker](https://intervals.icu)** — Creator of Intervals.icu
- **[Clive King](https://www.cliveking.net/)** — Pioneer of GPT-based endurance coaching and URF
- **[Intervals.icu Forum](https://forum.intervals.icu)** community
- **Researchers** behind the scientific frameworks cited in Section 11

---

## Roadmap

- [x] Section 11 A/B/C Protocol
- [x] Dossier Template
- [x] JSON sync automation scripts
- [x] Report templates (pre/post workout)
- [x] Longitudinal history generation (tiered granularity)
- [x] Upstream update notifications via GitHub Issues
- [ ] CustomGPT implementation
- [ ] MCP Server integration

---

## Links

- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Examples:** [examples/](examples/)
- **Report Templates:** [examples/reports/](examples/reports/)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum](https://forum.intervals.icu)

---
