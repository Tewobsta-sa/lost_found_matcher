import unittest
from datetime import date

from lost_found.matcher import compare, find_matches
from lost_found.models import Report, ReportType


def lost(desc, location=None, d=None):
    return Report(ReportType.LOST, desc, location, d)


def found(desc, location=None, d=None):
    return Report(ReportType.FOUND, desc, location, d)


class TestPromptExamples(unittest.TestCase):
    def test_library_backpack_is_a_strong_match(self):
        l = lost("Black backpack containing a laptop charger. Lost around the "
                  "library on Monday afternoon.", "library", date(2026, 8, 17))
        f = found("Dark-colored backpack found near the library entrance Monday evening.",
                   "library entrance", date(2026, 8, 17))
        result = compare(l, f)
        self.assertGreaterEqual(result.score, 0.70)
        self.assertEqual(result.label, "Strong match")

    def test_football_field_two_weeks_later_scores_lower_than_library_match(self):
        l = lost("Black backpack containing a laptop charger. Lost around the "
                  "library on Monday afternoon.", "library", date(2026, 8, 17))
        f_near = found("Dark-colored backpack found near the library entrance Monday evening.",
                        "library entrance", date(2026, 8, 17))
        f_far = found("Black backpack found at the football field two weeks later.",
                       "football field", date(2026, 8, 31))
        near_result = compare(l, f_near)
        far_result = compare(l, f_far)
        self.assertLess(far_result.score, near_result.score)

    def test_airpods_case_matches_earbud_case(self):
        l = lost("I lost my black AirPods case yesterday near the cafeteria.",
                  "cafeteria", date(2026, 8, 20))
        f = found("Found a dark wireless earbud case beside the coffee shop.",
                   "coffee shop", date(2026, 8, 20))
        result = compare(l, f)
        self.assertGreaterEqual(result.score, POSSIBLE := 0.45)


class TestSignals(unittest.TestCase):
    def test_completely_unrelated_items_score_low(self):
        l = lost("Lost my brown wallet near the gym.", "gym", date(2026, 8, 1))
        f = found("Found a blue umbrella in the lecture hall.", "lecture hall", date(2026, 8, 15))
        result = compare(l, f)
        self.assertLess(result.score, 0.45)

    def test_found_before_lost_is_penalized(self):
        l = lost("Lost a black jacket near the gym.", "gym", date(2026, 8, 20))
        f = found("Found a black jacket near the gym.", "gym", date(2026, 8, 10))
        result = compare(l, f)
        self.assertLessEqual(result.breakdown["time"], 0.1)

    def test_missing_fields_are_treated_as_neutral_not_penalized(self):
        l = lost("Lost my keys.")
        f = found("Found a set of keys.")
        result = compare(l, f)
        # category matches (keys), everything else neutral -> should still
        # clear the "possible match" bar even with almost no detail.
        self.assertGreaterEqual(result.score, 0.45)

    def test_conflicting_categories_score_zero_on_that_signal(self):
        l = lost("Lost a black backpack near the library.")
        f = found("Found a blue umbrella near the library.")
        result = compare(l, f)
        self.assertEqual(result.breakdown["category"], 0.0)


class TestFindMatches(unittest.TestCase):
    def test_ranks_best_match_first_and_filters_type(self):
        target = lost("Black backpack near the library.", "library", date(2026, 8, 17))
        candidates = [
            found("Black backpack near the library entrance.", "library entrance", date(2026, 8, 17)),
            found("Black backpack at the football field.", "football field", date(2026, 9, 1)),
            lost("Another lost backpack report, should be excluded."),  # wrong type
        ]
        results = find_matches(target, candidates)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0].score, results[1].score)


class TestValidation(unittest.TestCase):
    def test_empty_description_raises(self):
        with self.assertRaises(ValueError):
            Report(ReportType.LOST, "   ")


if __name__ == "__main__":
    unittest.main()
