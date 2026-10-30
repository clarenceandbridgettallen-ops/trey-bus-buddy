import unittest
from trip_transfer_diagnostic import diagnose_trip_transfer


def week(service_id='weekday'):
    return {'service_id': service_id, 'start_date': '20260101', 'end_date': '20261231',
            **{day: '1' for day in
               ('monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                'saturday', 'sunday')}}


class TripTransferDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.freq = [
            {'trip_id': 'in', 'start_time': '08:00:00', 'end_time': '09:00:00',
             'headway_secs': '900', 'exact_times': '0'},
            {'trip_id': 'out', 'start_time': '08:30:00', 'end_time': '10:00:00',
             'headway_secs': '900', 'exact_times': '0'},
        ]
        self.trips = {'in': {'service': 'weekday'}, 'out': {'service': 'weekday'}}
        self.times = [
            {'trip_id': 'in', 'stop_id': 'A', 'stop_sequence': '1',
             'arrival_time': '08:00:00', 'departure_time': '08:00:00',
             'timepoint': '1'},
            {'trip_id': 'in', 'stop_id': 'X', 'stop_sequence': '2',
             'arrival_time': '08:15:00', 'departure_time': '08:15:00',
             'timepoint': '1'},
            {'trip_id': 'out', 'stop_id': 'X', 'stop_sequence': '1',
             'arrival_time': '08:30:00', 'departure_time': '08:30:00',
             'timepoint': '1'},
            {'trip_id': 'out', 'stop_id': 'Y', 'stop_sequence': '2',
             'arrival_time': '08:45:00', 'departure_time': '08:45:00',
             'timepoint': '1'},
        ]

    def check(self, **kwargs):
        options = {
            'frequencies': self.freq, 'trips': self.trips, 'stop_times': self.times,
            'calendar': [week()], 'exceptions': [], 'service_date': '20261029',
            'inbound_trip_id': 'in', 'inbound_stop_id': 'X',
            'inbound_stop_sequence': 2, 'outbound_trip_id': 'out',
            'outbound_stop_id': 'X', 'outbound_stop_sequence': 1,
            'minimum_transfer_seconds': 300,
        }
        options.update(kwargs)
        return diagnose_trip_transfer(**options)

    def test_both_active_still_not_guaranteed(self):
        result = self.check()
        self.assertEqual(result['feasibility'], 'possible_unverified_never_guaranteed')
        self.assertFalse(result['actual_departures_verified'])
        self.assertFalse(result['safe_walking_route_verified'])
        self.assertFalse(result['live_arrivals_verified'])

    def test_exception_removes_one_leg(self):
        self.trips['out']['service'] = 'removed'
        result = self.check(calendar=[week(), week('removed')],
                            exceptions=[{'service_id': 'removed',
                                         'date': '20261029', 'exception_type': '2'}])
        self.assertEqual(result['inbound_service'], 'active')
        self.assertEqual(result['outbound_service'], 'inactive')
        self.assertEqual(result['feasibility'], 'inactive_service_on_selected_date')

    def test_conflicting_exception_fails_closed(self):
        exceptions = [
            {'service_id': 'weekday', 'date': '20261029', 'exception_type': '1'},
            {'service_id': 'weekday', 'date': '20261029', 'exception_type': '2'},
        ]
        result = self.check(exceptions=exceptions)
        self.assertEqual(result['inbound_service'], 'uncertain')
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')

    def test_missing_or_multiple_frequency_rows_not_guessed(self):
        self.assertEqual(self.check(frequencies=self.freq[:1])['reason'],
                         'missing_or_ambiguous_frequency_row')
        self.assertEqual(self.check(frequencies=self.freq + [self.freq[0]])['reason'],
                         'missing_or_ambiguous_frequency_row')

    def test_different_stop_ids_do_not_imply_a_walkable_transfer(self):
        # Overlapping headway windows cannot certify a pedestrian connection.
        result = self.check(outbound_stop_id='Y', outbound_stop_sequence=2)
        self.assertEqual(result['reason'],
                         'different_transfer_stops_no_verified_walk')
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')
        self.assertFalse(result['safe_walking_route_verified'])

    def test_missing_transfer_stop_identity_fails_closed(self):
        for inbound, outbound in [('', 'X'), ('X', ''), (None, 'X')]:
            with self.subTest(inbound=inbound, outbound=outbound):
                result = self.check(inbound_stop_id=inbound,
                                    outbound_stop_id=outbound)
                self.assertEqual(result['reason'], 'missing_transfer_stop_id')
                self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')

    def test_repeated_stop_requires_exact_sequence(self):
        duplicate = dict(self.times[1], stop_sequence='3')
        result = self.check(stop_times=self.times + [duplicate],
                            inbound_stop_sequence=None)
        self.assertEqual(result['inbound_window_status'], 'unknown_do_not_navigate')
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')

    def test_untimed_or_approximate_stop_is_not_confirmed(self):
        data = [dict(r) for r in self.times]
        data[1]['arrival_time'] = ''
        data[1]['timepoint'] = '0'
        self.assertEqual(self.check(stop_times=data)['feasibility'],
                         'unknown_do_not_navigate')
        data[1]['arrival_time'] = '08:15:00'
        result = self.check(stop_times=data)
        self.assertTrue(result['approximate_stop_times_used'])
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')

    def test_time_bounds_can_rule_out_impossible(self):
        freq = [dict(r) for r in self.freq]
        freq[1]['start_time'] = '07:50:00'
        freq[1]['end_time'] = '08:10:00'
        result = self.check(frequencies=freq)
        self.assertEqual(result['feasibility'], 'impossible_by_time_bounds')

    def test_invalid_date_and_unknown_trip_fail_closed(self):
        self.assertEqual(self.check(service_date='20260230')['reason'],
                         'invalid_service_date')
        self.assertEqual(self.check(outbound_trip_id='missing')['reason'],
                         'unknown_trip_id')

    def test_service_date_not_current_clock_date(self):
        result = self.check(service_date='20261030')
        self.assertEqual(result['inbound_service'], 'active')
        self.assertEqual(result['outbound_service'], 'active')


    def test_corrupt_later_timepoint_blocks_otherwise_valid_transfer(self):
        # The selected inbound X arrival looks plausible, but a later stop
        # impossibly arrives before X departed. Reject the whole template.
        corrupt = self.times + [
            {'trip_id': 'in', 'stop_id': 'Z', 'stop_sequence': '3',
             'arrival_time': '08:05:00', 'departure_time': '08:35:00',
             'timepoint': '1'},
        ]
        result = self.check(stop_times=corrupt)
        self.assertEqual(result['reason'], 'invalid_trip_timepoint_chronology')
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')

    def test_reversed_dwell_blocks_otherwise_valid_transfer(self):
        # A later stop on the outbound template has impossible dwell times.
        # Its error must not be ignored because the selected transfer is X.
        corrupt = [dict(row) for row in self.times]
        corrupt[3]['arrival_time'] = '08:55:00'
        result = self.check(stop_times=corrupt)
        self.assertEqual(result['reason'], 'invalid_trip_timepoint_chronology')
        self.assertEqual(result['feasibility'], 'unknown_do_not_navigate')


if __name__ == '__main__':
    unittest.main()
