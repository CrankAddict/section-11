# DFA a1 — Non-Garmin Platforms

> **Status: Documentation only.** Section 11's DFA a1 features currently work with one source: AlphaHRV on Garmin. This file tracks what other platforms could plausibly support, what's been verified, and what we'd need from a non-Garmin user to confirm.

---

## Why this exists

The DFA a1 Protocol in `SECTION_11.md` requires the [AlphaHRV](https://apps.garmin.com/en-US/apps/40fd5e67-1ed0-457b-944b-19fdb3aae7e7) Connect IQ data field by Marco Altini, recording on a Garmin head unit, syncing directly to Intervals.icu (Strava strips developer fields). Other head units have varying paths to DFA a1 — some plausible, none currently verified end-to-end against the Section 11 pipeline.

This file:

1. Documents the **current support status** per platform, honestly labeled
2. Names **specific verification gaps** for each plausible alternative
3. Provides **discovery commands** that a user on the relevant platform can run and paste back to us
4. Explains how to **contribute** verification or fixes via GitHub issues / PRs

If you're on a non-Garmin platform and want DFA a1 to work, this file is for you. We'd like to help, but we need a user on the relevant device to run the commands — none of the maintainers own Wahoo, Karoo, Coros, or Suunto hardware.

---

## Status by platform

| Platform | Path | Status | Notes |
|---|---|---|---|
| **Garmin** + AlphaHRV | Connect IQ data field → FIT developer field → Intervals.icu `dfa_a1` stream → `sync.py` | ✅ **Supported** | The reference path. Validated end-to-end. See `SECTION_11.md` DFA a1 Protocol §Overview. |
| **Suunto** + Zone Sense (DDFA) | SuuntoPlus app → FIT developer field → ? | ⚠️ **Investigational** | Suunto records DDFA (Dynamic DFA) via Zone Sense / Monicardi partnership. **Different algorithm than DFA a1** — values are not directly comparable, threshold mapping (1.0/0.5) may not apply. Even if Intervals.icu surfaces the field, Section 11 would need a separate protocol section to interpret it. |
| **Hammerhead Karoo** + [veloVigil](https://github.com/velovigil/velovigil-karoo) | Karoo extension (Android sideload) → ? | ⚠️ **Investigational, gaps known** | veloVigil is an open-source Karoo extension (MIT licensed) that connects to Polar H10 over BLE and computes HRV (RMSSD, SDNN, pNN50). **Currently does NOT compute or write DFA a1** — that would require a contribution upstream. Hammerhead's own "log RR to FIT" is on the roadmap but not shipped as of late 2025. |
| **Phone fallback** (FatMaxxer / HRV Logger) | Phone app records on a separate device → CSV export → manual reconciliation with the ride activity | ❌ **Evaluated, not supported** | Both apps output CSV from a phone running in parallel with the head unit. Neither writes into the ride's FIT, so the alpha1 record is always a separate file that has to be time-aligned and merged per ride. Even with Intervals.icu's Supporter-only streams.csv upload, the workflow is manual, fragile, and architecturally distinct from AlphaHRV's "just record the ride" path. See *Phone fallback (evaluated, not supported)* below. |
| **Wahoo** (ELEMNT, BOLT, ROAM) | — | ❌ **No supported path** | Wahoo's ELEMNT firmware does not log RR intervals to the FIT file, and Wahoo has no third-party app platform analogous to Connect IQ. DFA a1 in Section 11 currently requires Garmin + AlphaHRV. |
| **Coros** | — | ❌ **No supported path** | Coros watches do not log in-activity HRV/RR. DFA a1 in Section 11 currently requires Garmin + AlphaHRV. |
| **Polar** (head units / watches) | — | ❌ **No supported path** | Polar records HRV but does not share it with third-party platforms via API. DFA a1 in Section 11 currently requires Garmin + AlphaHRV. |

---

## Phone fallback (evaluated, not supported)

Two phone apps can record DFA a1 in parallel with a ride: [FatMaxxer](https://github.com/IanPeake/FatMaxxer) on Android (Polar H10 only, Apache 2.0, [formally validated against Kubios in EJAP, October 2025](https://link.springer.com/article/10.1007/s00421-025-06037-0)) and [HRV Logger](https://www.hrv.tools/) on iOS (paid, by Marco Altini, works with any BLE strap broadcasting RR). Both have been evaluated for Section 11 and **neither is supported**.

The reason is architectural, not algorithmic. Both apps run on a phone, on a device separate from the bike computer that records the ride. Both output CSV — neither writes into the ride's FIT file. That means the alpha1 record is always a second file that has to be time-aligned and merged with the ride per session. Even with Intervals.icu's Supporter-only `streams.csv` upload (added October 2025), the user workflow is: record on two devices, export from the phone, download the activity's stream CSV, manually align timestamps, add an `dfa_a1` column, re-upload. Per ride. Forever. The algorithmic accuracy of FatMaxxer (validated by EJAP) is real but orthogonal — it doesn't make the integration story any less fragile.

By contrast, AlphaHRV runs *on* the Garmin head unit, writes alpha1 as a FIT developer field into the same file as the ride, and Intervals.icu picks it up natively on upload. Zero user steps after recording. That's the bar Section 11 requires of any supported DFA a1 source: alpha1 must arrive time-aligned with the ride without manual reconciliation.

If a future Android/iOS app records into the ride's FIT directly (rather than producing a parallel file), or if a head-unit-side DFA a1 implementation appears for Wahoo / Coros / Karoo, that path will be re-evaluated. Until then, **Garmin + AlphaHRV is the only supported source.**

> **Note:** HRV4Training is also by Marco Altini but is a separate app for resting morning HRV measurements, not in-activity recording. It is not relevant to DFA a1 in Section 11.

---

## Discovery commands

If you're on a non-Garmin platform and want to help verify a path, run the relevant block below and paste the output as a [GitHub issue](https://github.com/CrankAddict/section-11/issues). All commands are read-only.

### Intervals.icu credentials (needed for all platforms)

```bash
# Set these once
ATHLETE=i123456                      # your athlete id (i + digits)
KEY=your_intervals_icu_api_key       # from intervals.icu Settings → Developer Settings
```

### Suunto: does Intervals.icu surface DDFA from Suunto FIT files?

**Goal:** find one recent Suunto-sourced ride where Zone Sense was active, and check whether Intervals.icu exposes any DFA / DDFA / alpha stream or interval field.

```bash
# 1. List recent Suunto activities (look for type=Ride and source=SUUNTO)
curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/athlete/$ATHLETE/activities?limit=10" \
  | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(a['id'], a.get('start_date_local','')[:10], 'src=', a.get('source',''), a.get('name',''))
"

# 2. Pick a recent Zone Sense ride and substitute its ID below
ACT=i123456789

# 3. Check stream types — does any contain dfa, alpha, or ddfa?
curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/activity/$ACT/streams" \
  | python3 -c "
import sys, json
for s in json.load(sys.stdin):
    print(s.get('type'), '|', s.get('name'), '| len=', len(s.get('data', []) or []))
"

# 4. Check activity-level fields and intervals for DDFA
curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/activity/$ACT" \
  | python3 -m json.tool | grep -iE 'dfa|alpha|ddfa|hrv'

curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/activity/$ACT/intervals" \
  | python3 -m json.tool | grep -iE 'dfa|alpha|ddfa|hrv' | head -20
```

**What we're looking for in the output:**
- A stream with `type` containing `dfa`, `alpha`, or `ddfa` → Intervals.icu exposes Suunto DDFA, and we know the stream name to use
- A non-null `average_dfa_a1` field on intervals → Intervals.icu maps Suunto DDFA into the same slot as AlphaHRV (unlikely but possible)
- Nothing → Intervals.icu does not currently surface Suunto DDFA. The data is in the FIT file (per Suunto's API docs) but Intervals.icu doesn't expose it via API.

### Karoo: does veloVigil (or any Karoo HRV path) write something Intervals.icu surfaces?

```bash
# 1. List recent Karoo activities
curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/athlete/$ATHLETE/activities?limit=10" \
  | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    src = a.get('source','')
    dev = a.get('device_name','')
    if 'KAROO' in src.upper() or 'KAROO' in dev.upper() or 'HAMMERHEAD' in src.upper():
        print(a['id'], a.get('start_date_local','')[:10], 'src=', src, 'dev=', dev, a.get('name',''))
"

# 2. Pick a Karoo ride (ideally one where veloVigil was running) and substitute below
ACT=i123456789

# 3. Same checks as Suunto: stream types, activity fields, intervals
curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/activity/$ACT/streams" \
  | python3 -c "
import sys, json
for s in json.load(sys.stdin):
    print(s.get('type'), '|', s.get('name'), '| len=', len(s.get('data', []) or []))
"

curl -s -u "API_KEY:$KEY" "https://intervals.icu/api/v1/activity/$ACT" \
  | python3 -m json.tool | grep -iE 'dfa|alpha|hrv|rr_'
```

**What we're looking for:**
- A `hrv` stream → Karoo + veloVigil is writing per-second HRV to the FIT and Intervals.icu picks it up. (This wouldn't be DFA a1 directly — it'd be RMSSD or similar — but it confirms the dev-field path works on Karoo.)
- A `dfa_a1` stream → veloVigil (or another Karoo extension) is writing DFA a1 directly. **If this exists, sync.py works on Karoo with zero changes.**
- Nothing → no Karoo extension is currently writing HRV-related fields that Intervals.icu surfaces. The path is theoretically viable but no app fills it yet.

### Phone fallback verification

Not applicable — phone fallback is not supported. See *Phone fallback (evaluated, not supported)* above for the architectural reason.

---

## Contribute

If you're on Suunto, Karoo, Wahoo, Coros, Polar, or trying the phone fallback, and you want DFA a1 to work in Section 11:

1. **Run the relevant discovery commands above.**
2. **Open a [GitHub issue](https://github.com/CrankAddict/section-11/issues)** with title `DFA a1 verification: <platform>`.
3. **Paste the full command output** (sanitized — no API keys, no athlete IDs you don't want public).
4. **Tell us your setup**: head unit model, strap, app versions, sync path to Intervals.icu (direct or via Strava — direct is required for any of this to work).

If the verification reveals a path that needs a small `sync.py` change (e.g. new stream name to map), we'll do it. If it reveals a contribution upstream is needed (e.g. veloVigil could write DFA a1), we'll either help draft the upstream PR or document what's needed clearly enough for someone else to.

We don't own non-Garmin hardware, so we can't verify any of this ourselves. Your output is the only way these paths get built.

---

## Honesty notes

- **None of the non-Garmin paths are currently verified end-to-end.** Section 11 supports Garmin + AlphaHRV. Everything else in this file is plausible-but-unverified, clearly labeled.
- **The Suunto DDFA path may never produce identical numbers to DFA a1.** Different algorithm. Even if Intervals.icu exposes Suunto DDFA, Section 11 would need a separate `DDFA a1 Protocol` section with its own threshold validation before it could be interpreted. We're not building that speculatively.
- **Phone fallback (FatMaxxer / HRV Logger) was evaluated and is not supported.** Both apps record on a separate device from the bike computer and output CSV, requiring per-ride manual time alignment and merge into the activity stream. AlphaHRV records into the ride's FIT directly, so it has no equivalent reconciliation cost. See *Phone fallback (evaluated, not supported)* above.
- **Wahoo, Coros, and Polar have no supported DFA a1 path.** Section 11 currently requires Garmin + AlphaHRV. That's a hardware/firmware limitation on those platforms, not a Section 11 design choice — we'd happily support any head unit that records alpha1 (or RR with a recognized alpha1 developer field) into the ride's FIT.
