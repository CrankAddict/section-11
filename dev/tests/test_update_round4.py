"""B2 replaces PR polling/merge with standing policy and direct validation."""
from unittest import mock
from test_update_prototype import Offline
from test_b2_hosted import Remote, release
from direct_commit import DirectPublisher
import hosted_update as H


class AutomaticDirectTests(Offline):
    def test_full_never_substitutes_for_first_acceptance(self):
        remote = Remote({'sync.py': b'legacy'})
        pub = DirectPublisher(remote)
        controller = H.HostedUpdater(pub, lambda: release(), {'SECTION11_AUTO_UPDATE': 'true'})
        before = remote.tip
        with self.assertRaisesRegex(ValueError, 'first installation'):
            controller.install(pub.snapshot(), automatic=True)
        self.assertEqual(remote.tip, before)

    def test_no_merge_method_or_pr_setting_is_required(self):
        remote = Remote({'sync.py': b'legacy'})
        metadata = remote.metadata
        remote.metadata = lambda: dict(metadata(), allow_merge_commit=False, allow_squash_merge=False,
                                       allow_rebase_merge=False)
        pub = DirectPublisher(remote)
        H.HostedUpdater(pub, lambda: release(), {}).install(pub.snapshot(), accepted=True)
        self.assertFalse(any('/pulls' in call[1] or '/merge' in call[1] for call in remote.calls))

    def test_higher_content_holds_full_but_explicit_update_can_accept(self):
        remote = Remote({'sync.py': b'legacy'})
        pub = DirectPublisher(remote)
        H.HostedUpdater(pub, lambda: release('2026.10.29', '99.0'), {}).install(pub.snapshot(), accepted=True)
        controller = H.HostedUpdater(pub, lambda: release(), {'SECTION11_AUTO_UPDATE': 'true'})
        before = remote.tip
        with self.assertRaisesRegex(ValueError, 'higher installed'):
            controller.install(pub.snapshot(), automatic=True)
        self.assertEqual(remote.tip, before)
        controller.install(pub.snapshot(), accepted=True)
        self.assertNotEqual(remote.tip, before)

    def test_invalid_policy_claims_day_without_fetch_or_install(self):
        remote = Remote({'sync.py': b'legacy'})
        pub = DirectPublisher(remote)
        fetch = mock.Mock(return_value=release())
        controller = H.HostedUpdater(pub, fetch,
            {'SECTION11_AUTO_UPDATE': 'invalid'})
        with self.assertRaisesRegex(ValueError, 'invalid'):
            controller.maintain(pub.snapshot(), '2026.10.30', True)
        fetch.assert_not_called()
        self.assertEqual(H.control(remote.inventory()[H.CONTROL])['attempted_day'], '2026.10.30')
        self.assertEqual(remote.inventory()['sync.py'], b'legacy')

    def test_false_keeps_half_mode(self):
        for setting in ('SECTION11_AUTO_UPDATE',):
            self.assertFalse(H.policy({setting: 'false'}))
            self.assertTrue(H.policy({setting: 'true'}))
