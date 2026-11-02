"""Offline regression tests for conservative Bus Buddy rider-data diagnostics."""
import unittest
from rider_snapshot_safety import audit_snapshot


class SnapshotSafetyTests(unittest.TestCase):
    def setUp(self):
        self.stops = {'stops': [{'id': 'A'}, {'id': 'B'}]}

    def test_untimed_intermediate_and_looped_stop_are_not_assumed_timed(self):
        journeys = {'trips': [{'stops': [
            {'stop': 'A', 'seq': 1, 'arr': '08:00:00', 'dep': '08:00:00'},
            {'stop': 'B', 'seq': 2, 'arr': '', 'dep': ''},
            {'stop': 'A', 'seq': 3, 'arr': '08:30:00', 'dep': '08:30:00'},
        ]}]}
        result = audit_snapshot(self.stops, journeys)
        self.assertEqual(result['untimed_rows'], 1)
        self.assertEqual(result['untimed_trips'], 1)
        self.assertEqual(result['adjacent_links'], 2)
        self.assertEqual(result['fully_timed_links'], 0)
        self.assertEqual(result['loop_trips'], 1)
        self.assertEqual(result['repeated_stop_visits'], 1)
        self.assertEqual(result['duplicate_sequences'], 0)
        self.assertFalse(result['exact_departures_certified'])

    def test_complete_times_still_do_not_certify_live_arrivals(self):
        journeys = {'trips': [{'stops': [
            {'stop': 'A', 'seq': 1, 'arr': '08:00:00', 'dep': '08:00:00'},
            {'stop': 'B', 'seq': 2, 'arr': '08:10:00', 'dep': '08:10:00'},
        ]}]}
        result = audit_snapshot(self.stops, journeys)
        self.assertEqual(result['fully_timed_links'], 1)
        self.assertEqual(result['untimed_rows'], 0)
        self.assertFalse(result['live_arrivals_certified'])
        self.assertFalse(result['exact_departures_certified'])

    def test_detects_duplicate_sequence_and_unknown_stop(self):
        journeys = {'trips': [{'stops': [
            {'stop': 'A', 'seq': 1, 'arr': '', 'dep': ''},
            {'stop': 'UNKNOWN', 'seq': 1, 'arr': '', 'dep': ''},
        ]}]}
        result = audit_snapshot(self.stops, journeys)
        self.assertEqual(result['duplicate_sequences'], 1)
        self.assertEqual(result['orphan_stop_references'], 1)

    def test_partial_time_is_not_counted_as_fully_untimed(self):
        journeys = {'trips': [{'stops': [
            {'stop': 'A', 'seq': 1, 'arr': '', 'dep': '08:00:00'},
            {'stop': 'B', 'seq': 2, 'arr': '08:10:00', 'dep': ''},
        ]}]}
        result = audit_snapshot(self.stops, journeys)
        self.assertEqual(result['partially_timed_rows'], 2)
        self.assertEqual(result['untimed_rows'], 0)
        self.assertEqual(result['fully_timed_links'], 1)
        self.assertFalse(result['exact_departures_certified'])


if __name__ == '__main__':
    unittest.main()
