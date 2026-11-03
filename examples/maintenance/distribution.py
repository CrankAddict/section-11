"""Adapters share the standalone bootstrap's one distribution implementation."""
import importlib.util
from pathlib import Path
import requests

_path = Path(__file__).resolve().parents[1] / 'sync.py'
_spec = importlib.util.spec_from_file_location('section11_distribution_sync', _path)
_sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sync)
Distribution = _sync.Distribution
DistributionError = _sync.DistributionError


class UnknownOutcome(RuntimeError):
    pass

# Plain-language next steps for deliberate, handled stops. Matched on the
# stop message; anything unmatched still gets a safe generic step.
NEXT_STEPS = (
    ('unmanaged installation files',
     'section11/ contains files that are not part of the installed release. Move your own files to custom/ '
     '(see custom/README.md), then run the update again.'),
    ('second same-date release',
     "Today's release already exists. New changes are published in the next nightly release."),
    ('release date does not follow',
     'The latest published release is not older than this run. Nothing was published; check the release list.'),
    ('hash mismatch',
     'manifest.json does not match the files. Regenerate the manifest for the changed files and push; '
     'see the open release issue.'),
    ('publication not on observed default history',
     'Inspect the named commit and repository policy with the owner. No retry or alternate credential was used.'),
    ('no published date release',
     'The first official date release must be published and verified before installation or update. Check Releases.'),
    ('owner wrapper update required',
     'A workflow file must be replaced by hand from the release; GitHub does not let Actions change workflow files.'),
    ('default branch', 'Run this workflow on the default branch.'),
)


def run_cli(main, extra_steps=()):
    """Run an entry point; handled stops end with one clear error line and exit 1.

    Deliberate refusals, transport failures and unknown publication outcomes
    receive actionable messages. Unexpected programming/API errors keep their traceback.
    """
    import sys
    try:
        return main()
    except Exception as exc:
        if not (isinstance(exc, (ValueError, requests.exceptions.RequestException, UnknownOutcome))
                or type(exc) is RuntimeError):
            raise
        message = (str(exc).splitlines() or [type(exc).__name__])[0]
        step = next((s for key, s in tuple(extra_steps) + NEXT_STEPS if key in message),
                    'Nothing further was changed by this run; see the lines above.')
        if isinstance(exc, (requests.exceptions.RequestException, UnknownOutcome)):
            step = 'Outcome may be unknown. Inspect remote state and the workflow log before any retry; no automatic retry was made.'
        print('::error::' + message)
        if exc.__cause__ is not None:
            print('Cause: ' + str(exc.__cause__)[:300])
        print('Next step: ' + step)
        sys.exit(1)
