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

## Related Projects

This protocol builds on concepts from the endurance coaching community:

### Clive King's Intervals.icu GPT Coach

**[Intervals.icu GPT Coaching Framework v17](https://github.com/revo2wheels/intervalsicugptcoach-public)** — A full CustomGPT implementation with Railway backend, OAuth integration, and automated reporting via the Unified Reporting Framework (URF) v5.1.

- **Live App:** [cliveking.net](https://www.cliveking.net/) — Working Coach V5 with automated Weekly, Seasonal, and Wellness reports

---

## What's Included

| File | Description |
|------|-------------|
| [SECTION_11.md](SECTION_11.md) | Complete protocol: AI Coach Guidance (11 A), Training Plan Protocol (11 B), Validation Protocol (11 C) |
| [examples/](examples/) | Sync scripts and integration guides |
| [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md) | Blank athlete dossier template — fill in your own data |
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
https://raw.githubusercontent.com/[you]/[repo]/main/latest.json
```

This allows AI coaches to access your real-time metrics (CTL, ATL, TSB, HRV, recent activities) without manual input each session.

#### 3. Use With Any AI

#### Option A: Persistent Setup (Recommended)

For ongoing coaching, create a dedicated space with persistent context:

| Platform    | Feature     | How to Set Up                                                  |
|-------------|-------------|----------------------------------------------------------------|
| **Claude**  | Projects    | Create Project → Add Section 11 + Dossier to Project Knowledge |
| **ChatGPT** | Projects    | Create Project → Add Section 11 + Dossier to Project Files     |
| **ChatGPT** | CustomGPT   | Create GPT → Paste Section 11 in Instructions → Upload Dossier |
| **Gemini**  | Gems        | Create Gem → Add Section 11 + Dossier to instructions          |
| **Grok**    | Projects    | Create Project → Add Section 11 + Dossier to Project Sources   |
| **Mistral** | New Project | Create New Project → Add Section 11 + Dossier to instructions  |
| **Poe**     | Bot         | Create Bot → Add Section 11 as System Prompt → Upload Dossier  |

**Required settings:**
- ✅ Enable **web search / browsing** — Required for the AI to fetch your live JSON data
- ✅ Add your JSON URL to the instructions

**Copy-paste instructions for your Project/Space:**
```
You are my endurance cycling coach. Follow Section 11 protocol strictly.

MANDATORY FIRST ACTION for any training question:
Fetch data from: https://raw.githubusercontent.com/bikedata420/t1-data/refs/heads/main/latest.json
Do NOT ask me for data — fetch it yourself, then respond.

Rules:
- Follow Section 11 validation checklist (start at Step 0: Data Source Fetch)
- Brief responses (1-3 sentences) when metrics normal
- Detailed only when thresholds breached or I ask why
- No virtual math — use only fetched/provided values
- TSB -10 to -30 is NORMAL during build phases — don't recommend recovery unless other triggers present

Documents:
- DOSSIER_DANIEL.md — Profile, zones, thresholds, goals
- SECTION_11.md — Complete AI coaching protocol
```

**Files to attach:**
- `SECTION_11.md` — The protocol
- `DOSSIER.md` (or `.txt`) — Your filled-in athlete dossier

#### Option B: Per-Chat Setup

For quick one-off analysis without persistent setup:

1. Start a new chat
2. Paste Section 11 + your Dossier
3. Provide your JSON URL or paste current data manually
4. Ask your question

**Example prompt:**
> "You are my endurance coach. Follow this protocol: [paste Section 11]. Here is my athlete dossier: [paste dossier]. My current data is at: [JSON URL]. Based on this, how am I recovering? Should I adjust today's session?"

#### Platform Notes

| Platform | Web Access | Notes |
|----------|------------|-------|
| Claude | ✅ Projects + Chat | Enable "Web search" in settings |
| ChatGPT | ✅ Plus/Team | Browsing enabled by default |
| Gemini | ✅ | Web access built-in |
| Grok | ✅ | Web access built-in |
| Mistral | ✅ | Le Chat has web access |
| Perplexity | ✅ | Always searches web |
| Local LLMs | ❌ | Must paste JSON data manually |

#### Tips for Best Results

- **Update your dossier** when FTP, weight, or goals change
- **Check JSON freshness** — If sync fails, the AI should flag stale data
- **Start sessions with context** — "Review my latest.json and summarize my current status"
- **Ask for validation** — "Show me your Section 11 B validation metadata for this response"

---

## How It Works

### Section 11 A — AI Coach Guidance Protocol

Defines behavioral rules for AI coaches:

- **No virtual math** — AI must use your actual logged values, not estimates
- **Explicit data requests** — If data is missing, AI asks rather than assumes
- **Tolerance compliance** — Recommendations stay within ±3W / ±1bpm / ±1% variance
- **Framework citations** — Every recommendation references specific science
- **10-point validation checklist** — AI self-validates before responding

### Section 11 B — AI Training Plan Protocol

Defines structure for AI-generated training plans: phase alignment, load targets, polarization ratios, and audit metadata.

### Section 11 C — AI Validation Protocol

Standardized metadata schema for audit trails:

```json
{
{
  "validation_metadata": {
    "data_source_fetched": true,
    "json_fetch_status": "success",
    "protocol_version": "11.1",
    "checklist_passed": [0, 1, 2, 3, 4, 5, 6, "6b", 7, 8, 9, 10],
    "checklist_failed": [],
    "data_timestamp": "2026-01-13T22:32:05Z",
    "data_age_hours": 2.3,
    "athlete_timezone": "UTC+1",
    "utc_aligned": true,
    "system_offset_minutes": 8,
    "timestamp_valid": true,
    "confidence": "high",
    "missing_inputs": [],
    "frameworks_cited": ["Seiler 80/20", "Gabbett ACWR"],
    "recommendation_count": 3
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
> "Based on my latest.json, how am I recovering? Should I adjust today's session?"

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
- [x] Instructions Template
- [ ] CustomGPT implementation
- [ ] MCP Server integration
- [ ] Intervals.icu OAuth integration guide
- [ ] Forum guides and tutorials

---

## Links

- **Protocol:** [SECTION_11.md](SECTION_11.md)
- **Template:** [DOSSIER_TEMPLATE.md](DOSSIER_TEMPLATE.md)
- **Intervals.icu:** [intervals.icu](https://intervals.icu)
- **Discussion:** [Intervals.icu Forum](https://forum.intervals.icu)

---
