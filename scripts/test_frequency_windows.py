import unittest
from frequency_windows import seconds, stop_window, transfer_feasibility, audit_frequency_boarding_windows, has_bracketing_timepoints, audit_frequency_anchor_order


def freq(**changes):
    return dict({'trip_id':'t','start_time':'08:00:00','end_time':'09:00:00','headway_secs':'900','exact_times':'0'},**changes)


def stops():
    return [
        {'trip_id':'t','stop_id':'A','stop_sequence':'1','arrival_time':'07:59:00','departure_time':'08:00:00','pickup_type':'0'},
        {'trip_id':'t','stop_id':'B','stop_sequence':'2','arrival_time':'08:15:00','departure_time':'08:17:00','pickup_type':'0'},
    ]


class FrequencyWindowTests(unittest.TestCase):
    def test_overnight_gtfs_hours(self):
        self.assertEqual(seconds('25:01:00'), 90060)

    def test_malformed_time_rejected(self):
        self.assertIsNone(seconds('08:90:00'))
        self.assertIsNone(seconds('8:30:00'))

    def test_downstream_window_is_not_a_departure(self):
        result = stop_window(freq(), stops(), 'B')
        self.assertEqual(result['status'], 'possible_window_only_not_departure')
        self.assertEqual(result['earliest_seconds'], 8*3600 + 17*60)
        self.assertEqual(result['latest_exclusive_seconds'], 9*3600 + 17*60)
        self.assertFalse(result['timing_verified'])

    def test_arrival_offset_differs_from_departure(self):
        result = stop_window(freq(), stops(), 'B', 'arrival')
        self.assertEqual(result['earliest_seconds'], 8*3600 + 15*60)

    def test_missing_first_departure_blocks_all_downstream(self):
        data = stops(); data[0]['departure_time'] = ''
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'missing_first_stop_departure_anchor')

    def test_no_pickup_stop_cannot_be_boarded(self):
        data = stops(); data[1]['pickup_type'] = '1'
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'boarding_or_alighting_not_confirmed')

    def test_duplicate_stop_id_blocks_ambiguous_loop(self):
        data = stops(); data.append(dict(data[1], stop_sequence='3'))
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'repeated_stop_id_requires_stop_sequence')

    def test_invalid_or_missing_offset_rejected(self):
        data = stops(); data[1]['departure_time'] = 'not-time'
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'malformed_stop_time')

    def test_exact_times_one_still_not_claimed_verified(self):
        result = stop_window(freq(exact_times='1'), stops(), 'B')
        self.assertFalse(result['timing_verified'])
        self.assertEqual(result['exact_times_mode'], '1')

    def test_time_bounds_rule_out_impossible_transfer(self):
        inbound = stop_window(freq(), stops(), 'B', 'arrival')
        outbound = stop_window(freq(start_time='07:00:00',end_time='08:00:00'),stops(),'A')
        self.assertEqual(transfer_feasibility(inbound,outbound,600),'impossible_by_time_bounds')

    def test_overlapping_windows_never_guarantee_transfer(self):
        inbound = stop_window(freq(),stops(),'B','arrival')
        outbound = stop_window(freq(start_time='08:30:00',end_time='10:00:00'),stops(),'A')
        self.assertEqual(transfer_feasibility(inbound,outbound,600),'possible_unverified_never_guaranteed')

    def test_unknown_input_blocks_transfer(self):
        self.assertEqual(transfer_feasibility({'status':'unknown_do_not_navigate'}, {}, 600),'unknown_do_not_navigate')

    def test_untimed_approximate_stop_is_not_malformed(self):
        data = stops()
        data[1]['timepoint'] = '0'
        data[1]['departure_time'] = ''
        result = stop_window(freq(), data, 'B')
        self.assertEqual(result['reason'], 'untimed_approximate_stop_requires_interpolation')
        self.assertEqual(result['status'], 'unknown_do_not_navigate')

    def test_missing_exact_or_unspecified_stop_time_is_separate(self):
        for timepoint in ('1', ''):
            with self.subTest(timepoint=timepoint):
                data = stops()
                data[1]['timepoint'] = timepoint
                data[1]['departure_time'] = ''
                self.assertEqual(stop_window(freq(), data, 'B')['reason'],
                                 'missing_required_or_unmarked_stop_time')

    def test_malformed_time_distinguished_from_untimed(self):
        data = stops()
        data[1]['timepoint'] = '0'
        data[1]['departure_time'] = '08:75:00'
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'malformed_stop_time')

    def test_unknown_timepoint_is_not_trusted(self):
        data = stops()
        data[1]['timepoint'] = '9'
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'invalid_timepoint')

    def test_estimated_time_is_labeled_approximate(self):
        data = stops()
        data[1]['timepoint'] = '0'
        result = stop_window(freq(), data, 'B')
        self.assertTrue(result['stop_time_approximate'])
        self.assertFalse(result['timing_verified'])

    def test_mismatched_trip_rows_do_not_create_windows(self):
        data = stops()
        data[1]['trip_id'] = 'another-trip'
        self.assertEqual(stop_window(freq(), data, 'B')['reason'], 'mismatched_trip_stop_times')

    def test_missing_stop_id_distinguished_from_legitimate_loop(self):
        self.assertEqual(stop_window(freq(), stops(), 'NOT-A-STOP')['reason'], 'missing_stop_id')

    def test_audit_separates_untimed_and_malformed_counts(self):
        data = stops()
        data[0]['timepoint'] = '0'
        data[0]['departure_time'] = '08:00:00'
        data[1]['timepoint'] = '0'
        data[1]['departure_time'] = ''
        report = audit_frequency_boarding_windows([freq()], data)
        self.assertEqual(report['unknown_reasons']['untimed_approximate_stop_requires_interpolation'], 1)
        self.assertEqual(report['window_only_boarding_pairs'], 1)

    def test_missing_trip_stop_times_are_not_mistaken_for_coverage(self):
        report = audit_frequency_boarding_windows([freq()], [])
        self.assertEqual(report['unknown_reasons']['missing_trip_stop_times'], 1)
        self.assertEqual(report['blocked_template_examples'], ['t'])

    def test_audit_counts_unknown_without_departures(self):
        data = stops(); data[0]['departure_time']=''
        report = audit_frequency_boarding_windows([freq()],data)
        self.assertEqual(report['unknown_boarding_pairs'],2)
        self.assertEqual(report['blocked_template_examples'],['t'])
        self.assertFalse(report['transfers_verified'])


    def test_looped_stop_visits_have_distinct_sequence_offsets(self):
        data = stops()
        data.append(dict(data[1], stop_sequence='3',
                         arrival_time='08:28:00', departure_time='08:30:00'))
        first = stop_window(freq(), data, 'B', stop_sequence=2)
        second = stop_window(freq(), data, 'B', stop_sequence='3')
        self.assertEqual(first['status'], 'possible_window_only_not_departure')
        self.assertEqual(second['status'], 'possible_window_only_not_departure')
        self.assertEqual(first['stop_sequence'], 2)
        self.assertEqual(second['stop_sequence'], 3)
        self.assertEqual(second['earliest_seconds'] - first['earliest_seconds'], 13 * 60)
        self.assertFalse(first['timing_verified'])
        self.assertFalse(second['timing_verified'])

    def test_looped_stop_without_sequence_remains_ambiguous(self):
        data = stops()
        data.append(dict(data[1], stop_sequence='3', departure_time='08:30:00'))
        self.assertEqual(stop_window(freq(), data, 'B')['reason'],
                         'repeated_stop_id_requires_stop_sequence')

    def test_wrong_or_invalid_sequence_cannot_select_a_different_stop(self):
        data = stops()
        self.assertEqual(stop_window(freq(), data, 'B', stop_sequence=1)['reason'],
                         'stop_sequence_does_not_match_stop_id')
        for invalid in ('', '2.0', '-2', 'not-a-sequence'):
            with self.subTest(invalid=invalid):
                self.assertEqual(stop_window(freq(), data, 'B', stop_sequence=invalid)['reason'],
                                 'invalid_requested_stop_sequence')

    def test_audit_counts_loop_visits_by_sequence_without_certifying_departures(self):
        data = stops()
        data.append(dict(data[1], stop_sequence='3',
                         arrival_time='08:28:00', departure_time='08:30:00'))
        report = audit_frequency_boarding_windows([freq()], data)
        self.assertEqual(report['window_only_boarding_pairs'], 3)
        self.assertEqual(report['unknown_boarding_pairs'], 0)
        self.assertEqual(report['blocked_template_count'], 0)
        self.assertFalse(report['transfers_verified'])
        self.assertFalse(report['live_arrivals_verified'])

    def test_audit_loop_with_untimed_visit_remains_blocked(self):
        data = stops()
        data.append(dict(data[1], stop_sequence='3',
                         departure_time='', timepoint='0'))
        report = audit_frequency_boarding_windows([freq()], data)
        self.assertEqual(report['window_only_boarding_pairs'], 2)
        self.assertEqual(report['unknown_reasons']['untimed_approximate_stop_requires_interpolation'], 1)
        self.assertEqual(report['blocked_template_count'], 1)


    def test_untimed_bracket_counts_do_not_publish_times(self):
        data = [
            {'trip_id':'t','stop_id':'A','stop_sequence':'1','departure_time':'08:00:00','timepoint':'1'},
            {'trip_id':'t','stop_id':'B','stop_sequence':'2','departure_time':'','timepoint':'0'},
            {'trip_id':'t','stop_id':'C','stop_sequence':'3','departure_time':'08:30:00','timepoint':'1'},
        ]
        report = audit_frequency_boarding_windows([freq()], data)
        self.assertEqual(report['untimed_bracket_candidates_not_verified'], 1)
        self.assertEqual(report['untimed_without_valid_brackets'], 0)
        self.assertEqual(report['unknown_boarding_pairs'], 1)
        self.assertFalse(report['transfers_verified'])
        self.assertEqual(stop_window(freq(), data, 'B')['status'], 'unknown_do_not_navigate')

    def test_untimed_terminal_without_later_anchor_not_bracketed(self):
        data = stops()
        data[1]['timepoint'] = '0'
        data[1]['departure_time'] = ''
        report = audit_frequency_boarding_windows([freq()], data)
        self.assertEqual(report['untimed_bracket_candidates_not_verified'], 0)
        self.assertEqual(report['untimed_without_valid_brackets'], 1)

    def test_approximate_or_malformed_anchors_not_trusted(self):
        data = [
            {'stop_sequence':'1','departure_time':'08:00:00','timepoint':'0'},
            {'stop_sequence':'2','departure_time':'','timepoint':'0'},
            {'stop_sequence':'3','departure_time':'08:30:00','timepoint':'1'},
        ]
        self.assertFalse(has_bracketing_timepoints(data, 2))
        data[0]['timepoint'] = '1'
        data[2]['departure_time'] = '08:99:00'
        self.assertFalse(has_bracketing_timepoints(data, 2))

    def test_reverse_order_anchors_do_not_bracket(self):
        data = [
            {'stop_sequence':'1','departure_time':'09:00:00','timepoint':'1'},
            {'stop_sequence':'2','departure_time':'','timepoint':'0'},
            {'stop_sequence':'3','departure_time':'08:00:00','timepoint':'1'},
        ]
        self.assertFalse(has_bracketing_timepoints(data, 2))

    def test_loop_visit_bracketed_by_sequence_not_stop_id(self):
        data = [
            {'stop_sequence':'1','stop_id':'A','departure_time':'08:00:00','timepoint':'1'},
            {'stop_sequence':'2','stop_id':'B','departure_time':'','timepoint':'0'},
            {'stop_sequence':'3','stop_id':'A','departure_time':'08:30:00','timepoint':'1'},
        ]
        self.assertTrue(has_bracketing_timepoints(data, 2))
        self.assertFalse(has_bracketing_timepoints(data, 3))


    def test_backward_timepoint_anchors_are_flagged(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','arrival_time':'08:00:00','departure_time':'08:01:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','arrival_time':'08:20:00','departure_time':'08:21:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'3','arrival_time':'08:10:00','departure_time':'08:11:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['backward_anchor_pairs'], 2)
        self.assertEqual(report['affected_template_examples'], ['t'])
        self.assertFalse(report['interpolation_performed'])

    def test_approximate_timepoint_is_not_an_exact_anchor(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','departure_time':'08:00:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','departure_time':'07:00:00','timepoint':'0'},
            {'trip_id':'t','stop_sequence':'3','departure_time':'08:30:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['backward_anchor_pairs'], 0)
        self.assertEqual(report['excluded_approximate_rows'], 1)
        self.assertEqual(report['ordered_anchor_pairs_checked'], 1)

    def test_arrival_later_than_departure_is_flagged(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','arrival_time':'08:05:00','departure_time':'08:00:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','arrival_time':'08:30:00','departure_time':'08:31:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['arrival_after_departure_at_stop'], 1)
        self.assertEqual(report['affected_template_count'], 1)

    def test_malformed_and_duplicate_sequences_fail_diagnostic(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','departure_time':'08:00:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'1','departure_time':'08:30:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['invalid_sequence_templates'], 1)
        self.assertEqual(report['ordered_anchor_pairs_checked'], 0)
        data[1]['stop_sequence'] = '2'
        data[1]['departure_time'] = '08:99:00'
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['malformed_anchor_or_timepoint_rows'], 1)

    def test_gtfs_overnight_hours_remain_ordered(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','departure_time':'23:55:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','departure_time':'24:10:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'3','departure_time':'25:00:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['ordered_anchor_pairs_checked'], 2)
        self.assertEqual(report['backward_anchor_pairs'], 0)
        self.assertFalse(report['departures_verified'])


    def test_cross_event_reverse_segment_not_missed_by_same_event_checks(self):
        # Arrival-to-arrival and departure-to-departure are increasing, but
        # the bus cannot depart stop 1 at 08:30 and arrive at stop 2 at 08:20.
        data = [
            {'trip_id':'t','stop_sequence':'1','arrival_time':'08:00:00','departure_time':'08:30:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','arrival_time':'08:20:00','departure_time':'08:45:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['backward_anchor_pairs'], 0)
        self.assertEqual(report['cross_event_pairs_checked'], 1)
        self.assertEqual(report['backward_cross_event_pairs'], 1)
        self.assertEqual(report['affected_template_examples'], ['t'])
        self.assertFalse(report['departures_verified'])

    def test_cross_event_audit_skips_approximate_rows_and_accepts_overnight(self):
        data = [
            {'trip_id':'t','stop_sequence':'1','arrival_time':'23:55:00','departure_time':'23:58:00','timepoint':'1'},
            {'trip_id':'t','stop_sequence':'2','arrival_time':'20:00:00','departure_time':'20:01:00','timepoint':'0'},
            {'trip_id':'t','stop_sequence':'3','arrival_time':'24:05:00','departure_time':'24:06:00','timepoint':'1'},
        ]
        report = audit_frequency_anchor_order([freq()], data)
        self.assertEqual(report['cross_event_pairs_checked'], 1)
        self.assertEqual(report['backward_cross_event_pairs'], 0)
        self.assertEqual(report['excluded_approximate_rows'], 1)
        self.assertEqual(report['affected_template_count'], 0)


if __name__ == '__main__': unittest.main()
