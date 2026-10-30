#!/usr/bin/env python3
"""Offline tests for the fail-closed GTFS frequency import guard."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_coast_rta import check_frequency_coverage, inspect_frequency_windows, summarize_frequency_routes, inspect_frequency_templates, compare_stop_inventory, inspect_stop_record_integrity, audit_boarding_permissions


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

    def test_nested_frequency_windows_report_all_overlapping_pairs(self):
        # The first interval contains both later windows, which do not overlap each other.
        rows = [
            {"trip_id": "a", "start_time": "08:00:00", "end_time": "12:00:00", "headway_secs": "900"},
            {"trip_id": "a", "start_time": "09:00:00", "end_time": "10:00:00", "headway_secs": "900"},
            {"trip_id": "a", "start_time": "10:00:00", "end_time": "11:00:00", "headway_secs": "900"},
        ]
        report = inspect_frequency_windows(rows, {"a"})
        self.assertEqual(report["overlap_count"], 2)
        self.assertEqual(report["overlapping_trip_windows"], [["a", 1, 2], ["a", 1, 3]])

    def test_touching_frequency_windows_are_not_overlap(self):
        rows = [
            {"trip_id": "a", "start_time": "08:00:00", "end_time": "09:00:00", "headway_secs": "900"},
            {"trip_id": "a", "start_time": "09:00:00", "end_time": "10:00:00", "headway_secs": "900"},
        ]
        self.assertEqual(inspect_frequency_windows(rows, {"a"})["overlap_count"], 0)

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

    def test_frequency_template_audit_reports_missing_anchors_and_calendar(self):
        rows = [{"trip_id": "a"}, {"trip_id": "b"}, {"trip_id": "unknown"}]
        trips = {"a": {"service": "weekday"}, "b": {"service": "missing"}}
        times = [
            {"trip_id": "a", "stop_sequence": "1", "arrival_time": "", "departure_time": ""},
            {"trip_id": "a", "stop_sequence": "2", "arrival_time": "08:30:00", "departure_time": "08:30:00"},
            {"trip_id": "b", "stop_sequence": "1", "arrival_time": "", "departure_time": ""},
            {"trip_id": "b", "stop_sequence": "2", "arrival_time": "", "departure_time": ""},
        ]
        report = inspect_frequency_templates(rows, trips, times, [{"service_id": "weekday"}], [])
        self.assertEqual(report["known_frequency_trip_templates"], 2)
        self.assertEqual(report["fewer_than_two_stops"]["count"], 0)
        self.assertEqual(report["missing_first_stop_time"]["count"], 2)
        self.assertEqual(report["all_stop_times_blank"]["example_trip_ids"], ["b"])
        self.assertEqual(report["unresolved_calendar_service"]["example_trip_ids"], ["b"])

    def test_official_stop_inventory_reports_changes_without_inventing_stops(self):
        official = [
            {"stop_id": "A", "stop_name": "New A", "stop_lat": "33.7", "stop_lon": "-79.0"},
            {"stop_id": "B", "stop_name": "B", "stop_lat": "33.8", "stop_lon": "-79.0"},
            {"stop_id": "D", "stop_name": "D", "stop_lat": "33.9", "stop_lon": "-79.0"},
            {"stop_id": "invalid", "stop_lat": "unknown", "stop_lon": "-79.0"},
        ]
        stored = [
            {"id": "A", "name": "Old A", "lat": 33.7, "lon": -79.0},
            {"id": "B", "name": "B", "lat": 33.802, "lon": -79.0},
            {"id": "C", "name": "C", "lat": 33.9, "lon": -79.0},
        ]
        report = compare_stop_inventory(official, stored)
        self.assertEqual(report["official_valid_stop_ids"], 3)
        self.assertEqual(report["stored_valid_stop_ids"], 3)
        self.assertEqual(report["new_in_official_feed_ids"], ["D"])
        self.assertEqual(report["not_in_official_feed_ids"], ["C"])
        self.assertEqual(report["coordinate_changes_over_100m_count"], 1)
        self.assertEqual(report["coordinate_changes_over_100m"][0]["id"], "B")
        self.assertEqual(report["name_changes"][0]["id"], "A")

    def test_unchanged_stop_inventory_has_no_false_changes(self):
        official = [{"stop_id": "A", "stop_name": "A", "stop_lat": "33.7", "stop_lon": "-79.0"}]
        stored = [{"id": "A", "name": "A", "lat": 33.7, "lon": -79.0}]
        report = compare_stop_inventory(official, stored)
        self.assertEqual(report["new_in_official_feed_count"], 0)
        self.assertEqual(report["not_in_official_feed_count"], 0)
        self.assertEqual(report["coordinate_changes_over_100m_count"], 0)
        self.assertEqual(report["name_changes_count"], 0)

    def test_small_stop_coordinate_shift_is_visible_to_safety_audit(self):
        # Roughly 22 meters north. This may change the correct crossing or boarding side.
        official = [{"stop_id": "A", "stop_name": "A", "stop_lat": "33.7002", "stop_lon": "-79.0"}]
        stored = [{"id": "A", "name": "A", "lat": 33.7, "lon": -79.0}]
        report = compare_stop_inventory(official, stored)
        self.assertEqual(report["coordinate_changes_over_10m_count"], 1)
        self.assertEqual(report["coordinate_changes_over_100m_count"], 0)
        self.assertEqual(report["coordinate_changes_over_10m"][0]["id"], "A")

    def test_identical_stop_coordinates_have_no_shift_warning(self):
        official = [{"stop_id": "A", "stop_name": "A", "stop_lat": "33.7", "stop_lon": "-79.0"}]
        stored = [{"id": "A", "name": "A", "lat": 33.7, "lon": -79.0}]
        report = compare_stop_inventory(official, stored)
        self.assertEqual(report["coordinate_changes_over_10m_count"], 0)

    def test_frequency_template_audit_describes_first_timed_stop_without_guessing_departure(self):
        report = inspect_frequency_templates(
            [{"trip_id": "a"}],
            {"a": {"route": "Rt 14 Georgetown / Andrews", "service": "weekday"}},
            [
                {"trip_id": "a", "stop_sequence": "1", "stop_id": "S1",
                 "arrival_time": "", "departure_time": "", "pickup_type": "1", "timepoint": "0"},
                {"trip_id": "a", "stop_sequence": "2", "stop_id": "S2",
                 "arrival_time": "", "departure_time": ""},
                {"trip_id": "a", "stop_sequence": "3", "stop_id": "S3",
                 "arrival_time": "09:10:00", "departure_time": "09:12:00"},
            ],
            [{"service_id": "weekday"}], [],
        )
        self.assertEqual(report["missing_first_stop_time"]["count"], 1)
        detail = report["missing_first_stop_details"][0]
        self.assertEqual(detail["trip_id"], "a")
        self.assertEqual(detail["first_stop_id"], "S1")
        self.assertEqual(detail["first_stop_pickup_type"], "1")
        self.assertEqual(detail["first_stop_timepoint"], "0")
        self.assertEqual(detail["leading_untimed_stops"], 2)
        self.assertEqual(detail["first_timed_stop_id"], "S3")
        self.assertEqual(detail["first_timed_stop_time"], "09:12:00")
        self.assertEqual(detail["route"], "Rt 14 Georgetown / Andrews")

    def test_frequency_template_audit_entirely_untimed_has_no_invented_anchor(self):
        report = inspect_frequency_templates(
            [{"trip_id": "b"}], {"b": {"route": "Rt 3", "service": "s"}},
            [{"trip_id": "b", "stop_sequence": "1", "stop_id": "X",
              "arrival_time": "", "departure_time": ""},
             {"trip_id": "b", "stop_sequence": "2", "stop_id": "Y",
              "arrival_time": "", "departure_time": ""}],
            [{"service_id": "s"}], [],
        )
        detail = report["missing_first_stop_details"][0]
        self.assertEqual(detail["leading_untimed_stops"], 2)
        self.assertEqual(detail["first_timed_stop_id"], "")
        self.assertEqual(detail["first_timed_stop_time"], "")
        self.assertEqual(report["all_stop_times_blank"]["count"], 1)

    def test_frequency_template_audit_accepts_exception_only_service(self):
        rows = [{"trip_id": "a"}]
        trips = {"a": {"service": "holiday"}}
        times = [
            {"trip_id": "a", "stop_sequence": "2", "arrival_time": "09:00:00", "departure_time": "09:00:00"},
            {"trip_id": "a", "stop_sequence": "1", "arrival_time": "08:00:00", "departure_time": "08:00:00"},
        ]
        report = inspect_frequency_templates(rows, trips, times, [], [{"service_id": "holiday"}])
        self.assertEqual(report["missing_first_stop_time"]["count"], 0)
        self.assertEqual(report["all_stop_times_blank"]["count"], 0)
        self.assertEqual(report["unresolved_calendar_service"]["count"], 0)

    def test_invalid_windows_and_unknown_trip_are_reported(self):
        rows = [{"trip_id":"missing","start_time":"10:00:00","end_time":"09:00:00","headway_secs":"0"}]
        report = inspect_frequency_windows(rows, {"a"})
        self.assertEqual(report["invalid_row_count"], 1)
        self.assertEqual(report["unknown_trip_ids"], ["missing"])

    def test_duplicate_stop_ids_are_visible_even_when_unique_count_matches(self):
        official = [
            {"stop_id":"TL-1","stop_lat":"33.7","stop_lon":"-79.0"},
            {"stop_id":"TL-1","stop_lat":"33.8","stop_lon":"-79.1"},
            {"stop_id":"TL-2","stop_lat":"33.9","stop_lon":"-79.0"},
        ]
        report = inspect_stop_record_integrity(official)
        self.assertEqual(report["raw_rows"],3)
        self.assertEqual(report["distinct_nonempty_ids"],2)
        self.assertEqual(report["duplicate_id_count"],1)
        self.assertEqual(report["duplicate_ids"],["TL-1"])

    def test_missing_stop_ids_and_unusable_coordinates_are_not_hidden(self):
        official = [
            {"stop_id":"","stop_lat":"33.7","stop_lon":"-79.0"},
            {"stop_id":"TL-2","stop_lat":"nan","stop_lon":"-79.0"},
            {"stop_id":"TL-3","stop_lat":"91","stop_lon":"-79.0"},
            {"stop_id":"TL-4","stop_lat":"33.7","stop_lon":"-79.0"},
        ]
        report = inspect_stop_record_integrity(official)
        self.assertEqual(report["missing_id_rows"],1)
        self.assertEqual(report["unusable_coordinate_rows"],2)
        self.assertEqual([x["id"] for x in report["unusable_coordinate_examples"]],["TL-2","TL-3"])

    def test_stored_stop_integrity_uses_stored_field_names(self):
        stored = [{"id":"TL-1","lat":33.7,"lon":-79.0},
                  {"id":"TL-2","lat":33.8,"lon":-79.1}]
        report = inspect_stop_record_integrity(stored,official=False)
        self.assertEqual(report["distinct_nonempty_ids"],2)
        self.assertEqual(report["missing_id_rows"],0)
        self.assertEqual(report["duplicate_id_count"],0)
        self.assertEqual(report["unusable_coordinate_rows"],0)

if __name__ == "__main__":
    unittest.main()


class BoardingPermissionAuditTests(unittest.TestCase):
    def test_blank_types_are_regular_and_do_not_claim_accessibility(self):
        rows = [{'trip_id':'T', 'stop_sequence':'1', 'stop_id':'A'}]
        stored = [{'id':'T', 'stops':[{'seq':1,'stop':'A'}]}]
        result = audit_boarding_permissions(rows, stored)
        self.assertEqual(result['pickup_codes'], {'0':1})
        self.assertEqual(result['drop_off_codes'], {'0':1})
        self.assertEqual(result['rows_with_any_restriction'], 0)
        self.assertFalse(result['safe_boarding_side_verified'])

    def test_restricted_boarding_and_alighting_missing_from_snapshot(self):
        rows = [
            {'trip_id':'T', 'stop_sequence':'1', 'stop_id':'A',
             'pickup_type':'1', 'drop_off_type':'0'},
            {'trip_id':'T', 'stop_sequence':'2', 'stop_id':'B',
             'pickup_type':'2', 'drop_off_type':'3'},
        ]
        stored = [{'id':'T','stops':[{'seq':1,'stop':'A'},
                                    {'seq':2,'stop':'B'}]}]
        result = audit_boarding_permissions(rows, stored)
        self.assertEqual(result['rows_with_any_restriction'], 2)
        self.assertEqual(result['pickup_codes'], {'1':1,'2':1})
        self.assertEqual(result['drop_off_codes'], {'0':1,'3':1})
        self.assertEqual(result['restricted_fields_not_represented_in_snapshot'], 3)
        self.assertEqual(result['restricted_fields_missing_matching_snapshot_row'], 0)
        self.assertEqual(len(result['restricted_examples']), 3)

    def test_missing_snapshot_row_and_unknown_code_are_visible(self):
        rows = [{'trip_id':'T','stop_sequence':'5','stop_id':'Z',
                 'pickup_type':'unknown','drop_off_type':'1'}]
        result = audit_boarding_permissions(rows, [])
        self.assertEqual(result['rows_with_any_restriction'], 1)
        self.assertEqual(result['restricted_fields_missing_matching_snapshot_row'], 2)
        self.assertEqual(result['restricted_fields_not_represented_in_snapshot'], 0)
        self.assertEqual(result['restricted_examples'][0]['stored_code'], None)

    def test_matching_explicit_permissions_are_not_flagged(self):
        rows = [{'trip_id':'T','stop_sequence':'7','stop_id':'Z',
                 'pickup_type':'1','drop_off_type':'2'}]
        stored = [{'id':'T','stops':[{'seq':7,'stop':'Z',
                                    'pickup_type':'1','drop_off_type':'2'}]}]
        result = audit_boarding_permissions(rows, stored)
        self.assertEqual(result['rows_with_any_restriction'], 1)
        self.assertEqual(result['restricted_fields_not_represented_in_snapshot'], 0)
