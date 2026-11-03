"""Live-review A-C regressions and small D error/reporting fixes; no live transport."""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from test_update_prototype import (D, SYNC, ROOT, Offline, fixture, manifest, install, write, inventory,
                                   github_api, distribution)
from test_update_path_fixes import Response


# DispatchTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


# AdoptionTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


# HumanScopeTests PR contracts are replaced by direct-commit acceptance in test_b2_hosted.py.


class SmallReportingTests(Offline):
    def test_connection_and_unknown_outcome_get_error_and_next_step_without_traceback(self):
        for exc in (SYNC.requests.ConnectionError('synthetic lost transport'), distribution.UnknownOutcome('push outcome unknown')):
            def fail():
                raise exc
            output = io.StringIO()
            with self.subTest(exc=exc), contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stop:
                distribution.run_cli(fail)
            self.assertEqual(stop.exception.code, 1)
            self.assertIn('::error::', output.getvalue())
            self.assertIn('Next step: Outcome may be unknown', output.getvalue())
            self.assertNotIn('Traceback', output.getvalue())

    def test_missing_first_release_is_clear_for_both_clients(self):
        api = github_api.GitHub(D.UPSTREAM, token='')
        with mock.patch.object(api, 'get', side_effect=github_api.APIError(404, 'not found')):
            with self.assertRaisesRegex(ValueError, 'no published date release'):
                api.release_metadata()
        error = SYNC.requests.HTTPError('404', response=Response(status=404))
        with mock.patch.object(D, 'api_read', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'no published date release'):
                D.release_metadata()


