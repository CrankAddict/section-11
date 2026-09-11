# Private Athlete Context Dossier

**Template version:** 2.1.0

**Dossier revision:** [1.0: increment when an approved change is applied]

**Last reviewed:** [YYYY-MM-DD]

**Protocol compatibility:** Section 11 JSON-first coaching workflow

**Athlete:** [Name or alias]

**Privacy:** [Private local file / private repository / private document store]

**Official dossier location:** [Absolute path, private repository path, or "not applicable — uploaded manually"]

**Authority:** This is the current official dossier and the single source of truth for stable private athlete context. All older dossier files, drafts, exports, and uploaded copies are superseded and must not be used as current context. If more than one copy is present, do not merge them; identify this authority block, compare the dossier revision and last-reviewed date, and ask the athlete which copy is official.

**The official dossier is private.** A sanitized or shareable copy is a separate, non-authoritative artifact: it never carries this authority statement, never replaces the private original, and requires its own explicit sharing approval.

This dossier is a portable context file for AI coaches. It stores stable, athlete-specific information that does not belong in the public Section 11 protocol or in a live training-data feed.

It is deliberately **not** a training dashboard. Current fitness, readiness, body weight, zones, thresholds, planned workouts, recent activities, load, and race state should come from the current JSON data.

> Keep this completed dossier private unless you deliberately create a sanitized copy. Never put passwords, API keys, access tokens, private repository credentials, or other secrets in it.

## Quick start

1. Fill in only information that materially changes coaching advice.
2. Replace bracketed prompts and delete unused rows or sections.
3. Keep exact medication, supplement, allergy, and tested-fueling details when you want an AI to account for them.
4. Link the current JSON data and Section 11 protocol under **Data and protocol sources** (§8).
5. Change this file only through the maintenance rule in §1: a durable change in health, medication, supplements, goals, equipment, environment, constraints, or coaching preference is what triggers a proposal, not a change in fitness, fatigue, phase, schedule, or planned training.

These five steps are completion help for a blank template. Delete this **Quick start** section, including this line, once the dossier is filled in. Retain the scope lists below, the authority and privacy block in the header, and the applicable per-section rules.

## What belongs here

- Stable personal and sport context.
- Long-term goals, priorities, and trade-offs.
- Health context the athlete chooses to disclose.
- Medications, supplements, allergies, intolerances, and tested fueling.
- Stable availability, environment, equipment, and carrying constraints.
- Athlete-specific interpretation notes and communication preferences.
- Pointers to authoritative data and protocol sources.

## What does not belong here

- Current FTP, zones, threshold estimates, weight, fitness, fatigue, or readiness.
- Current phase, weekly schedule, planned workouts, or temporary transition plans.
- Copies of Section 11 decision rules, recovery thresholds, or report instructions.
- Generic training or fueling tables.
- Activity logs, calibration logs, incident timelines, or long release histories.
- Credentials or secrets.

## 1. How an AI should use this file

1. Read this dossier at the start of a coaching session, after losing context, and whenever it changes; reuse that context for follow-ups.
2. Read the current JSON before citing or acting on dynamic training information.
3. Use Section 11 for coaching policy, decision logic, and report formats, and follow the required report format for the task.
4. Use this dossier for stable personal context and constraints, and base recommendations on the relevant personal context, the current data, and the applicable Section 11 rules.
5. When this dossier conflicts with current JSON, use JSON for dynamic facts and ask the athlete before changing a stable personal fact.
6. Treat medications and supplements as context, not as permission to prescribe or change treatment.
7. Distinguish athlete-reported facts, measured data, interpretation, and uncertainty, and state material uncertainty when it affects the advice.

### Maintaining this file

An AI may propose changes to this dossier. It may never make them unilaterally.

1. **Propose the exact change**: the section affected, the current text, the proposed text, and why the fact belongs here rather than in JSON, the calendar, or the conversation.
2. **Obtain the athlete's exact approval.** Approval of one change authorizes that change only. General agreement with an analysis is not approval, and approval from a reviewer or another AI is never a substitute for the athlete's.
3. **Verify write access before applying.** Apply an approved change only against a location whose write access has actually been verified. Otherwise return the revised artifact and say plainly that the source was not updated.
4. **Never emit a full replacement dossier unless the complete current file is in context.** With only an excerpt available, return the changed section clearly labelled as a fragment, not as a replacement.
5. **Increment the dossier revision and update the last-reviewed date** when an approved change is applied, then re-read and confirm what changed.

Review this dossier after a durable change in health, medication, supplements, goals, equipment, environment, constraints, or coaching preference, not after ordinary fluctuations in fitness, fatigue, phase, or scheduling.

## 2. Coaching and communication preferences

Apply these defaults whenever this dossier is current context. Explicit current athlete instructions and task-specific Section 11 requirements take precedence where they conflict; otherwise these defaults fill the gaps. Where a stored preference conflicts materially with a safety or report requirement, surface the conflict once, when it first affects the current task.

### Portable defaults

- Be direct, calm, data-driven, and concise; lead with the recommendation or verdict, grounded in the evidence and the athlete's context.
- Do not invent missing metrics or carry old numbers forward from memory.
- Distinguish athlete-reported facts, measured data, interpretation, and uncertainty.
- Be a focused, critical expert partner; challenge weak reasoning and explain disagreements rather than agreeing reflexively.
- Surface material risks, assumptions, missing context, and missing validation.
- Answer the question asked, without appending unrelated analysis, motivational filler, generic advice, life advice, or tangents.
- Treat athlete-reported feel and lived training experience as real evidence alongside device data.
- Do not repeat an observation unless it is asked for, has materially changed, or is required by the report; stop when asked to stop.
- Ask a question only when the missing information materially affects the answer; otherwise state the assumption being made.

Coaching decision rules, report structure, and threshold logic are **not** here; they belong in Section 11. The compact maintenance rule is in §1; the full dossier lifecycle and approval policy lives in Section 11.

### Athlete-specific overrides

These override the portable defaults above and apply whenever this dossier is current context. They remain subordinate to platform safety rules, the athlete's explicit current request, and task-specific Section 11 requirements.

- Tone: [Direct / supportive / technical / concise / other].
- Preferred answer shape: [Verdict first / short explanation / detailed analysis / report template].
- Technical depth: [Minimal / moderate / expert].
- Motivation style: [What helps; what does not help].
- Repetition tolerance: [Preference].
- Questions and uncertainty: [When the AI should ask rather than assume].

### Decision preferences

- Risk tolerance: [Conservative / balanced / aggressive, with context].
- Preference when evidence is mixed: [Describe].
- Role of athlete-reported feel: [Describe].
- Live pacing preference: [Power / pace / HR / RPE / mixed; source values from JSON].
- Data the athlete prefers hidden during training: [Optional].
- Topics the athlete does not want unsolicited commentary about: [Optional].

## 3. Open review items / facts needing confirmation

- [Missing medication or supplement label details].
- [Fuel recipe or tolerance detail to confirm].
- [Goal, equipment, health, or preference item to confirm].
- [Data-source path or privacy choice to confirm].

Delete this section when no facts need confirmation. List only unresolved facts here; standing maintenance guidance lives in §1, not in the athlete's open items.

## 4. Private profile and goals

| Field | Context |
|---|---|
| Name or alias | [Name] |
| Birth year or age range | [Optional; prefer birth year so the file does not become stale annually] |
| Sex | [Optional; include when relevant to health, medication, nutrition, or performance interpretation] |
| Height | [Optional] |
| Home region | [City/region/country; include only the precision useful for weather, terrain, travel, or altitude context] |
| Primary sport | [Sport and focus] |
| Secondary sports/activities | [Optional] |
| Occupation/lifestyle context | [Only stable facts that affect recovery, schedule, travel, or stress] |

Do not store current body weight or current training status here when those are available in JSON.

### Stable measurement routines (optional)

Record the method and timing of measurements when consistency affects interpretation. Keep current values and targets in JSON.

| Measurement | Stable routine | Last confirmed |
|---|---|---|
| [Body weight / blood pressure / other] | [Example: day, time, fasting state, device, protocol] | [Date] |

### Long-term goals

| Goal | Target date | Priority | Why it matters / success definition |
|---|---|---|---|
| [Goal] | [Date/year/ongoing] | [Primary/secondary] | [Context] |
| [Goal] | [Date/year/ongoing] | [Primary/secondary] | [Context] |

### Priorities and trade-offs

- Primary priority: [Performance / health / event completion / consistency / other].
- Acceptable trade-offs: [Examples: lower short-term performance for sustainability; indoor training for precision].
- Unacceptable trade-offs: [Examples: injury risk, disrupted sleep, excessive travel burden].
- What a successful season looks like: [Plain-language definition].

Event dates, current priority tags, and race-week state belong in the live calendar/JSON.

## 5. Health, medication and supplements

The health, medication, and supplement content in this section is optional and private. Include only what the athlete wants an AI coach to know. Confirm clinically important details with the athlete when they matter to a decision.

### Relevant health context

| Topic | Athlete-provided context | Coaching implication | Last confirmed |
|---|---|---|---|
| [Diagnosis, recurring issue, past injury, mental-health context, sleep issue, etc.] | [Context] | [How advice or interpretation should change] | [Date] |

### Allergies, intolerances, and restrictions

| Type | Item | Reaction/restriction | Last confirmed |
|---|---|---|---|
| [Allergy/intolerance/dietary/clinician restriction] | [Item] | [Context] | [Date] |

### Medication

| Time/frequency | Medication | Dose/formulation | Relevant context | Last confirmed |
|---|---|---|---|---|
| [Time] | [Name] | [Exact dose and formulation] | [Optional; do not speculate about effects] | [Date] |

### Supplements

Keep the full known stack here if supplement review is one reason for maintaining a private dossier. Record exact label doses when possible; “two capsules” is not enough if the active dose per capsule is unknown.

| Time/frequency | Product | Exact active ingredients and total dose | Purpose claimed/experienced | Status | Last reviewed |
|---|---|---|---|---|---|
| [Time] | [Product] | [Label details] | [Why used] | [Keep / review / situational / stopped] | [Date] |

### Supplement audit notes

- Combined-dose concerns: [Overlapping ingredients or “not yet checked”].
- Medication interactions to verify: [Items or “not yet checked”].
- Cost/value notes: [Context].
- Products awaiting exact label photos: [List].

Do not change prescribed medication or add/drop supplements solely because an AI suggests it. Use the dossier to make the stack visible and auditable.

### Athlete-specific data interpretation

Interpretation notes are optional. Whenever one is recorded (in this table or beside the subject it qualifies), the four-column and provenance requirements below apply in full.

Each note needs all four columns. A note without a stated basis is an assumption; a note without an approval date cannot be reviewed. Place a note beside the subject it qualifies where that is clearer than listing it here.

Where a note claims a durable preference revealed consistently across decisions, the factual basis must **cite the specific decisions**. "It recurred" is not a basis.

| Observation | Factual basis | Coaching implication | Approved |
|---|---|---|---|
| [Example: live HR may be elevated by anxiety rather than load] | [Athlete-reported, recurring across sessions] | [Interpret decoupling with athlete-reported context; prefer power as the live pacing signal when valid] | [Date] |
| [Example: indoor and outdoor power differ] | [Measured on both setups] | [Use environment-specific values from JSON; do not treat them as interchangeable] | [Date] |

A note must not contain a diagnosis, a hidden personality assessment, a speculative motive, a raw chat quotation, or an unsupported causal claim.

## 6. Fueling, hydration and recovery

Store the athlete's **tested personal practice**, tolerances, and logistics here. Generic targets and protocol rules belong in Section 11.

### Tested training fuel

| Use case | Exact recipe/product | Amount carried | How it is used | Tolerance/result | Last confirmed |
|---|---|---|---|---|---|
| [Routine training drink] | [Ingredients and quantities] | [Bottle/serving details] | [Personal routine] | [GI tolerance, taste, practicality] | [Date] |
| [Long-event fuel] | [Products/food] | [Capacity] | [Personal routine] | [Result] | [Date] |

### Recovery food/drink

| Recipe/product | Exact ingredients and quantities | When used | Purpose/tolerance | Last confirmed |
|---|---|---|---|---|
| [Recovery drink/meal] | [Details] | [Use case] | [Context] | [Date] |

### Hydration and practical preferences

- Typical carrying capacity: [Bottles/bladder/storage].
- Preferred drink reminder basis: [Time/distance/thirst/no reminder].
- Preferred fuel reminder basis: [Time/distance/no reminder].
- Heat/cold considerations: [Athlete-specific observations].
- Known GI limits or disliked products: [Context].
- Restock preference: [No-stop / planned stops / route-dependent].

## 7. Practical training context and essential equipment

### Availability

Record durable constraints, not this week's plan.

| Constraint | Context |
|---|---|
| Typical available days/times | [Stable pattern or “variable; use calendar”] |
| Maximum practical session window | [Only if genuinely stable] |
| Work/family/travel constraints | [Context] |
| Preferred rest day(s) | [Optional] |
| Indoor/outdoor preference | [Context] |

### Environment

| Factor | Context that changes advice |
|---|---|
| Local terrain | [Flat/rolling/mountainous; road/trail access; traffic constraints] |
| Typical weather | [Heat, cold, rain, wind, altitude, seasonality] |
| Indoor environment | [Cooling, ventilation, heat limitations] |
| Route constraints | [Safe roads, lighting, restock access, technical terrain] |

### Established routines (optional)

Record only durable routines that an AI may need to recall or adapt. Current workout prescriptions still belong in the live plan or JSON.

| Routine | Exact steps or reference | When used | Flexibility/status | Last confirmed |
|---|---|---|---|---|
| [Pre-session activation] | [Exercises, sets, repetitions, duration] | [Use case] | [Default / optional / symptom-dependent] | [Date] |
| [Post-session mobility] | [Exercises and duration] | [Use case] | [Default / optional / symptom-dependent] | [Date] |
| [Other stable routine] | [Details] | [Use case] | [Status] | [Date] |

### Calibration and setup habits (optional)

- Indoor/outdoor fit relationship: [How closely setups match and any durable caveats].
- Power-meter/trainer calibration routine: [Stable practice; do not store a rolling calibration log here].
- Sensor-specific interpretation notes: [Sidedness, known offsets, environmental sensitivities, or other durable context].

### Essential equipment

List only equipment that changes workout prescription, data interpretation, safety, route choice, or fueling logistics.

| Use | Equipment/context |
|---|---|
| Indoor training | [Trainer/bike/platform/cooling] |
| Outdoor training | [Bike/shoes/power meter/head unit] |
| Sensors | [HR, power, temperature, glucose, etc.] |
| Safety/navigation | [Radar, lights, emergency equipment] |
| Other modalities | [Equipment and purpose] |
| Carrying capacity | [Bottles, hydration pack, food/storage limits] |

Keep this table concise. Record only what changes advice. If a fuller inventory is genuinely useful, put it in the optional **Appendix A** rather than expanding this table.

## 8. Data and protocol sources

### Configuration

Fill in the method(s) the athlete actually uses. Delete unused examples.

| Purpose | Source/path/repository |
|---|---|
| Current snapshot | [Local path, private connector path, or URL to `latest.json`] |
| Longitudinal history | [Path/URL to `history.json`] |
| Recent interval detail | [Path/URL to `intervals.json`] |
| FTP history | [Path/URL to `ftp_history.json`] |
| Planned route terrain | [Path/URL to `routes.json`] |
| Section 11 protocol | [Path or official repository URL] |
| Report templates | [Path or official repository URL] |

**Data directory:** [Runtime-accessible location where training data is read (local path, provider-hosted path, mounted folder, connector root) or "not applicable"]

This is where a runtime reads training data. It is **not** the authoritative dossier copy; that is recorded as **Official dossier location** in the header block at the top of this file.

**Last data-source check:** [Date]

### Privacy choices

- Recommended local setup: keep the completed dossier outside the public Section 11 repository and point the AI to its path.
- Connector setup: store it only in a private repository or private document source if the athlete accepts that access model.
- Manual handoff: upload the dossier directly to the AI for the task or conversation.
- Public sharing: create a sanitized copy rather than publishing the private original.

Never store API credentials in this file, even when the data source requires authentication.

### External-AI handoff

For a fresh AI coach, provide:

1. The completed private dossier.
2. The current JSON files needed for the task.
3. The current Section 11 protocol or relevant report template.
4. The date, timezone, and specific request.

Suggested handoff prompt:

> Use the attached dossier only for stable personal context. Use the current JSON files for all dynamic training facts and metrics. Follow the attached/current Section 11 protocol for coaching decisions and report structure. If the sources conflict, distinguish the conflict and ask before changing a stable personal fact.

## Appendix A. Detailed equipment inventory (optional)

Optional. Use this only if a fuller inventory is genuinely useful to the athlete. Anything that actually changes workout prescription, data interpretation, safety, route choice, or fueling logistics belongs in **Essential equipment** (§7), not here. Delete this appendix when it is not used.

| Category | Items and details |
|---|---|
| Indoor setup | [Trainer/bike, platform, cooling, display/devices] |
| Outdoor setup | [Bike, components, tires, spares] |
| Sensors and safety | [HR, power, temperature, radar, lights, tracking] |
| Storage and carrying | [Bags, bottles, hydration pack, capacity] |
| Clothing and contact points | [Shoes, cleats, helmet, saddle, layering] |
| Other modalities and tools | [Equipment and purpose] |
| Apps and services | [Platforms used and what each is used for] |
