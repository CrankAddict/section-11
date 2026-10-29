"""Ninety-day portable cache retention, separated from fast contracts."""
import unittest
import test_hosted_cache as fixtures


class Growth(unittest.TestCase):
    setUp = fixtures.HostedCase.setUp
    new_sync = fixtures.HostedCase.new_sync
    new_runner = fixtures.HostedCase.new_runner
    produce = fixtures.HostedCase.produce
    publish = fixtures.HostedCase.publish
    seed = fixtures.HostedCase.seed
    test_ninety_day_portable_curve_windows_do_not_accumulate = fixtures.HostedCase.measure_ninety_day_portable_curve_windows_do_not_accumulate
