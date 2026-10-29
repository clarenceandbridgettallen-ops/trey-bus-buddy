#!/usr/bin/env python3
"""Offline tests for the fail-closed GTFS frequency import guard."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_coast_rta import check_frequency_coverage


class FrequencyCoverageTests(unittest.TestCase):
    def test_absent_frequency_file_is_explicitly_reported(self):
        self.assertEqual(
            check_frequency_coverage(False, [], {"trip-a"}),
            {"file_present": False, "row_count": 0, "status": "absent"},
        )

    def test_header_only_frequency_file_is_safe(self):
        self.assertEqual(
            check_frequency_coverage(True, [], {"trip-a"}),
            {"file_present": True, "row_count": 0, "status": "empty"},
        )

    def test_exact_schedule_frequency_is_not_misread_as_one_trip(self):
        with self.assertRaisesRegex(RuntimeError, "Refusing to replace"):
            check_frequency_coverage(True, [
                {"trip_id": "trip-a", "headway_secs": "600", "exact_times": "1"}
            ], {"trip-a"})

    def test_headway_only_frequency_is_not_given_fabricated_departures(self):
        with self.assertRaisesRegex(RuntimeError, "exact_times=0"):
            check_frequency_coverage(True, [
                {"trip_id": "trip-a", "headway_secs": "900", "exact_times": "0"}
            ], {"trip-a"})

    def test_unknown_frequency_trip_is_not_silently_ignored(self):
        with self.assertRaisesRegex(RuntimeError, "0 known trip IDs"):
            check_frequency_coverage(True, [
                {"trip_id": "unknown-trip", "headway_secs": "600"}
            ], {"trip-a"})


if __name__ == "__main__":
    unittest.main()
