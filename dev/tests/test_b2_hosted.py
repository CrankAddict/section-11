"""B2 acceptance over a synthetic content-addressed remote; no Git or network."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
from unittest import mock

from test_update_prototype import D, Offline, ROOT, fixture, manifest
from direct_commit import DirectPublisher, blob_sha
from distribution import UnknownOutcome
import hosted_update as H


class Remote:
    def __init__(self, files=None):
        self.repo = 'synthetic/data'
        self.blobs, self.trees, self.commits, self.calls = {}, {}, {}, []
        self.ref_fault = None
        self.on_ref = None
        self.fail_reads = False
        self.tip = self.commit(files or {}, [], 'Initial synthetic repository')

    def tree_id(self, entries):
        value = copy.deepcopy(entries)
        identity = hashlib.sha1(json.dumps(value, sort_keys=True).encode()).hexdigest()
        self.trees[identity] = value
        return identity

    def commit(self, changes, parents, message):
        entries = copy.deepcopy(self.trees[self.commits[parents[0]]['tree']['sha']]) if parents else {}
        for name, data in changes.items():
            if data is None:
                entries.pop(name, None)
            else:
                identity = blob_sha(data)
                self.blobs[identity] = data
                entries[name] = {'path': name, 'mode': '100644', 'type': 'blob', 'sha': identity}
        return self.commit_tree(self.tree_id(entries), parents, message)

    def commit_tree(self, tree, parents, message):
        value = {'tree': {'sha': tree}, 'parents': [{'sha': p} for p in parents], 'message': message}
        identity = hashlib.sha1(json.dumps(value, sort_keys=True).encode()).hexdigest()
        self.commits[identity] = dict(value, sha=identity)
        return identity

    def metadata(self):
        self.calls.append(('GET', 'metadata'))
        return {'default_branch': 'main', 'private': True}

    def tree(self, tree):
        self.calls.append(('GET', 'tree'))
        return copy.deepcopy(self.trees[tree])

    def blob(self, identity):
        self.calls.append(('GET', 'blob'))
        return self.blobs[identity]

    def ancestors(self, commit):
        result, pending = set(), [commit]
        while pending:
            item = pending.pop()
            if item not in result:
                result.add(item)
                pending.extend(p['sha'] for p in self.commits[item]['parents'])
        return result

    def get(self, path):
        self.calls.append(('GET', path))
        if self.fail_reads:
            raise RuntimeError('synthetic readback unavailable')
        if path == '/git/ref/heads/main':
            return {'object': {'type': 'commit', 'sha': self.tip}}
        if path.startswith('/git/commits/'):
            return copy.deepcopy(self.commits[path.rsplit('/', 1)[1]])
        if path.startswith('/compare/'):
            left, right = path.split('/compare/')[1].split('...')
            status = ('identical' if left == right else 'ahead' if left in self.ancestors(right)
                      else 'behind' if right in self.ancestors(left) else 'diverged')
            return {'status': status}
        if path.startswith('/commits?'):
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(path).query)
            wanted = query.get('path', [None])[0]
            limit = int(query.get('per_page', ['100'])[0])
            result = []
            tip = query.get('sha', [self.tip])[0]
            while tip and len(result) < limit:
                commit = self.commits[tip]
                parents = commit['parents']
                entries = self.trees[commit['tree']['sha']]
                prior = self.trees[self.commits[parents[0]['sha']]['tree']['sha']] if parents else {}
                relevant = lambda tree: {p: v for p, v in tree.items()
                                         if p == wanted or p.startswith(wanted + '/')}
                if wanted is None or relevant(entries) != relevant(prior):
                    result.append({'sha': tip, 'commit': {'message': commit['message']}})
                tip = parents[0]['sha'] if parents else None
            return result
        raise AssertionError('unexpected API read: ' + path)

    def write(self, method, path, body):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path == '/git/blobs':
            data = base64.b64decode(body['content'])
            identity = blob_sha(data)
            self.blobs[identity] = data
            return {'sha': identity}
        if path == '/git/trees':
            entries = copy.deepcopy(self.trees[body['base_tree']])
            for entry in body['tree']:
                if entry['sha'] is None:
                    entries.pop(entry['path'], None)
                else:
                    entries[entry['path']] = entry
            return {'sha': self.tree_id(entries)}
        if path == '/git/commits':
            return {'sha': self.commit_tree(body['tree'], body['parents'], body['message'])}
        if path == '/git/refs/heads/main':
            assert method == 'PATCH' and body['force'] is False
            if self.on_ref:
                self.on_ref(self)
            if self.ref_fault == 'denied':
                raise RuntimeError('synthetic 403 protected branch')
            if self.tip not in self.ancestors(body['sha']):
                raise RuntimeError('synthetic non-fast-forward rejection')
            self.tip = body['sha']
            if self.ref_fault == 'unknown':
                self.fail_reads = True
            if self.ref_fault in ('unknown', 'lost'):
                raise RuntimeError('synthetic accepted response lost')
            if self.ref_fault == 'later':
                self.tip = self.commit({'custom/later.md': b'later'}, [self.tip], 'Later owner change')
            return {'object': {'type': 'commit', 'sha': self.tip}}
        raise AssertionError('unexpected API mutation: ' + path)

    def inventory(self):
        return {p: self.blobs[e['sha']] for p, e in self.trees[self.commits[self.tip]['tree']['sha']].items()}


def release(date='2026.10.30', version='11.103'):
    raw, files = fixture(version)
    return raw, files, {'repository': D.UPSTREAM, 'tag': date, 'commit': 'c' * 40}


class HostedAcceptance(Offline):
    def setUp(self):
        super().setUp()
        self.protected = {'latest.json': b'{"training":"unchanged"}', 'DOSSIER.md': b'private dossier',
                          'custom/mine.txt': b'personal', '.github/workflows/auto-sync.yml': b'owner workflow',
                          '.sync_config.json': b'{"secret":"synthetic-only"}'}
        self.remote = Remote(dict(self.protected, **{'sync.py': b'legacy', 'push.py': b'old push',
                                                    'pull.py': b'old pull'}))
        self.publisher = DirectPublisher(self.remote)
        self.fetch = mock.Mock(return_value=release())
        self.updater = H.HostedUpdater(self.publisher, self.fetch, {})

    def install(self, updater=None):
        return (updater or self.updater).install(self.publisher.snapshot(), accepted=True)

    def test_T10_first_run_unknown_tree_latest_and_exact_preservation(self):
        self.remote.tip = self.remote.commit({'section11/unknown.txt': b'personal managed edit',
                                              'section11/manifest.json': b'damaged'}, [self.remote.tip], 'Old copy')
        before = self.publisher.snapshot()
        after = self.install()
        self.assertEqual(after['parents'], [before['commit']])
        actual = self.remote.inventory()
        raw, files, identity = self.fetch.return_value
        expected = {'section11/' + p: b for p, b in files.items()}
        expected.update({'section11/manifest.json': raw, 'section11/' + D.RECEIPT: D.receipt(raw, identity)})
        self.assertEqual({p: b for p, b in actual.items() if p.startswith('section11/')}, expected)
        for p, value in self.protected.items():
            self.assertEqual(actual[p], value)
        self.assertFalse(set(H.ROOT_TOOLS) & actual.keys())
        self.assertEqual(actual['custom/README.md'], files['examples/maintenance/CUSTOM_README.md'])
        self.assertEqual(len([c for c in self.remote.calls if c[0] == 'PATCH']), 1)
        self.assertFalse(any('/pulls' in c[1] or '/issues' in c[1] for c in self.remote.calls))

    def test_T10_no_acceptance_has_no_fetch_or_write(self):
        with self.assertRaisesRegex(ValueError, 'acceptance'):
            self.updater.install(self.publisher.snapshot())
        self.fetch.assert_not_called()
        self.assertFalse(any(c[0] != 'GET' for c in self.remote.calls))

    def test_T10_reappeared_roots_and_unknown_managed_files_removed(self):
        self.install()
        self.remote.tip = self.remote.commit({'sync.py': b'reappeared', 'section11/unknown.txt': b'edit',
                                             'custom/README.md': b'owner guide'}, [self.remote.tip], 'Edit')
        self.install()
        self.assertNotIn('sync.py', self.remote.inventory())
        self.assertNotIn('section11/unknown.txt', self.remote.inventory())
        self.assertEqual(self.remote.inventory()['custom/README.md'], b'owner guide')

    def test_T12_denied_unknown_and_lost_response_have_exactly_one_attempt(self):
        for fault in ('denied', 'unknown', 'lost', 'later'):
            with self.subTest(fault=fault):
                remote = Remote({'sync.py': b'legacy'})
                remote.ref_fault = fault
                pub = DirectPublisher(remote)
                updater = H.HostedUpdater(pub, lambda: release(), {})
                before = pub.snapshot()
                if fault == 'lost':
                    after = updater.install(before, accepted=True)
                    self.assertEqual(after['commit'], remote.tip)
                else:
                    with self.assertRaises((RuntimeError, UnknownOutcome)):
                        updater.install(before, accepted=True)
                self.assertEqual(len([c for c in remote.calls if c[0] == 'PATCH']), 1)
                if fault == 'denied':
                    self.assertEqual(remote.tip, before['commit'])

    def test_T12_racing_human_data_custom_and_workflow_commits_survive(self):
        for path in ('latest.json', 'custom/mine.txt', '.github/workflows/auto-sync.yml', 'section11/owner.txt'):
            with self.subTest(path=path):
                remote = Remote({'sync.py': b'old'})
                remote.on_ref = lambda r: setattr(r, 'tip', r.commit({path: b'owner change'}, [r.tip], 'Owner'))
                pub = DirectPublisher(remote)
                updater = H.HostedUpdater(pub, lambda: release(), {})
                with self.assertRaisesRegex(RuntimeError, 'no retry'):
                    updater.install(pub.snapshot(), accepted=True)
                self.assertEqual(remote.inventory()[path], b'owner change')
                self.assertEqual(remote.inventory()['sync.py'], b'old')
                self.assertEqual(len([c for c in remote.calls if c[0] == 'PATCH']), 1)

    def test_T12_tip_change_before_objects_stops_without_mutation(self):
        before = self.publisher.snapshot()
        self.remote.tip = self.remote.commit({'custom/later': b'keep'}, [self.remote.tip], 'Owner')
        with self.assertRaisesRegex(ValueError, 'default tip changed'):
            self.updater.install(before, accepted=True)
        self.assertFalse(any(c[0] != 'GET' for c in self.remote.calls))

    def test_T12_unexpected_prepared_tree_or_parent_never_reaches_ref_write(self):
        for fault in ('tree', 'parent'):
            with self.subTest(fault=fault):
                remote = Remote({'sync.py': b'old'})
                original = remote.write
                def corrupt(method, path, body):
                    result = original(method, path, body)
                    if fault == 'tree' and path == '/git/trees':
                        remote.trees[result['sha']].pop('section11/LICENSE')
                    if fault == 'parent' and path == '/git/commits':
                        remote.commits[result['sha']]['parents'] = []
                    return result
                remote.write = corrupt
                pub = DirectPublisher(remote)
                updater = H.HostedUpdater(pub, lambda: release(), {})
                with self.assertRaisesRegex(ValueError, 'differs'):
                    updater.install(pub.snapshot(), accepted=True)
                self.assertFalse(any(c[0] == 'PATCH' for c in remote.calls))
                self.assertEqual(remote.inventory(), {'sync.py': b'old'})

    def test_T12_exact_scope_rejects_extra_file_or_changed_payload(self):
        before = self.publisher.snapshot()
        expected = H.target_changes(before, release(), H.control(None))
        for extra in ({'DOSSIER.md': b'bad'}, {'section11/LICENSE': b'bad'},
                      {'.github/workflows/auto-sync.yml': b'bad'}, {'custom/mine.txt': b'bad'}):
            with self.subTest(extra=next(iter(extra))):
                with self.assertRaisesRegex(ValueError, 'exact validated'):
                    self.publisher.publish(before, dict(expected, **extra), 'Bad', H.exact_validator(expected))
        self.assertFalse(any(c[0] != 'GET' for c in self.remote.calls))

    def test_T13_status_does_not_claim_adopt_or_repair(self):
        before = self.remote.inventory()
        result = self.updater.status(self.publisher.snapshot())
        self.assertEqual(result['installed'], 'unknown')
        self.assertEqual(self.remote.inventory(), before)
        self.assertFalse(any(c[0] != 'GET' for c in self.remote.calls))

    def test_T13_root_only_rollback_stops_with_workflow_recovery_before_write(self):
        self.install()
        before = self.remote.inventory()
        writes = len([c for c in self.remote.calls if c[0] != 'GET'])
        with self.assertRaisesRegex(ValueError, 'earlier workflow'):
            self.updater.rollback(self.publisher.snapshot())
        self.assertEqual(self.remote.inventory(), before)
        self.assertEqual(len([c for c in self.remote.calls if c[0] != 'GET']), writes)

    def test_T13_rollback_preserves_new_data_custom_and_suppresses_release(self):
        self.fetch.return_value = release('2026.10.29', '11.102')
        self.install()
        prior = {p: v for p, v in self.remote.inventory().items() if p.startswith('section11/')}
        update = H.HostedUpdater(self.publisher, lambda: release(), {})
        self.install(update)
        self.remote.tip = self.remote.commit({'latest.json': b'newer data', 'custom/mine.txt': b'newer custom'},
                                             [self.remote.tip], 'Later data')
        update.rollback(self.publisher.snapshot())
        actual = self.remote.inventory()
        self.assertEqual({p: v for p, v in actual.items() if p.startswith('section11/')}, prior)
        self.assertEqual(actual['latest.json'], b'newer data')
        self.assertEqual(actual['custom/mine.txt'], b'newer custom')
        self.assertEqual('2026.10.30', H.control(actual[H.CONTROL])['skip_release'])
        with self.assertRaisesRegex(ValueError, 'remains skipped'):
            with mock.patch.dict(update.env, {'SECTION11_AUTO_UPDATE': 'true'}):
                update.install(self.publisher.snapshot(), automatic=True)
        self.install(update)
        self.assertIsNone(H.control(self.remote.inventory()[H.CONTROL])['skip_release'])

    def test_T13_rollback_refuses_later_code_edit(self):
        self.fetch.return_value = release('2026.10.29', '11.102')
        self.install()
        update = H.HostedUpdater(self.publisher, lambda: release(), {})
        self.install(update)
        self.remote.tip = self.remote.commit({'section11/LICENSE': b'new owner edit'}, [self.remote.tip], 'Edit')
        before = self.remote.inventory()
        with self.assertRaisesRegex(ValueError, 'later code edits'):
            update.rollback(self.publisher.snapshot())
        self.assertEqual(self.remote.inventory(), before)

    def test_T13_same_release_root_repair_uses_latest_installation_not_receipt_history(self):
        self.install()
        self.remote.tip = self.remote.commit({'push.py': b'owner reappeared root'}, [self.remote.tip], 'Owner')
        before = self.remote.inventory()
        self.install()
        self.assertNotIn('push.py', self.remote.inventory())
        self.updater.rollback(self.publisher.snapshot())
        self.assertEqual(self.remote.inventory()['push.py'], before['push.py'])
        self.assertTrue(all('path=' in call[1] and 'per_page=1' in call[1]
                            for call in self.remote.calls if '/commits?' in call[1]))

    def test_T13_recorded_installation_with_unrelated_changes_stops(self):
        self.fetch.return_value = release('2026.10.29', '11.102')
        self.install()
        prior_tip = self.remote.tip
        update = H.HostedUpdater(self.publisher, lambda: release(), {})
        self.install(update)
        tip = self.remote.tip
        commit = self.remote.commits[tip]
        # Build a real synthetic child tree with an extra, unauthorized change.
        changes = dict(self.remote.inventory(), **{'DOSSIER.md': b'unrelated'})
        self.remote.tip = self.remote.commit(changes, [prior_tip], commit['message'])
        with self.assertRaisesRegex(ValueError, 'unrelated changes'):
            update.rollback(self.publisher.snapshot())

    def test_T11_claim_is_confirmed_before_release_read_failure_consumes_day(self):
        def fail():
            self.assertEqual(H.control(self.remote.inventory()[H.CONTROL])['attempted_day'], '2026.10.30')
            raise ValueError('synthetic release failure')
        updater = H.HostedUpdater(self.publisher, fail, {})
        with self.assertRaisesRegex(ValueError, 'synthetic release failure'):
            updater.maintain(self.publisher.snapshot(), '2026.10.30', True)
        before = self.remote.tip
        updater.maintain(self.publisher.snapshot(), '2026.10.30', True)
        self.assertEqual(self.remote.tip, before)

    def test_T11_failed_export_claims_day_and_rerun_cannot_repeat(self):
        before = self.remote.tip
        self.updater.maintain(self.publisher.snapshot(), '2026.10.30', False)
        self.assertNotEqual(self.remote.tip, before)
        self.fetch.assert_called_once()
        claimed = self.remote.tip
        self.updater.maintain(self.publisher.snapshot(), '2026.10.30', True, run_attempt=2)
        self.assertEqual(self.remote.tip, claimed)
        self.fetch.assert_called_once()

    def test_T11_denied_claim_never_reads_release(self):
        self.remote.ref_fault = 'denied'
        with self.assertRaises(RuntimeError):
            self.updater.maintain(self.publisher.snapshot(), '2026.10.30', True)
        self.fetch.assert_not_called()

    def test_T11_half_notifies_full_installs_and_target_is_shared(self):
        old = H.HostedUpdater(self.publisher, lambda: release('2026.10.29', '11.102'), {})
        self.install(old)
        before = self.remote.tip
        after, status = self.updater.maintain(self.publisher.snapshot(), '2026.10.30', True)
        self.assertNotEqual(after['commit'], before)
        self.assertEqual(H.receipt(self.remote.inventory()['section11/' + D.RECEIPT])['tag'], '2026.10.29')
        self.assertEqual(H.control(self.remote.inventory()[H.CONTROL])['available_date'], '2026.10.30')
        self.fetch.assert_called_once()
        full = H.HostedUpdater(self.publisher, self.fetch, {'SECTION11_AUTO_UPDATE': 'true'})
        full.maintain(self.publisher.snapshot(), '2026.10.31', True)
        self.assertNotIn('sync.py', self.remote.inventory())
        self.assertEqual(self.fetch.call_count, 2)

    def test_T17_known_downgrade_and_changed_same_date_hold(self):
        self.install()
        for target in (release('2026.10.29'), (*release()[:2], dict(release()[2], commit='d' * 40))):
            updater = H.HostedUpdater(self.publisher, lambda: target, {})
            before = self.remote.tip
            with self.assertRaises(ValueError):
                self.install(updater)
            self.assertEqual(self.remote.tip, before)

    def test_T11_suppression_clears_pending_notice_without_installing(self):
        self.fetch.return_value = release('2026.10.29', '11.102')
        self.install()
        state = H.control(self.remote.inventory()[H.CONTROL])
        state['available_date'] = '2026.10.30'
        state['skip_release'] = '2026.10.30'
        self.remote.tip = self.remote.commit({H.CONTROL: H.encoded(state)}, [self.remote.tip], 'Prior notice')
        updater = H.HostedUpdater(self.publisher, lambda: release(), {})
        updater.maintain(self.publisher.snapshot(), '2026.10.30', True)
        self.assertIsNone(H.control(self.remote.inventory()[H.CONTROL])['available_date'])
        self.assertEqual(H.receipt(self.remote.inventory()['section11/' + D.RECEIPT])['tag'], '2026.10.29')

    def test_T14_nonordinary_and_type_collisions_refuse(self):
        before = self.publisher.snapshot()
        for name, mode, kind in (('section11/file', '120000', 'blob'), ('section11', '160000', 'commit'),
                                  ('custom', '100644', 'blob'), ('custom/README.md/child', '100644', 'blob'),
                                  ('sync.py/child', '100644', 'blob'),
                                  ('README.md', '120000', 'blob'), ('README.md/child', '100644', 'blob')):
            with self.subTest(name=name):
                snapshot = copy.deepcopy(before)
                snapshot['entries'][name] = {'path': name, 'mode': mode, 'type': kind, 'sha': 'a' * 40}
                with self.assertRaises(ValueError):
                    H.target_changes(snapshot, release(), H.control(None))


class HostedPolicyTests(Offline):
    def test_T04_only_explicit_boolean_auto_update_setting(self):
        for env, expected in (({}, False), ({'SECTION11_AUTO_UPDATE': 'true'}, True),
                              ({'SECTION11_AUTO_UPDATE': 'false'}, False)):
            self.assertEqual(H.policy(env), expected)
        for value in ('1', 'yes', 'invalid'):
            with self.assertRaises(ValueError):
                H.policy({'SECTION11_AUTO_UPDATE': value})

    def test_T11_creation_boundaries_delayed_start_and_on_demand(self):
        for time, expected in (('03:59:59', None), ('04:00:00', '2026.10.30'),
                               ('04:17:00', '2026.10.30'), ('23:59:59', '2026.10.30')):
            self.assertEqual(H.eligible_day('2026-10-30T' + time + 'Z', 'schedule', True), expected)
        self.assertIsNone(H.eligible_day('2026-10-30T00:01:00Z', 'workflow_dispatch', True,
                                        scheduled=False))
        self.assertIsNone(H.eligible_day('2026-10-30T04:17:00Z', 'schedule', True, scheduled=False))
        self.assertEqual(H.eligible_day('2026-10-30T04:17:00Z', 'schedule', False, run_attempt=2),
                         '2026.10.30')

    def test_T14_control_schema_rejects_private_extra_and_invalid_dates(self):
        value = H.control(None)
        self.assertEqual(H.control(H.encoded(value)), value)
        for bad in (dict(value, token='synthetic'), dict(value, attempted_day='tomorrow'),
                    dict(value, skip_release='2026.02.30'), dict(value, schema=True)):
            with self.assertRaises(ValueError):
                H.control(H.encoded(bad))
        state = dict(value, skip_release='2026.10.29')
        self.assertEqual(H.suppression(state, {}),
                         {'2026.10.29'})
