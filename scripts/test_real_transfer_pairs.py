import unittest
from audit_real_transfer_pairs import audit_real_transfer_pairs


def week():
    return {'service_id': 'daily', 'start_date': '20260101', 'end_date': '20261231',
            **{day: '1' for day in ('monday','tuesday','wednesday','thursday',
                                   'friday','saturday','sunday')}}


class RealPairAuditTests(unittest.TestCase):
    def setUp(self):
        self.frequencies = [
            {'trip_id': 'a', 'start_time': '08:00:00', 'end_time': '09:00:00',
             'headway_secs': '900', 'exact_times': '0'},
            {'trip_id': 'b', 'start_time': '08:30:00', 'end_time': '10:00:00',
             'headway_secs': '900', 'exact_times': '0'},
        ]
        self.trips = {'a': {'service': 'daily', 'route': 'A'},
                      'b': {'service': 'daily', 'route': 'B'}}
        self.times = [
            {'trip_id': 'a', 'stop_id': 'origin', 'stop_sequence': '1',
             'arrival_time': '08:00:00', 'departure_time': '08:00:00', 'timepoint': '1'},
            {'trip_id': 'a', 'stop_id': 'hub', 'stop_sequence': '2',
             'arrival_time': '08:15:00', 'departure_time': '08:15:00', 'timepoint': '1'},
            {'trip_id': 'b', 'stop_id': 'hub', 'stop_sequence': '1',
             'arrival_time': '08:30:00', 'departure_time': '08:30:00', 'timepoint': '1'},
            {'trip_id': 'b', 'stop_id': 'destination', 'stop_sequence': '2',
             'arrival_time': '08:45:00', 'departure_time': '08:45:00', 'timepoint': '1'},
        ]

    def audit(self, **changes):
        options = dict(frequencies=self.frequencies, trips=self.trips,
                       stop_times=self.times, calendar=[week()], exceptions=[],
                       service_date='20261029', limit=8)
        options.update(changes)
        return audit_real_transfer_pairs(**options)

    def test_same_stop_real_identifiers_not_certified_boarding(self):
        result = self.audit()
        self.assertGreaterEqual(result['sample_count'], 1)
        self.assertEqual(result['status'], 'read_only_actual_feed_sample_not_rider_navigation')
        sample = next(s for s in result['samples']
                      if s['inbound_trip_id'] == 'a' and s['outbound_trip_id'] == 'b')
        self.assertEqual(sample['stop_id'], 'hub')
        self.assertEqual(sample['inbound_stop_sequence'], 2)
        self.assertEqual(sample['outbound_stop_sequence'], 1)
        self.assertNotIn('departure_seconds', str(result))
        self.assertIn('not verify walking', result['sample_limitations'])

    def test_no_shared_stop_yields_no_candidate(self):
        times = [dict(row, stop_id='other') if row['trip_id'] == 'b' else row
                 for row in self.times]
        self.assertEqual(self.audit(stop_times=times)['sample_count'], 0)

    def test_duplicate_frequency_row_excluded_not_guessed(self):
        result = self.audit(frequencies=self.frequencies + [self.frequencies[0]])
        self.assertEqual(result['eligible_unique_frequency_trip_templates'], 1)
        self.assertEqual(result['sample_count'], 0)

    def test_approximate_timepoint_not_selected(self):
        times = [dict(row, timepoint='0') if row['stop_id'] == 'hub' else row
                 for row in self.times]
        self.assertEqual(self.audit(stop_times=times)['sample_count'], 0)

    def test_same_route_reboarding_not_called_a_transfer(self):
        trips = {tid: dict(trip, route='SAME') for tid, trip in self.trips.items()}
        self.assertEqual(self.audit(trips=trips)['sample_count'], 0)

    def test_terminal_only_meeting_not_called_transfer(self):
        # Only A's first-stop arrival and B's last-stop departure share a
        # location. Neither can establish A->B travel; clear reverse events.
        times = [
            dict(self.times[0], stop_id='terminal', departure_time=''),
            dict(self.times[1], stop_id='other-a'),
            dict(self.times[2], stop_id='other-b'),
            dict(self.times[3], stop_id='terminal', arrival_time=''),
        ]
        self.assertEqual(self.audit(stop_times=times)['sample_count'], 0)

    def test_limit_and_invalid_limit(self):
        self.assertEqual(self.audit(limit=0)['sample_count'], 0)
        with self.assertRaises(ValueError):
            self.audit(limit=-1)
        with self.assertRaises(ValueError):
            self.audit(limit=True)

    def test_inactive_service_not_reported_as_possible(self):
        result = self.audit(exceptions=[{'service_id': 'daily', 'date': '20261029',
                                        'exception_type': '2'}])
        self.assertTrue(result['samples'])
        self.assertTrue(all(s['feasibility'] == 'inactive_service_on_selected_date'
                            for s in result['samples']))


if __name__ == '__main__':
    unittest.main()
