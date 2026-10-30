"""Offline regression tests for route/direction drift diagnostics."""
import unittest
from route_direction_coverage import compare_route_direction_coverage


class RouteDirectionCoverageTests(unittest.TestCase):
    def setUp(self):
        self.routes = [
            {"route_id": "a", "route_short_name": "16"},
            {"route_id": "b", "route_short_name": "7"},
        ]
        self.trips = [
            {"trip_id": "t1", "route_id": "a", "direction_id": "0", "trip_headsign": "Georgetown"},
            {"trip_id": "t2", "route_id": "a", "direction_id": "1", "trip_headsign": "Myrtle Beach"},
            {"trip_id": "t3", "route_id": "b", "direction_id": "0", "trip_headsign": "Conway"},
        ]
        self.stored = [
            {"id": "t1", "route": "16", "direction": "0", "headsign": "Georgetown"},
            {"id": "t2", "route": "16", "direction": "1", "headsign": "Myrtle Beach"},
            {"id": "t3", "route": "7", "direction": "0", "headsign": "Conway"},
        ]

    def audit(self, **changes):
        args = dict(official_routes=self.routes, official_trips=self.trips,
                    stored_trips=self.stored)
        args.update(changes)
        return compare_route_direction_coverage(**args)

    def test_exact_snapshot_has_no_drift(self):
        r = self.audit()
        self.assertEqual(r["official_route_direction_pairs"], 3)
        self.assertEqual(r["official_only_pair_count"], 0)
        self.assertEqual(r["official_only_trip_count"], 0)
        self.assertEqual(r["shared_trip_route_direction_mismatch_count"], 0)
        self.assertFalse(r["schedule_times_verified"])

    def test_direction_reversal_detected_for_same_trip_id(self):
        stored = [dict(t) for t in self.stored]
        stored[0]["direction"] = "1"
        r = self.audit(stored_trips=stored)
        self.assertEqual(r["shared_trip_route_direction_mismatch_count"], 1)
        self.assertEqual(r["shared_trip_route_direction_mismatch_examples"][0]["trip_id"], "t1")

    def test_missing_route_direction_pair_detected(self):
        r = self.audit(stored_trips=self.stored[:1] + self.stored[2:])
        self.assertEqual(r["official_only_pair_examples"],
                         [{"route": "16", "direction_id": "1"}])
        self.assertEqual(r["official_only_trip_examples"], ["t2"])

    def test_headsign_drift_does_not_invent_new_direction(self):
        stored = [dict(t) for t in self.stored]
        stored[0]["headsign"] = "Other terminal"
        r = self.audit(stored_trips=stored)
        self.assertEqual(r["shared_trip_headsign_change_count"], 1)
        self.assertEqual(r["official_only_pair_count"], 0)

    def test_missing_direction_is_not_inferred(self):
        trips = [dict(t) for t in self.trips]
        stored = [dict(t) for t in self.stored]
        trips[0].pop("direction_id")
        stored[0]["direction"] = ""
        r = self.audit(official_trips=trips, stored_trips=stored)
        self.assertEqual(r["official_unspecified_direction_trip_count"], 1)
        self.assertEqual(r["shared_trip_route_direction_mismatch_count"], 0)

    def test_unknown_route_is_reported_and_not_invented(self):
        trips = self.trips + [{"trip_id": "ghost", "route_id": "absent"}]
        r = self.audit(official_trips=trips)
        self.assertEqual(r["unknown_official_route_references"], 1)
        self.assertEqual(r["official_only_trip_count"], 0)

    def test_duplicate_trip_ids_are_reported(self):
        r = self.audit(official_trips=self.trips + [self.trips[0]],
                       stored_trips=self.stored + [self.stored[0]])
        self.assertEqual(r["duplicate_official_trip_ids"], 1)
        self.assertEqual(r["duplicate_stored_trip_ids"], 1)
        self.assertEqual(r["official_only_pair_count"], 0)

    def test_route_relabel_detected_on_shared_trip(self):
        stored = [dict(t) for t in self.stored]
        stored[0]["route"] = "99"
        r = self.audit(stored_trips=stored)
        self.assertEqual(r["shared_trip_route_direction_mismatch_count"], 1)
        self.assertEqual(r["stored_only_pair_count"], 1)


if __name__ == "__main__":
    unittest.main()
