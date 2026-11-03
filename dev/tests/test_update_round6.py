"""B2 daily claims replace Actions/PR-history discovery."""
from unittest import mock
from test_update_prototype import Offline
from test_b2_hosted import Remote, release
from direct_commit import DirectPublisher
import hosted_update as H


class DailyDirectTests(Offline):
    def test_backup_and_data_share_claim_and_clock_regression_cannot_repeat(self):
        remote = Remote()
        pub = DirectPublisher(remote)
        updater = H.HostedUpdater(pub, lambda: release(), {})
        self.assertIsNotNone(updater.claim(pub.snapshot(), '2026.10.30'))
        before = remote.tip
        self.assertIsNone(updater.claim(pub.snapshot(), '2026.10.30'))
        self.assertIsNone(updater.claim(pub.snapshot(), '2026.10.29'))
        self.assertEqual(remote.tip, before)
        self.assertIsNotNone(updater.claim(pub.snapshot(), '2026.10.31'))

    def test_creation_day_survives_cross_midnight_delay_without_closing_hour(self):
        for instant in ('2026-10-30T04:00:00Z', '2026-10-30T14:30:00Z', '2026-10-30T23:59:59Z'):
            self.assertEqual(H.eligible_day(instant, 'schedule', True), '2026.10.30')
        self.assertIsNone(H.eligible_day('2026-10-30T03:59:59Z', 'schedule', True))

    def test_explicit_update_available_after_failed_claim_same_day(self):
        remote = Remote({'sync.py': b'old'})
        pub = DirectPublisher(remote)
        fail = mock.Mock(side_effect=ValueError('synthetic failed release'))
        controller = H.HostedUpdater(pub, fail, {})
        with self.assertRaisesRegex(ValueError, 'synthetic failed'):
            controller.maintain(pub.snapshot(), '2026.10.30', True)
        H.HostedUpdater(pub, lambda: release(), {}).install(pub.snapshot(), accepted=True)
        self.assertNotIn('sync.py', remote.inventory())
        self.assertEqual(H.control(remote.inventory()[H.CONTROL])['attempted_day'], '2026.10.30')

    def test_malformed_control_preserved_without_release_request(self):
        remote = Remote({H.CONTROL: b'{"schema":1,"secret":"synthetic"}'})
        pub = DirectPublisher(remote)
        fetch = mock.Mock(return_value=release())
        before = remote.tip
        with self.assertRaisesRegex(ValueError, 'control schema'):
            H.HostedUpdater(pub, fetch, {}).maintain(pub.snapshot(), '2026.10.30', True)
        self.assertEqual(remote.tip, before)
        fetch.assert_not_called()

    def test_new_claim_needs_no_workflow_or_pr_history(self):
        remote = Remote()
        pub = DirectPublisher(remote)
        H.HostedUpdater(pub, lambda: release(), {}).claim(pub.snapshot(), '2026.10.30')
        self.assertFalse(any('/actions/' in call[1] or '/pulls' in call[1] for call in remote.calls))

    def test_manual_on_demand_has_no_scheduled_opportunity(self):
        self.assertIsNone(H.eligible_day('2026-10-30T04:17:00Z', 'schedule', True, scheduled=False))
        self.assertIsNone(H.eligible_day('2026-10-30T00:00:00Z', 'workflow_dispatch', True,
                                       scheduled=False))
        self.assertEqual(H.eligible_day('2026-10-30T04:00:00Z', 'workflow_dispatch', False,
                                       scheduled=False), '2026.10.30')
