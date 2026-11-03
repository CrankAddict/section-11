# Section 11 public demo

This is **fictional demo data**, generated without a real athlete, account or
credentials. Never use its values as training advice. It demonstrates data
publication and verified official Section 11 updates in a visible repository.

![Daily synthetic sync](https://github.com/CrankAddict/section-11-demo/actions/workflows/auto-sync.yml/badge.svg)

**Last successful sync:** not yet run

The fictional rider uses indoor cycling, five rides and two rest days per week.
All values, identifiers and the sample [DOSSIER.md](DOSSIER.md) are invented.
No GPS routes, private context or health records are included. This public
dossier is a demonstration artifact, never a real athlete's authoritative dossier.

[Sync Now](../../actions/workflows/auto-sync.yml) requests today's synthetic files.
The schedule requests one run at 05:07 UTC daily; GitHub may delay or skip it.
The generator uses only the UTC date, so repeating a date produces identical
bytes. A second run on the same UTC date normally stops at publication's
unchanged-latest guard and makes no data commit; a new update notice can change
the exported notice. Use Status or Update when only maintenance is needed.
The first run creates the JSON files; none are seeded with stale sample dates.

[latest.json](latest.json) contains a seven-day snapshot. [history.json](history.json)
contains 28 synthetic days. The other JSON companions contain labelled sample
FTP history or explicit empty interval, route and workout collections. These
files demonstrate the publication contract, not every sync.py field or analysis.
The timestamp is the synthetic day's midnight UTC, not the runner's wall time.

The single sync/update workflow uses the published sealed user template. Its
data step uses [demo/generate.py](demo/generate.py) at 05:07 UTC daily; publication,
archiving, README timestamp updates and six-file downloads use the ordinary
verified controller.
The fictional producer needs no athlete secrets or slow-source cache.
Real users use the ordinary sync launcher with their own private account and
keep their dossier private. They should not copy this public demo as a data repo.

Official release files live under `section11/`, installed through the normal
first Sync installation. A test or development copy cannot
substitute for an official release. The owner enables
`SECTION11_AUTO_UPDATE=true` after checking the initial installation and data
readbacks. [Actions](../../actions) and repository history show the release
identity, exact parent/tree, direct commit outcome and refusals. The same workflow
offers Sync, Update, Status and Rollback. See the installed
[direct-update contract](section11/examples/maintenance/UPDATING.md#automatic-github-updates).

[SETUP_DEMO.md](SETUP_DEMO.md) has the owner's setup and first-run checks.
Personal experiments belong in [custom/](custom/). Keep this repository entirely
fictional. It uses the official Section 11 release, distributed under [LICENSE](LICENSE).

## Local setup

On your own machine, a local data folder looks like this:

```text
training-data/
├── latest.json, history.json, ...  # live JSON files
├── archive/                       # where present
├── maps/                          # where present
├── section11/                     # managed official files
├── custom/                        # personal files
├── DOSSIER.md                     # private dossier
└── state/                         # private request accounting
```

Keep `state/` on the machine; never publish it. Keep your real dossier private.
Auto sync is installed by default using launchd, systemd, cron or Windows Task
Scheduler; an explicit --no-timer choice keeps manual operation. The configured
check interval is preserved; see the [local sync guide](section11/examples/json-local-sync/SETUP.md).

Local updates are manual by default and ask for your confirmation. You can opt
into a daily update on the first run at or after 04:00 UTC, after data work even
if it failed, with one-step rollback to the previous installation. Failed or
unknown maintenance consumes the day; a rerun may claim an unclaimed day.
Automatic checks skip a rolled-back date; explicit Update installs it and clears
the skip; see [updates and rollback](section11/examples/maintenance/UPDATING.md).
