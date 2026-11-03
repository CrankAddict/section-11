"""Rebase integration: updater success gates and private Intervals state."""
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

from test_update_prototype import D, SYNC, ROOT, Offline, install, inventory, write, validate_data
from test_update_path_fixes import ReleaseHTTP


class RebaseIntegrationTests(Offline):
    def test_update_status_install_and_rollback_preserve_real_request_ledger(self):
        wire = ReleaseHTTP(1)
        install(self.root / 'section11', wire.raw[0], wire.files[0])
        write(self.root / 'section11', {D.RECEIPT: D.receipt(wire.raw[0], wire.identity(0))})
        with mock.patch.dict(os.environ, {'SECTION11_STATE_DIR': '', 'GITHUB_ACTIONS': ''}):
            budget = SYNC.RequestBudget(self.root, 'sync', SYNC.RequestBudgetRefused,
                                        SYNC.RequestBudget.fingerprint('i123', 'synthetic'))
            with budget._lock():
                budget._load()
                budget.state['days'][budget.day]['sync'] = {'seed': 4}
                budget._save()
            self.assertEqual(budget.root.parent, self.root / 'state/request-budget')
            write(self.root, {'state/sources/synthetic/entry.json': b'{"private": true}',
                              'custom/README.md': b'Owner text', 'latest.json': b'{}'})
            before = inventory(self.root / 'state')
            with wire.intercepted(), mock.patch.object(Path, 'cwd', return_value=self.root), \
                    mock.patch.object(SYNC, '__file__', str(self.root / 'section11/examples/sync.py')), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(SYNC.RequestBudget, '__init__', side_effect=AssertionError('updater opened budget')):
                self.assertTrue(SYNC.do_update(status_only=True))
                SYNC.auto_update_local(self.root, True)
                self.assertEqual(D.tree(self.root / 'section11'), (wire.raw[1], wire.files[1]))
                self.assertTrue(SYNC.do_rollback())
                self.assertEqual(D.tree(self.root / 'section11'), (wire.raw[0], wire.files[0]))
            self.assertEqual(len(wire.calls), 10)
            self.assertTrue(all(urlparse(url).hostname in ('api.github.com', 'github.com',
                                                          'raw.githubusercontent.com') for url in wire.calls))
            self.assertEqual(inventory(self.root / 'state'), before)
            self.assertEqual((self.root / 'custom/README.md').read_bytes(), b'Owner text')
            self.assertEqual((self.root / 'latest.json').read_bytes(), b'{}')
            self.assertFalse((self.root / 'section11/state').exists())
            self.assertFalse((self.root / 'custom/state').exists())

    def test_private_state_declaration_and_deletion_are_never_published(self):
        private = self.root / 'state/sources/private.json'
        private.parent.mkdir(parents=True)
        private.write_text('{"private": true}')
        def latest(paths):
            return {'data_overview': {'version': 1, 'managed_files': paths}}
        good = latest(['latest.json', 'maps/weather/page.json'])
        write(self.root, {'latest.json': json.dumps(good).encode(), 'maps/weather/page.json': b'{}'})
        self.assertEqual(validate_data.plan(self.root)['saved'], good['data_overview']['managed_files'])
        for name in ('state/sources/private.json', 'State/sources/private.json'):
            with self.assertRaisesRegex(ValueError, 'reserved data path'):
                validate_data.checked_path(self.root, name)
            bad = latest(['latest.json', name])
            (self.root / 'latest.json').write_text(json.dumps(bad))
            plan = validate_data.plan(self.root)
            self.assertEqual(plan['mode'], 'legacy_fallback')
            self.assertEqual(plan['saved'], ['latest.json'])
            (self.root / 'latest.json').write_text(json.dumps(good))
            self.assertEqual(validate_data.plan(self.root, bad)['removed'], [])
        self.assertEqual(private.read_text(), '{"private": true}')

    def test_budget_wait_or_refusal_still_attempts_update(self):
        for refused in (False, True):
            instance = mock.Mock()
            instance.request_budget.degraded = True
            instance.begin_tick.side_effect = SYNC.RequestBudgetRefused('synthetic hold') if refused else None
            instance.begin_tick.return_value = False
            with mock.patch.object(SYNC, 'IntervalsSync', return_value=instance), \
                    mock.patch.object(SYNC, '_rotate_log_if_needed'), \
                    mock.patch.object(SYNC.os.path, 'exists', return_value=False), \
                    mock.patch.object(SYNC, 'auto_update_local') as auto, \
                    mock.patch.object(SYNC, 'notify_if_updates_available') as notice, \
                    mock.patch.object(sys, 'argv', ['sync.py', '--athlete-id', 'i123', '--intervals-key',
                                                  'synthetic', '--output', str(self.root / 'latest.json'),
                                                  '--auto-update']), contextlib.redirect_stdout(io.StringIO()):
                SYNC._main(installation_root=self.root, distribution_locked=True)
            auto.assert_called_once_with(self.root, True, _locked=True, advisory_only=False, started_at=SYNC.datetime.now(SYNC.timezone.utc))
            notice.assert_not_called()
            instance.save_local_outputs.assert_not_called()

