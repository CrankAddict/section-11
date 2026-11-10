"""CP2 identities, mixed entries and single-attempt publication, all offline."""
import contextlib
import io
import json
from datetime import datetime, timedelta, timezone
from unittest import mock

from test_update_prototype import D, SYNC, Offline, fixture, manifest, install, write, inventory, publish_release as P
from _release_fakes import ReleaseAPI
from test_b2_hosted import Remote, release
from direct_commit import DirectPublisher
from hosted_update import HostedUpdater, control, encoded, CONTROL


class IdentityTests(Offline):
    def test_numeric_order_and_strict_tags(self):
        tags = ['2026.11.09', '2026.11.09-2', '2026.11.09-10', '2026.11.10']
        self.assertEqual(sorted(reversed(tags), key=D.release_key), tags)
        self.assertEqual(D.release_key('2028.02.29-999999')[1], 999999)
        for tag in ('2026.02.29-2', '0000.01.01', '2026.11.09-1', '2026.11.09-0',
                    '2026.11.09-02', '2026.11.09-+2', '2026.11.09--2', '2026.11.09-2-3',
                    '2026.11.09-1000000', '2026.11.09-٢', '2026.11.09-2\n', None):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                D.release_key(tag)

    def test_calendar_fields_reject_suffixes(self):
        state = control(None)
        state.update(installed_date='2026.11.09-2', skip_release='2026.11.09-10')
        self.assertEqual(control(encoded(state)), state)
        state['attempted_day'] = '2026.11.09-2'
        with self.assertRaises(ValueError):
            control(encoded(state))
        for day in ('2026-11-09-2', '2026.11.09-2', '2026-02-29'):
            write(self.root, {'auto-update.json': json.dumps({'last_attempt': day}).encode()})
            with self.assertRaises(ValueError):
                SYNC._auto_update_state(self.root)
        write(self.root, {'auto-update.json': b'{"last_attempt":"2026-11-09"}'})
        self.assertEqual(SYNC._auto_update_state(self.root)['last_attempt'], '2026-11-09')

    def test_local_order_identity_and_higher_labels(self):
        raw, files = fixture()
        ident = {'tag': '2026.11.09-2', 'commit': 'a' * 40}
        install(self.root, raw, files)
        write(self.root, {D.RECEIPT: D.receipt(raw, ident)})
        target = dict(ident, tag='2026.11.09-10', commit='b' * 40)
        self.assertEqual(SYNC._local_release_status(self.root, raw, files, target)['target_date'], target['tag'])
        for bad in (dict(ident, tag='2026.11.09'), dict(ident, commit='b' * 40)):
            with self.assertRaises(ValueError):
                SYNC._local_release_status(self.root, raw, files, bad)
        changed = dict(files, LICENSE=b'new')
        with self.assertRaisesRegex(ValueError, 'same-date'):
            SYNC._local_release_status(self.root, manifest(changed), changed, ident)
        lower_raw, lower_files = fixture('1.0')
        self.assertTrue(SYNC._local_release_status(self.root, lower_raw, lower_files, target)['content_ahead'])

    def test_local_skip_is_exact_and_half_mode_can_notice_next_suffix(self):
        raw, files = fixture('11.100')
        root = self.root / 'section11'
        install(root, raw, files)
        write(root, {D.RECEIPT: D.receipt(raw, {'tag': '2026.11.09', 'commit': 'a' * 40})})
        state = self.root / '.section11-state'
        for index, (tag, available) in enumerate((('2026.11.09-2', None), ('2026.11.09-3', '2026.11.09-3'))):
            write(state, {'auto-update.json': b'{"skip_release":"2026.11.09-2"}'})
            target = raw, files, {'tag': tag, 'commit': 'b' * 40}
            with mock.patch.object(SYNC, '_fetch_verified_release', return_value=target) as fetch, \
                    mock.patch.dict(SYNC.os.environ, {'GITHUB_ACTIONS': 'false'}), \
                    contextlib.redirect_stdout(io.StringIO()):
                SYNC.auto_update_local(self.root, False, advisory_only=True,
                                       started_at=datetime(2026, 11, 10, 12, tzinfo=timezone.utc) + timedelta(minutes=10 * index))
            fetch.assert_called_once()
            saved = SYNC._auto_update_state(state)
            self.assertEqual(saved.get('available_release'), available)
            self.assertEqual(SYNC._known_local_identity(root)['tag'], '2026.11.09')

    def test_hosted_higher_content_still_holds_automatic_suffix(self):
        api = Remote()
        publisher = DirectPublisher(api)
        HostedUpdater(publisher, lambda: release('2026.11.09', '11.200'), {},
                      suffix_capable=True).install(publisher.snapshot(), accepted=True)
        updater = HostedUpdater(publisher, lambda: release('2026.11.09-2', '11.100'),
                                {'SECTION11_AUTO_UPDATE': 'true'}, suffix_capable=True)
        before = api.tip
        with self.assertRaisesRegex(ValueError, 'higher installed version'):
            updater.install(publisher.snapshot(), automatic=True)
        self.assertEqual(api.tip, before)
        updater.install(publisher.snapshot(), accepted=True)

    def test_hosted_default_holds_suffix_without_suffix_records(self):
        for operation in ('status', 'install', 'maintain'):
            for auto in ('true', 'false'):
                with self.subTest(operation=operation, auto=auto):
                    api = Remote()
                    publisher = DirectPublisher(api)
                    HostedUpdater(publisher, lambda: release('2026.11.09'), {}).install(publisher.snapshot(), accepted=True)
                    updater = HostedUpdater(publisher, lambda: release('2026.11.09-2'), {'SECTION11_AUTO_UPDATE': auto})
                    before = publisher.snapshot()
                    with self.assertRaisesRegex(ValueError, 'compatible workflow'):
                        if operation == 'maintain':
                            updater.maintain(before, '2026.11.10', True)
                        elif operation == 'install':
                            updater.install(before, accepted=True)
                        else:
                            updater.status(before)
                    state = control(publisher.read(publisher.snapshot(), CONTROL))
                    self.assertEqual(state['installed_date'], '2026.11.09')
                    self.assertIsNone(state['available_date'])
                    if operation != 'maintain':
                        self.assertEqual(api.tip, before['commit'])

    def test_hosted_hook_skip_exact_update_and_numeric_guards(self):
        api = Remote()
        publisher = DirectPublisher(api)
        def updater(tag, **kwargs):
            return HostedUpdater(publisher, lambda: release(tag, **kwargs),
                                 {'SECTION11_AUTO_UPDATE': 'true'}, suffix_capable=True)
        updater('2026.11.09').install(publisher.snapshot(), accepted=True)
        updater('2026.11.09-2').install(publisher.snapshot(), accepted=True)
        updater('2026.11.09-2').rollback(publisher.snapshot())
        self.assertTrue(updater('2026.11.09-2').status(publisher.snapshot())['suppressed'])
        self.assertFalse(updater('2026.11.09-3').status(publisher.snapshot())['suppressed'])
        with self.assertRaisesRegex(ValueError, 'remains skipped'):
            updater('2026.11.09-2').install(publisher.snapshot(), automatic=True)
        updater('2026.11.09-2').install(publisher.snapshot(), accepted=True)
        self.assertIsNone(control(publisher.read(publisher.snapshot(), CONTROL))['skip_release'])
        updater('2026.11.09-10').install(publisher.snapshot(), accepted=True)
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            updater('2026.11.09-2').status(publisher.snapshot())

    def test_hosted_same_tag_changed_manifest_or_commit_stops(self):
        api = Remote()
        publisher = DirectPublisher(api)
        original = release('2026.11.09-2')
        HostedUpdater(publisher, lambda: original, {}, suffix_capable=True).install(publisher.snapshot(), accepted=True)
        raw, files, ident = original
        changed = dict(files, LICENSE=b'new')
        for target in ((manifest(changed), changed, ident), (raw, files, dict(ident, commit='f' * 40))):
            before = api.tip
            with self.assertRaisesRegex(ValueError, 'same-date'):
                HostedUpdater(publisher, lambda: target, {}, suffix_capable=True).install(publisher.snapshot(), accepted=True)
            self.assertEqual(api.tip, before)


class PublisherTests(Offline):
    def setUp(self):
        super().setUp()
        self.api = ReleaseAPI()
        self.raw, self.files = fixture()
        self.commit = 'b' * 40
        self.api.manifests[self.commit] = self.raw
        for patch in (mock.patch.object(P, 'workflow_gate'), mock.patch.object(P, 'upload', self.api.upload),
                      mock.patch.object(P.time, 'sleep'), contextlib.redirect_stdout(io.StringIO())):
            patch.__enter__()
            self.addCleanup(patch.__exit__, None, None, None)

    def run_publish(self, day='2026.11.09'):
        return P.publish(self.api, self.commit, self.raw, self.files, day)

    def previous(self, tag='2026.11.09', **kwargs):
        old = dict(self.files, LICENSE=b'previous')
        return self.api.seed(tag, 'a' * 40, manifest(old), old, **kwargs)

    def test_first_changed_same_day_numeric_next_and_next_day(self):
        self.previous('2026.11.09-2')
        self.previous('2026.11.09-10')
        self.api.latest = '2026.11.09-10'  # Explicitly set/confirmed by the publisher.
        self.assertEqual(self.run_publish(), 'published')
        self.assertIn('2026.11.09-11', self.api.releases)
        self.assertFalse(self.api.releases['2026.11.09-11']['prerelease'])
        self.assertEqual([w[2] for w in self.api.writes if w[0] == 'PATCH'],
                         [{'draft': False, 'make_latest': 'true'}])

    def test_first_release_and_next_day_use_bare_day(self):
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(self.api.latest, '2026.11.09')
        self.commit = 'c' * 40
        self.files = dict(self.files, LICENSE=b'next day')
        self.raw = manifest(self.files)
        self.api.manifests[self.commit] = self.raw
        self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertEqual(self.api.latest, '2026.11.10')

    def test_unchanged_has_no_zip_dependency_or_sequence_use(self):
        self.api.seed('2026.11.09', 'a' * 40, self.raw, self.files)
        self.raw = json.dumps(json.loads(self.raw), indent=4).encode()
        self.assertEqual(self.run_publish(), 'unchanged')
        self.assertEqual(self.api.writes, [])
        self.assertFalse(any(c[0] == 'ASSET' for c in self.api.calls))
        self.assertEqual(set(self.api.tags), {'2026.11.09'})

    def test_missing_and_broken_previous_zip_allow_changed_source(self):
        self.previous(assets=True)
        for asset in self.api.assets.values():
            asset['data'] = b'broken old asset'
        old_ids = set(self.api.assets)
        self.assertEqual(self.run_publish(), 'published')
        self.assertFalse(any(c[0] == 'ASSET' and c[1] in old_ids for c in self.api.calls))

    def test_missing_previous_source_stops_before_write(self):
        self.previous()
        del self.api.manifests['a' * 40]
        with self.assertRaises(P.APIError):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_lost_tag_reply_stops_then_resumes_same_identity_after_midnight(self):
        self.previous()
        self.api.fail = ('POST', '/git/refs', 'after')
        with self.assertRaisesRegex(RuntimeError, 'tag creation'):
            self.run_publish()
        self.assertEqual(len(self.api.writes), 1)
        self.assertIn('2026.11.09-2', self.api.tags)
        self.api.fail = None
        self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertIn('2026.11.09-2', self.api.releases)
        self.assertNotIn('2026.11.10', self.api.tags)
        self.assertEqual(sum(w[1] == '/git/refs' for w in self.api.writes), 1)

    def test_lost_draft_reply_stops_then_resumes(self):
        self.api.fail = ('POST', '/releases', 'after')
        with self.assertRaisesRegex(RuntimeError, 'draft creation'):
            self.run_publish()
        self.assertEqual(len(self.api.writes), 2)
        self.api.fail = None
        self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertEqual(sum(w[1] == '/releases' for w in self.api.writes), 1)
        self.assertEqual(set(self.api.tags), {'2026.11.09'})

    def test_upload_unknown_never_continues_writes_and_resume_skips_exact_asset(self):
        name = 'section11-2026.11.09.zip'
        self.api.fail = ('UPLOAD', name, 'after')
        with self.assertRaisesRegex(RuntimeError, 'upload failed/unknown'):
            self.run_publish()
        self.assertEqual(len(self.api.writes), 3)
        self.api.fail = None
        self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertEqual(sum(w[:2] == ('UPLOAD', name) for w in self.api.writes), 1)

    def test_uncertain_publication_stops_then_read_only_noop_confirms_latest(self):
        self.api.fail = ('PATCH', '/releases/1', 'after')
        with self.assertRaisesRegex(RuntimeError, 'publication failed/unknown'):
            self.run_publish()
        before = list(self.api.writes)
        self.api.fail = None
        self.assertEqual(self.run_publish('2026.11.10'), 'unchanged')
        self.assertEqual(self.api.writes, before)

    def test_latest_immediate_delayed_mismatch_and_published_rerun(self):
        release = self.api.seed('2026.11.09', self.commit, self.raw, self.files)
        for reads in ([release], [P.APIError(404, 'not yet'), dict(release, id=99), release]):
            self.api.latest_reads = reads
            P.confirm_latest(self.api, release)
        self.api.latest_reads = [release] + [dict(release, tag_name='2026.11.08')] * 10
        with self.assertRaisesRegex(RuntimeError, 'only rechecks'):
            self.run_publish('2026.11.10')
        self.assertEqual(self.api.writes, [])
        self.assertEqual(self.run_publish('2026.11.10'), 'unchanged')
        self.assertEqual(self.api.writes, [])

    def test_latest_wrong_id_unpublished_and_prerelease_are_not_confirmation(self):
        release = self.api.seed('2026.11.09', self.commit, self.raw, self.files)
        for change in ({'id': 99}, {'published_at': None}, {'draft': True}, {'prerelease': True}):
            self.api.latest_reads = [dict(release, **change)] * 10
            with self.assertRaisesRegex(RuntimeError, 'not confirmed latest'):
                P.confirm_latest(self.api, release)

    def test_foreign_draft_or_tag_and_future_latest_stop(self):
        self.previous(draft=True)
        with self.assertRaisesRegex(ValueError, 'collision.*' + 'a' * 40):
            self.run_publish()
        self.api.releases.clear()
        with self.assertRaisesRegex(ValueError, 'collision.*' + 'a' * 40):
            self.run_publish()
        self.api.tags.clear()
        self.previous('2026.11.10')
        with self.assertRaisesRegex(ValueError, 'ahead'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_same_complete_tag_different_manifest_and_multiple_source_tags_stop(self):
        self.api.seed('2026.11.09', self.commit, self.raw, self.files)
        self.files = dict(self.files, LICENSE=b'changed')
        self.raw = manifest(self.files)
        with self.assertRaisesRegex(ValueError, 'different manifest'):
            self.run_publish()
        self.api.tags['2026.11.09-2'] = self.commit
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_starter_deleted_once_exact_draft_only(self):
        draft = self.api.seed('2026.11.09', self.commit, self.raw, self.files, draft=True)
        self.api.store_asset(draft['id'], 'section11-2026.11.09.zip', b'', 'starter')
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(sum(w[0] == 'DELETE' for w in self.api.writes), 1)

    def test_changed_nonempty_draft_asset_never_deleted_or_overwritten(self):
        draft = self.api.seed('2026.11.09', self.commit, self.raw, self.files, draft=True)
        self.api.store_asset(draft['id'], 'section11-2026.11.09.zip', b'bad', 'starter')
        with self.assertRaisesRegex(ValueError, 'never overwrite'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_starter_delete_unknown_stops_before_upload(self):
        draft = self.api.seed('2026.11.09', self.commit, self.raw, self.files, draft=True)
        asset = self.api.store_asset(draft['id'], 'section11-2026.11.09.zip', b'', 'starter')
        self.api.fail = ('DELETE', '/releases/assets/' + str(asset), 'after')
        with self.assertRaisesRegex(RuntimeError, 'lost write'):
            self.run_publish()
        self.assertEqual(len(self.api.writes), 1)
        self.api.fail = None
        self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertEqual(sum(w[0] == 'DELETE' for w in self.api.writes), 1)

    def test_stale_same_day_tag_read_conflicts_then_reads_back_without_more_writes(self):
        self.api.tags['2026.11.09'] = self.commit
        real_get = self.api.get
        hidden = [False]
        def stale_get(path, **kwargs):
            if path.startswith('/git/matching-refs/tags/'):
                return []
            if path == '/git/ref/tags/2026.11.09' and not hidden[0]:
                hidden[0] = True
                raise P.APIError(404, 'synthetic stale read')
            return real_get(path, **kwargs)
        output = io.StringIO()
        with mock.patch.object(self.api, 'get', stale_get), contextlib.redirect_stdout(output), \
                self.assertRaisesRegex(RuntimeError, 'tag creation'):
            self.run_publish()
        self.assertEqual(self.api.releases, {})
        self.assertEqual(len(self.api.writes), 1)
        self.assertIn('tag=' + self.commit, output.getvalue())
        self.assertEqual(set(self.api.tags), {'2026.11.09'})
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(self.api.latest, '2026.11.09')

    def test_stale_previous_day_tag_can_leave_unused_tag_but_publishes_exact_source(self):
        self.api.tags['2026.11.09'] = self.commit
        real_get = self.api.get
        def stale_get(path, **kwargs):
            if path == '/git/matching-refs/tags/2026.11.09?per_page=100&page=1':
                return []
            return real_get(path, **kwargs)
        with mock.patch.object(self.api, 'get', stale_get):
            self.assertEqual(self.run_publish('2026.11.10'), 'published')
        self.assertEqual(self.api.tags, {'2026.11.09': self.commit, '2026.11.10': self.commit})
        self.assertNotIn('2026.11.09', self.api.releases)
        self.assertEqual(self.api.releases['2026.11.10']['target_commitish'], self.commit)
        self.assertEqual({a['name']: a['data'] for a in self.api.assets.values()},
                         P.build(self.raw, self.files, self.commit, '2026.11.10'))

    def test_draft_body_source_must_match_its_tag(self):
        self.api.seed('2026.11.09', self.commit, self.raw, self.files, draft=True)
        self.api.tags['2026.11.09'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'tag source ' + 'f' * 40):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_failed_tag_write_leaves_no_identity_and_next_same_day_dispatch_reuses_name(self):
        self.previous()
        self.api.fail = ('POST', '/git/refs', 'before')
        with self.assertRaisesRegex(RuntimeError, 'tag creation'):
            self.run_publish()
        self.assertEqual(len(self.api.writes), 1)
        self.api.fail = None
        self.assertNotIn('2026.11.09-2', self.api.tags)
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(self.api.latest, '2026.11.09-2')

    def test_tag_moved_while_reading_previous_source_stops(self):
        self.previous()
        original = self.api.manifest_at
        def moved(commit):
            value = original(commit)
            self.api.tags['2026.11.09'] = 'f' * 40
            return value
        with mock.patch.object(self.api, 'manifest_at', moved), self.assertRaisesRegex(ValueError, 'tag moved'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_tag_moved_before_publish_stops_with_draft_retained(self):
        def move_on_second_gate(api, commit):
            if self.api.releases:
                self.api.tags['2026.11.09'] = 'f' * 40
        with mock.patch.object(P, 'workflow_gate', side_effect=move_on_second_gate), \
                self.assertRaisesRegex(ValueError, 'tag moved before publish'):
            self.run_publish()
        self.assertTrue(self.api.releases['2026.11.09']['draft'])
        self.assertFalse(any(w[0] == 'PATCH' for w in self.api.writes))

    def test_latest_wait_stops_at_elapsed_budget(self):
        release = self.api.seed('2026.11.09', self.commit, self.raw, self.files)
        self.api.latest_reads = [dict(release, id=99)] * 10
        clock = [0.0]
        original = self.api.get
        def slow_get(path, **kwargs):
            clock[0] += 3
            return original(path, **kwargs)
        def wait(seconds):
            clock[0] += seconds
        with mock.patch.object(P.time, 'monotonic', lambda: clock[0]), \
                mock.patch.object(P.time, 'sleep', wait), mock.patch.object(self.api, 'get', slow_get), \
                self.assertRaisesRegex(RuntimeError, 'not confirmed latest'):
            P.confirm_latest(self.api, release)
        self.assertEqual(clock[0], 30)
        self.assertEqual(sum(c[0] == 'GET' for c in self.api.calls), 5)

    def test_duplicate_release_rows_and_missing_tag_refuse_all_writes(self):
        previous = self.previous()
        original = self.api.get
        with mock.patch.object(self.api, 'get', lambda p, **kw: [previous, previous]
                               if p == '/releases?per_page=100&page=1' else original(p, **kw)), \
                self.assertRaisesRegex(ValueError, 'collision'):
            self.run_publish()
        self.api.tags.clear()
        with self.assertRaises(P.APIError):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_unchanged_pending_identity_and_older_source_stay_noops(self):
        self.api.seed('2026.11.08', 'a' * 40, self.raw, self.files)
        self.api.tags['2026.11.09'] = self.commit
        self.assertEqual(self.run_publish(), 'unchanged')
        self.assertEqual(self.api.writes, [])
        self.assertEqual(set(self.api.releases), {'2026.11.08'})
        self.api.seed('2026.11.09', self.commit, self.raw, self.files)
        self.api.seed('2026.11.09-2', 'c' * 40, self.raw, self.files)
        self.assertEqual(self.run_publish(), 'unchanged')
        self.assertEqual(self.api.writes, [])

    def test_latest_missing_its_tag_stops_before_allocation(self):
        latest = self.previous()
        self.api.latest_reads = [dict(latest, tag_name='2026.11.09-10')]
        with self.assertRaises(P.APIError):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_draft_on_first_page_resumes_beyond_previous_day(self):
        self.api.seed('2026.11.01', self.commit, self.raw, self.files, draft=True)
        self.assertEqual(self.run_publish(), 'published')
        self.assertEqual(set(self.api.tags), {'2026.11.01'})

    def test_previous_day_foreign_tag_and_older_draft_name_the_source(self):
        self.api.tags['2026.11.08-2'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'collision.*' + 'f' * 40):
            self.run_publish()
        self.api.tags.clear()
        self.api.seed('2026.11.01', 'e' * 40, self.raw, self.files, draft=True)
        with self.assertRaisesRegex(ValueError, 'collision.*' + 'e' * 40):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_stale_latest_pointer_is_not_replaced_by_sorting_history(self):
        self.previous('2026.11.09-2')
        self.previous('2026.11.09-10')
        self.api.latest = '2026.11.09-2'
        with self.assertRaisesRegex(ValueError, 'newer than latest'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])

    def test_published_source_with_stale_pointer_only_confirms_latest(self):
        self.previous()
        target = self.api.seed('2026.11.09-2', self.commit, self.raw, self.files)
        self.api.latest = '2026.11.09'
        with self.assertRaisesRegex(RuntimeError, 'not confirmed latest'):
            self.run_publish()
        self.assertEqual(self.api.writes, [])
        self.api.latest_reads = [self.api.releases['2026.11.09'], target]
        self.assertEqual(self.run_publish(), 'unchanged')
        self.assertEqual(self.api.writes, [])

    def test_publisher_request_count_is_identical_with_5_and_500_historical_releases(self):
        counts = []
        traces = []
        for history in (5, 500):
            api = ReleaseAPI()
            old = dict(self.files, LICENSE=b'old')
            for i in range(history):
                date = (datetime(2024, 1, 1) + timedelta(days=i)).strftime('%Y.%m.%d')
                api.seed(date, format(i + 1, '040x'), manifest(old), old)
            api.seed('2026.11.09', 'a' * 40, manifest(old), old)
            api.manifests[self.commit] = self.raw
            with mock.patch.object(P, 'upload', api.upload):
                self.assertEqual(P.publish(api, self.commit, self.raw, self.files, '2026.11.09'), 'published')
            reads = [c[1] for c in api.calls if c[0] == 'GET']
            # Release/asset IDs differ with history, but endpoint count must not.
            counts.append(len(reads) + sum(w[0] != 'UPLOAD' for w in api.writes))
            traces.append([p for p in reads if '/git/' in p or '?' in p])
            self.assertEqual([p for p in reads if p.startswith('/releases?')],
                             ['/releases?per_page=100&page=1'])
            self.assertFalse(any(c[:2] in (('PAGES', '/releases'), ('PAGES', '/git/matching-refs/tags/'))
                                 for c in api.calls))
            self.assertEqual(set(api.tags) - {r['tag_name'] for r in api.releases.values()}, set())
            api.calls.clear()
            api.writes.clear()
            self.assertEqual(P.publish(api, self.commit, self.raw, self.files, '2026.11.09'), 'unchanged')
            self.assertEqual(api.writes, [])
            counts[-1] = (counts[-1], sum(c[0] == 'GET' for c in api.calls))
        self.assertEqual(counts[0], counts[1])
        self.assertLess(max(counts[0]), 32)
        self.assertEqual(traces[0], traces[1])
