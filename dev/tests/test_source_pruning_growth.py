"""Full ninety-day retention acceptance, separated from the fast regressions."""
import unittest
import test_source_pruning as checks


class LongGrowth(unittest.TestCase):
    simulate = checks.Growth.simulate
    test_ninety_day_plateau_matches_reviewed_unpruned_producer = checks.Growth.check_ninety_day_plateau_matches_reviewed_unpruned_producer


if __name__ == "__main__":
    unittest.main()
