#!/usr/bin/env python3
"""Offline tests for the fail-closed GTFS frequency import guard."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_coast_rta import check_frequency_coverage, inspect_frequency_windows, summarize_frequency_routes


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


    def test_blank_exact_times_means_headway_not_unknown(self):
        rows = [{"trip_id":"a","start_time":"08:00:00","end_time":"09:00:00","headway_secs":"900","exact_times":""}]
        report = inspect_frequency_windows(rows, {"a"})
        self.assertEqual(report["exact_times_modes"], {"0":1})
        self.assertEqual(report["headway_secs_min"], 900)
        self.assertEqual(report["invalid_row_count"], 0)

    def test_service_day_times_past_midnight(self):
        rows = [{"trip_id":"a","start_time":"23:00:00","end_time":"25:00:00","headway_secs":"600"}]
        self.assertEqual(inspect_frequency_windows(rows, {"a"})["window_end_latest_secs"], 90000)

    def test_overlapping_headway_windows_are_reported(self):
        rows = [{"trip_id":"a","start_time":"08:00:00","end_time":"09:00:00","headway_secs":"600"},
                {"trip_id":"a","start_time":"08:30:00","end_time":"10:00:00","headway_secs":"600"}]
        self.assertEqual(inspect_frequency_windows(rows, {"a"})["overlap_count"], 1)

    def test_frequency_route_coverage_groups_without_inventing_departures(self):
        trips = {
            "t1": {"route": "Rt 14 Georgetown / Andrews", "service": "weekday"},
            "t2": {"route": "Rt 14 Georgetown / Andrews", "service": "weekend"},
            "t3": {"route": "Rt 16 Georgetown / Myrtle Beach", "service": "weekday"},
        }
        rows = [
            {"trip_id": "t1", "exact_times": ""},
            {"trip_id": "t1", "exact_times": "0"},
            {"trip_id": "t2", "exact_times": "1"},
            {"trip_id": "t3", "exact_times": "0"},
            {"trip_id": "unknown", "exact_times": "0"},
        ]
        report = summarize_frequency_routes(rows, trips)
        self.assertEqual(report["affected_routes"], 2)
        self.assertEqual(report["routes"][0]["frequency_rows"], 3)
        self.assertEqual(report["routes"][0]["unique_trip_ids"], 2)
        self.assertEqual(report["routes"][0]["service_ids"], ["weekday", "weekend"])
        self.assertEqual(report["routes"][0]["exact_times_modes"], {"0": 2, "1": 1})
        self.assertEqual(report["routes"][1]["unique_trip_ids"], 1)

    def test_frequency_route_coverage_empty(self):
        self.assertEqual(summarize_frequency_routes([], {}), {"affected_routes": 0, "routes": []})

    def test_invalid_windows_and_unknown_trip_are_reported(self):
        rows = [{"trip_id":"missing","start_time":"10:00:00","end_time":"09:00:00","headway_secs":"0"}]
        report = inspect_frequency_windows(rows, {"a"})
        self.assertEqual(report["invalid_row_count"], 1)
        self.assertEqual(report["unknown_trip_ids"], ["missing"])

if __name__ == "__main__":
    unittest.main()
