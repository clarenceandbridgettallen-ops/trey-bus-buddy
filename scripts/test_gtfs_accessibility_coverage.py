import unittest
from gtfs_accessibility_coverage import audit_gtfs_accessibility


class AccessibilityCoverageTests(unittest.TestCase):
    def test_missing_fields_remain_unknown(self):
        r = audit_gtfs_accessibility([{"stop_id": "A"}], [{"trip_id": "T"}], [])
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["unknown"], 1)
        self.assertFalse(r["boarding_stop_wheelchair_flags"]["field_present"])
        self.assertEqual(r["trip_wheelchair_flags"]["unknown"], 1)
        self.assertFalse(r["accessible_pedestrian_path_verified"])

    def test_all_standard_flags_and_invalid_values(self):
        stops = [{"location_type": "0", "wheelchair_boarding": x} for x in ("", "0", "1", "2", "9")]
        trips = [{"wheelchair_accessible": x} for x in ("0", "1", "2", "no")]
        r = audit_gtfs_accessibility(stops, trips, ["pathways.txt", "transfers.txt"])
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["unknown"], 2)
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["accessible_flag"], 1)
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["inaccessible_flag"], 1)
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["invalid_examples"], ["9"])
        self.assertEqual(r["trip_wheelchair_flags"]["invalid_examples"], ["no"])
        self.assertTrue(r["pathways_file_present"])
        self.assertTrue(r["transfers_file_present"])
        self.assertFalse(r["boarding_side_verified"])

    def test_station_and_entrance_are_not_counted_as_boarding_stops(self):
        stops = [{"location_type": "0", "wheelchair_boarding": "1"},
                 {"location_type": "1", "wheelchair_boarding": "1"},
                 {"location_type": "2", "wheelchair_boarding": "1"}]
        r = audit_gtfs_accessibility(stops, [], ["folder/levels.txt"])
        self.assertEqual(r["official_stop_rows"], 3)
        self.assertEqual(r["boarding_stop_rows"], 1)
        self.assertEqual(r["non_boarding_location_rows"], 2)
        self.assertTrue(r["levels_file_present"])

    def test_flagged_accessible_is_not_physical_accessibility_certification(self):
        r = audit_gtfs_accessibility([{"wheelchair_boarding": "1"}],
                                     [{"wheelchair_accessible": "1"}], [])
        self.assertEqual(r["boarding_stop_wheelchair_flags"]["accessible_flag"], 1)
        self.assertFalse(r["accessible_pedestrian_path_verified"])
        self.assertFalse(r["actual_vehicle_accessibility_verified"])

    def test_empty_feed_does_not_claim_metadata_coverage(self):
        r = audit_gtfs_accessibility([], [], [])
        self.assertEqual(r["boarding_stop_rows"], 0)
        self.assertFalse(r["boarding_stop_wheelchair_flags"]["field_present"])
        self.assertFalse(r["trip_wheelchair_flags"]["field_present"])


if __name__ == "__main__":
    unittest.main()
