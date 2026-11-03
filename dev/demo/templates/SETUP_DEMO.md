# Owner setup: CrankAddict/section-11-demo

The owner creates and operates this one public repository after the updater is
published and verified. It contains fictional data only. This kit does not create
the repository or install a release for you. The first Sync does the installation.

1. Wait for the first official date release containing verified release updates
   (Protocol 11.103 / sync.py 3.166 or later). If no official date release exists,
   stop here. Use the matching published, sealed source to build this kit.
   Do not use a test kit or development files. A workflow containing UNSEALED
   stops before checkout or installation; never invent pins.
2. Create **CrankAddict/section-11-demo**, **Public**, default branch `main`.
   Add this kit's owner files, including its single
   `.github/workflows/auto-sync.yml`. No managed tree needs to be uploaded.
   There is no Intervals account, `ATHLETE_ID` or `INTERVALS_KEY` to configure.
   GitHub supplies the job token; no personal token is needed.
3. Immediately before the owner-file commit, accept the installation terms:

   > Anything you added or changed inside section11/ will be deleted. Move what you want to keep to custom/ first.

   Root sync.py, push.py and pull.py will be removed if present. Outside
   `section11/`, any file in any folder named exactly like a release or historical
   Section 11 file is removed, except the update guide's keep list.
   Protection ignores case; removal requires exact spelling. Keep your own files
   in `custom/` or outside the repository. Existing data,
   custom files and the fictional dossier stay. Commit through the repository's
   normal policy. This action authorizes the first installation.
4. Enable Actions and effective **contents: write** and **actions: read** access.
   No PR-creation or merge setting is required. A protected-branch refusal stops
   without retry or alternate credentials; resolve repository policy explicitly.
   Confirm **Auto-Sync Intervals.icu Data** appears in Actions on the default branch.
   A committed file alone does not prove workflow registration.
5. Initially leave `SECTION11_AUTO_UPDATE` absent or false for half mode.
   No athlete secrets are needed.
6. Select **Sync** in the same workflow. Its bootstrap verifies the latest official
   release and reads back one installation commit before generating fictional
   files. Inspect the complete `section11/` inventory, manifest, receipt tag,
   full commit SHA and manifest digest, missing custom guidance and all outside removals.
   Then inspect the separate data commit: seven labelled JSON files, today's UTC
   archive and README timestamp. The data timestamp is synthetic midnight UTC.
   A manual Sync also offers the standard six-file training-data artifact.
7. Select **Status** in that workflow. It shows the verified target without an
   installation or training export. Select **Update** to accept a newer verified
   replacement when available; there is no adoption PR or merge.
8. Read the installed [update contract](section11/examples/maintenance/UPDATING.md).
   Set **SECTION11_AUTO_UPDATE=true** only after verifying the first installation
   and data readback. Automatic checks run once per UTC day at or after 04:00 UTC,
   after data work even if it failed. Failed or unknown maintenance consumes the
   day; a rerun can claim an unclaimed day. The daily 05:07 UTC data run
   uses the ordinary once-per-day update allowance.
   A later official release installs directly after trusted validation.
   Do not manufacture official releases for the demo.
9. Verify the next scheduled data run and the next genuine update's exact
   parent/tree readback in Actions and repository history. A dispatch acceptance
   or green badge alone is not proof of installation.

The generator is deterministic per UTC date. Repeating that date normally stops
at the unchanged-latest guard without another data commit; a newly recorded
update notice can change the exported notice. Use Status or Update for maintenance
without a needless data run. No slow-source cache is used by the fictional producer.

Set `SECTION11_AUTO_UPDATE=false` to disable future automatic installations.
Cancel an in-flight run separately and inspect its readback. **Rollback** restores
only a compatible previous managed installation and records its rejected date;
newer data/custom remain. A pre-adoption or missing-history recovery requires the
owner to restore the matching old workflows and installation paths from history.
Never revert the whole repository. An unknown publication result needs remote
inspection before another run.

The generator and fictional dossier remain outside `section11/`. Updates cannot
replace them or the active workflow. Review future workflow changes separately,
preserving the fictional producer, its data-run condition and daily data schedule.
This repository publishes every committed file to everyone.
