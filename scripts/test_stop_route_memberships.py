"""Offline regression tests for read-only stop/route membership drift audit."""
import unittest
from sync_coast_rta import compare_stop_route_memberships


class StopRouteMembershipTests(unittest.TestCase):
    def setUp(self):
        self.stops = [{'stop_id': x} for x in ('A', 'B', 'C')]
        self.routes = [
            {'route_id': 'r1', 'route_short_name': '1'},
            {'route_id': 'r2', 'route_short_name': '2'},
        ]
        self.trips = [
            {'trip_id': 't1', 'route_id': 'r1'},
            {'trip_id': 't2', 'route_id': 'r2'},
        ]
        self.times = [
            {'trip_id': 't1', 'stop_id': 'A'},
            {'trip_id': 't1', 'stop_id': 'B'},
            {'trip_id': 't2', 'stop_id': 'B'},
            {'trip_id': 't2', 'stop_id': 'C'},
        ]
        self.stored = [
            {'id': 'A', 'routes': ['1']},
            {'id': 'B', 'routes': ['1', '2']},
            {'id': 'C', 'routes': ['2']},
        ]

    def audit(self, **changes):
        args = dict(official_stops=self.stops, official_routes=self.routes,
                    official_trips=self.trips, official_stop_times=self.times,
                    stored_stops=self.stored)
        args.update(changes)
        return compare_stop_route_memberships(**args)

    def test_identical_memberships_are_not_changes(self):
        result = self.audit()
        self.assertEqual(result['official_route_stop_memberships'], 4)
        self.assertEqual(result['stored_route_stop_memberships'], 4)
        self.assertEqual(result['official_only_membership_count'], 0)
        self.assertEqual(result['stored_only_membership_count'], 0)
        self.assertEqual(result['unknown_stop_references'], 0)
        self.assertEqual(result['unknown_trip_references'], 0)
        self.assertFalse(result['live_arrivals_verified'])

    def test_route_change_detected_even_when_all_stop_ids_match(self):
        stored = [dict(row) for row in self.stored]
        stored[1]['routes'] = ['1']
        result = self.audit(stored_stops=stored)
        self.assertEqual(result['official_only_membership_count'], 1)
        self.assertEqual(result['official_only_membership_examples'],
                         [{'stop_id': 'B', 'route': '2'}])
        self.assertEqual(result['stored_only_membership_count'], 0)

    def test_stale_route_removed_from_official_stop(self):
        stored = [dict(row) for row in self.stored]
        stored[0]['routes'] = ['1', '99']
        result = self.audit(stored_stops=stored)
        self.assertEqual(result['stored_only_membership_examples'],
                         [{'stop_id': 'A', 'route': '99'}])

    def test_unknown_stop_and_trip_are_not_counted_as_valid_routes(self):
        times = self.times + [
            {'trip_id': 't1', 'stop_id': 'MISSING'},
            {'trip_id': 'ghost', 'stop_id': 'A'},
        ]
        result = self.audit(official_stop_times=times)
        self.assertEqual(result['unknown_stop_references'], 1)
        self.assertEqual(result['unknown_trip_references'], 1)
        self.assertEqual(result['official_only_membership_count'], 0)

    def test_unknown_route_id_is_reported_not_invented(self):
        trips = self.trips + [{'trip_id': 't3', 'route_id': 'missing-route'}]
        times = self.times + [{'trip_id': 't3', 'stop_id': 'A'}]
        result = self.audit(official_trips=trips, official_stop_times=times)
        self.assertEqual(result['unknown_route_references'], 1)
        self.assertEqual(result['official_only_membership_count'], 0)

    def test_duplicate_stop_visits_do_not_inflate_membership(self):
        result = self.audit(official_stop_times=self.times + [self.times[0]])
        self.assertEqual(result['official_route_stop_memberships'], 4)
        self.assertEqual(result['official_only_membership_count'], 0)

    def test_empty_route_list_and_missing_stop_are_diagnostic_not_physical(self):
        stored = [dict(row) for row in self.stored if row['id'] != 'C']
        stored[1]['routes'] = []
        result = self.audit(stored_stops=stored)
        self.assertEqual(result['official_only_membership_count'], 2)
        self.assertEqual(result['official_stop_ids_missing_from_snapshot'], ['C'])
        self.assertFalse(result['safe_walking_routes_verified'])


if __name__ == '__main__':
    unittest.main()
