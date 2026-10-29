"""Day request vectors, separated from fast cache validation."""
import unittest
import test_hosted_cache as fixtures


class Days(unittest.TestCase):
    setUp = fixtures.HostedCase.setUp
    new_sync = fixtures.HostedCase.new_sync
    new_runner = fixtures.HostedCase.new_runner
    produce = fixtures.HostedCase.produce
    publish = fixtures.HostedCase.publish
    seed = fixtures.HostedCase.seed
    test_actual_hosted_day_totals_and_pending_native_savings = fixtures.HostedCase.measure_actual_hosted_day_totals_and_pending_native_savings
