import unittest
from gtfs_transfer_coverage import audit_gtfs_transfers


class TransferCoverageTests(unittest.TestCase):
    def setUp(self):
        self.stops = [{'stop_id': 'A'}, {'stop_id': 'B'}]
        self.routes = [{'route_id': 'R1'}, {'route_id': 'R2'}]
        self.trips = [{'trip_id': 'T1', 'route_id': 'R1'},
                      {'trip_id': 'T2', 'route_id': 'R2'}]

    def check(self, rows, **kw):
        return audit_gtfs_transfers(rows, self.stops, self.routes, self.trips, **kw)

    def test_empty_feed_is_not_accessibility_proof(self):
        r = self.check([], file_present=False)
        self.assertEqual(r['transfer_rows'], 0)
        self.assertFalse(r['safe_pedestrian_connection_verified'])
        self.assertFalse(r['timed_transfer_guaranteed'])

    def test_recommended_and_timed_do_not_guarantee(self):
        r = self.check([{'from_stop_id': 'A', 'to_stop_id': 'B', 'transfer_type': '0'},
                        {'from_stop_id': 'B', 'to_stop_id': 'A', 'transfer_type': '1'}])
        self.assertEqual(r['cross_stop_rules'], 2)
        self.assertEqual(r['transfer_type_counts'], {'0': 1, '1': 1})
        self.assertFalse(r['timed_transfer_guaranteed'])

    def test_blank_type_is_recommended(self):
        self.assertEqual(self.check([{'from_stop_id': 'A', 'to_stop_id': 'B'}])['transfer_type_counts'], {'0': 1})

    def test_type_two_requires_nonnegative_integer(self):
        rows = [{'from_stop_id': 'A', 'to_stop_id': 'B', 'transfer_type': '2'},
                {'from_stop_id': 'A', 'to_stop_id': 'A', 'transfer_type': '2', 'min_transfer_time': '-1'},
                {'from_stop_id': 'B', 'to_stop_id': 'A', 'transfer_type': '2', 'min_transfer_time': '240'}]
        r = self.check(rows)
        self.assertEqual(r['issue_counts']['missing_required_min_transfer_time'], 1)
        self.assertEqual(r['issue_counts']['invalid_min_transfer_time'], 1)
        self.assertEqual(r['min_transfer_time_seconds_max'], 240)

    def test_type_three_forbidden_recorded(self):
        r = self.check([{'from_stop_id': 'A', 'to_stop_id': 'B', 'transfer_type': '3'}])
        self.assertEqual(r['transfer_type_counts']['3'], 1)
        self.assertFalse(r['safe_pedestrian_connection_verified'])

    def test_linked_trip_rules_require_both_trips(self):
        r = self.check([{'transfer_type': '4', 'from_trip_id': 'T1'},
                        {'transfer_type': '5', 'from_trip_id': 'T1', 'to_trip_id': 'T2'}])
        self.assertEqual(r['issue_counts']['missing_linked_trip'], 1)
        self.assertNotIn('missing_transfer_stop', r['issue_counts'])

    def test_unknown_refs_and_mismatched_route(self):
        r = self.check([{'from_stop_id': 'X', 'to_stop_id': 'A',
                         'from_trip_id': 'T1', 'from_route_id': 'R2',
                         'to_trip_id': 'Z', 'to_route_id': 'R3'}])
        self.assertEqual(r['issue_counts']['unknown_stop_reference'], 1)
        self.assertEqual(r['issue_counts']['unknown_trip_reference'], 1)
        self.assertEqual(r['issue_counts']['unknown_route_reference'], 1)
        self.assertEqual(r['issue_counts']['trip_route_mismatch'], 1)

    def test_duplicate_directional_rule_detected(self):
        row = {'from_stop_id': 'A', 'to_stop_id': 'B', 'transfer_type': '0'}
        r = self.check([row, dict(row), {'from_stop_id': 'B', 'to_stop_id': 'A'}])
        self.assertEqual(r['issue_counts']['duplicate_rule_key'], 1)
        self.assertEqual(r['cross_stop_rules'], 3)

    def test_invalid_type_and_malformed_row_fail_diagnostic(self):
        r = self.check([None, {'from_stop_id': 'A', 'to_stop_id': 'B', 'transfer_type': '99'}])
        self.assertEqual(r['issue_counts']['malformed_row'], 1)
        self.assertEqual(r['issue_counts']['invalid_transfer_type'], 1)

    def test_stop_only_rules_require_both_stops(self):
        r = self.check([{'from_stop_id': 'A', 'transfer_type': '0'}])
        self.assertEqual(r['issue_counts']['missing_transfer_stop'], 1)

    def test_issues_are_bounded(self):
        r = self.check([None] * 100)
        self.assertEqual(r['issue_counts']['malformed_row'], 100)
        self.assertEqual(len(r['issue_examples']), 12)

if __name__ == '__main__': unittest.main()
