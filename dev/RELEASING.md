# Maintainer release tools

These tools prepare and verify official release sources. They do not authorize
publication, edit Git history, generate a manifest, or change an athlete install.
Run them only from the reviewed full source checkout with the maintainer's normal
Python/Requests environment. No tool installs dependencies.

When retiring an official file, add its exact basename to `Distribution.HISTORICAL_NAMES` in `examples/sync.py` so later releases still remove old copies.

## First release

The public main producer and legacy manifest must remain unchanged until a
compatible official release is published and independently read back. The first
default-branch commit contains only the release workflow and a temporary hidden
publisher runtime. Prepare that exact overlay in a new directory outside the
source checkout:

```sh
python3 -I -B examples/maintenance/prepare_first_release.py --source . --output ../release-infrastructure
```

The output lists seven files: `.github/workflows/release.yml` plus six source
files under `.github/release-runtime/`. It contains no root manifest, public
producer entry or user guide. The hidden sync.py is required by distribution.py
for the main-owned publisher's manifest/archive checks. It is not a workflow pin
target. The entire hidden runtime is excluded from athlete releases and removed
on the staging branch when the complete candidate is added.

Before either commit, seal all six values offline from the reviewed bytes:

```sh
python3 -I -B examples/maintenance/seal_pins.py seal --source .
python3 -I -B examples/maintenance/seal_pins.py check --source .
```

The verifier is the candidate's own examples/sync.py. Its Git blob ID is SHA1 of
`blob <byte-length>\0<bytes>`; SHA256 separately authenticates the raw bytes. The
tool fills the bootstrap's verifier pair first, computes the resulting bootstrap
pair, fills both workflow pairs and reads back the exact written files. It needs
no Git repository, token or network for seal/check. Output reports both real
blob/digest pairs, the three changed paths and `published: false` for sealing.

Both source targets are fetched from the official repository's authenticated
`git/blobs/{sha}` raw endpoint. The workflow/bootstrap check both Git object
identity and SHA256 before execution, with size/time bounds and no redirects or
retries. A SHA1 collision cannot bypass the independent SHA256 check. A valid
offline address does not prove the object has been pushed or is retrievable.

Prepare two source commits: P contains the infrastructure overlay on main; W
contains all reviewed source, already-sealed pins and the owner-generated manifest
on a staging branch descending from P. No bootstrap-only commit is needed. After
W is pushed, use its full 40-character commit ID and privately supplied existing
GITHUB_TOKEN to verify the four named paths and independent raw/JSON readbacks:

```sh
python3 -I -B examples/maintenance/seal_pins.py verify --source . --commit FULL_W_SHA
```

The remote check admits at most 40 reads within 60 seconds, at most ten seconds
per read. Missing blobs, wrong bytes/digests, truncated/ambiguous trees or wrong
path modes stop. Identical offline resealing is harmless; changing an existing
seal requires reviewed source edits. All blocks/preimages are checked before
writes; an I/O failure still requires inspection and is not automatically retried.

Dispatch the main release workflow with W's full source commit. It checks
the selected commit and active workflow identity using default-owned code, runs
tests without publication authority, and repeats verification on a fresh writer
runner. Only after publication/readback may W be promoted using the owner's normal
merge policy. A merge/squash may create a different commit, but its complete Git
tree must equal W's tree; preserve W as the immutable release source/tag target.

## Publication and readback

The workflow runs on the default branch only. A blank source input uses its
pinned main commit after the first release; the infrastructure-only stage waits
for an explicit source input. The scheduled 02:17 UTC release remains unchanged.
Unchanged manifest content is a no-op; a different second release on the same UTC
date is refused. Never retag or replace published assets to resolve a failure.

The canonical ZIP, two lossless reading files and example PNG retain full
reconstruction checks. Three additional assets are exact manifest-covered copies:
`section11-YYYY.MM.DD-hosted-bootstrap.py`, `section11-YYYY.MM.DD-auto-sync.yml`
and `section11-YYYY.MM.DD-on-demand.yml`. Every asset is read back before and after
publication. A missing or different asset keeps the release incomplete.

The read-only promotion check, executed from the trusted main checkout against
the clean staged source checkout, is:

```sh
python3 -I -B TRUSTED_PUBLISHER --source STAGED_SOURCE --commit FULL_SOURCE_SHA --verify-published
```

`TRUSTED_PUBLISHER` is the main checkout's
`.github/release-runtime/examples/maintenance/publish_release.py` during the
first release, then `examples/maintenance/publish_release.py`. The placeholder
source path must name the exact clean checkout. Run with the official repository
and default-branch environment used by the release workflow. A pass prints
`Promotion readback verified:` followed by the actual date and commit. It proves
latest discovery, canonical source identity, all seven asset bytes and final tag
readback at that time. It does not move main or prove a subsequent user's install.

After promotion, rerun from trusted code against the same clean W source:

```sh
python3 -I -B TRUSTED_PUBLISHER --source STAGED_SOURCE --commit FULL_W_SHA --verify-promoted
```

This repeats published readback, compares main tip's complete root tree with W's,
then rereads main to reject a concurrent change. It accepts equal trees at different
commit IDs and rejects any extra/conflicted file, mode or path. A normal merge may
add a history commit; it needs no third prepared source/pin commit. Do not retag W,
rebase away its source availability, or advertise main before these checks pass.

The historical verifier pin intentionally need not equal a later release's
producer. Trusted older verifier code can authenticate a newer producer under the
same release format; ordinary producer changes need no workflow pin churn.
