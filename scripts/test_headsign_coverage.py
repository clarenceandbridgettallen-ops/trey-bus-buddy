"""Synthetic offline cases for official/stored trip-headsign comparison."""
import unittest
from headsign_coverage import compare_headsign_coverage


def official(tid="A", sign="Georgetown"):
    return {"trip_id": tid, "trip_headsign": sign}


def stored(tid="A", sign="Georgetown"):
    return {"id": tid, "headsign": sign}


class HeadsignCoverageTests(unittest.TestCase):
    def test_matching_label_not_a_physical_sign_claim(self):
        r = compare_headsign_coverage([official()], [stored()])
        self.assertEqual(r["changed_headsign_count"], 0)
        self.assertFalse(r["vehicle_destination_signs_verified"])

    def test_changed_label_is_detected(self):
        r = compare_headsign_coverage([official(sign="Conway")], [stored()])
        self.assertEqual(r["changed_headsign_trip_examples"], ["A"])

    def test_official_filled_stored_blank_is_detected(self):
        r = compare_headsign_coverage([official()], [stored(sign="")])
        self.assertEqual(r["official_filled_stored_blank_count"], 1)
        self.assertEqual(r["stored_blank_headsign_count"], 1)

    def test_both_blank_still_report_missing_sign_evidence(self):
        r = compare_headsign_coverage([official(sign="")], [stored(sign=" ")])
        self.assertEqual(r["changed_headsign_count"], 0)
        self.assertEqual(r["official_blank_headsign_count"], 1)
        self.assertFalse(r["safe_boarding_side_verified"])

    def test_missing_trip_ids_are_not_silently_ignored(self):
        r = compare_headsign_coverage([official("A")], [stored("B")])
        self.assertEqual(r["official_only_trip_count"], 1)
        self.assertEqual(r["stored_only_trip_count"], 1)

    def test_whitespace_normalization_avoids_false_changes(self):
        r = compare_headsign_coverage([official(sign="Georgetown   Terminal")], [stored(sign="Georgetown Terminal")])
        self.assertEqual(r["changed_headsign_count"], 0)

    def test_duplicate_and_malformed_rows_are_reported(self):
        r = compare_headsign_coverage([official(), official(), None, {}], [stored(), stored()])
        self.assertEqual(r["official_duplicate_trip_count"], 1)
        self.assertEqual(r["stored_duplicate_trip_count"], 1)
        self.assertEqual(r["official_malformed_trip_rows"], 2)


if __name__ == "__main__":
    unittest.main()
