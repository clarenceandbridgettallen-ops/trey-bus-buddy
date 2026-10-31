"""Conservative, read-only stop-level GTFS frequency-window diagnostics.

A frequency window is NEVER a scheduled departure or live arrival. This module
can reject impossible transfers but cannot certify that a bus will be there.
"""
import re


def seconds(value):
    text = str(value or '').strip()
    if not re.fullmatch(r'\d{2,}:[0-5]\d:[0-5]\d', text):
        return None
    h, m, s = map(int, text.split(':'))
    return h * 3600 + m * 60 + s


def unknown(reason):
    return {'status': 'unknown_do_not_navigate', 'reason': reason}


def stop_window(frequency, stops, stop_id, event='departure', stop_sequence=None):
    """Return a *possible service window*, never a specific bus time.

    GTFS frequencies start/end refer to the first stop's departure time. The
    offset for a downstream stop must be anchored to a valid first departure.
    End is exclusive. Timepoint=0 is retained as an uncertainty warning.
    """
    if event not in ('departure', 'arrival'):
        return unknown('invalid_event')
    mode = str(frequency.get('exact_times', '')).strip() or '0'
    if mode not in ('0', '1'):
        return unknown('invalid_exact_times_mode')
    start = seconds(frequency.get('start_time'))
    end = seconds(frequency.get('end_time'))
    try:
        headway = int(frequency.get('headway_secs', ''))
    except (TypeError, ValueError):
        headway = 0
    if start is None or end is None or end <= start or headway <= 0:
        return unknown('invalid_frequency_window')
    try:
        ordered = sorted(stops, key=lambda row: int(row['stop_sequence']))
        sequences = [int(row['stop_sequence']) for row in ordered]
    except (KeyError, ValueError, TypeError):
        return unknown('invalid_stop_sequence')
    if len(ordered) < 2 or len(set(sequences)) != len(sequences):
        return unknown('missing_or_duplicate_stop_sequence')
    # Never combine stop-time rows from a different trip into a plausible window.
    trip_id = str(frequency.get('trip_id', '')).strip()
    if not trip_id or any(str(row.get('trip_id', '')).strip() != trip_id for row in ordered):
        return unknown('mismatched_trip_stop_times')
    first_departure = seconds(ordered[0].get('departure_time'))
    if first_departure is None:
        return unknown('missing_first_stop_departure_anchor')
    matches = [row for row in ordered if str(row.get('stop_id', '')).strip() == str(stop_id)]
    if not matches:
        return unknown('missing_stop_id')
    if stop_sequence is not None:
        # GTFS stop_times primary key is (trip_id, stop_sequence).
        # Never guess which visit to a looped stop the rider intends.
        requested = str(stop_sequence).strip()
        if not re.fullmatch(r'\d+', requested):
            return unknown('invalid_requested_stop_sequence')
        matches = [row for row in matches if int(row['stop_sequence']) == int(requested)]
        if not matches:
            return unknown('stop_sequence_does_not_match_stop_id')
    if len(matches) > 1:
        # Looped trips may legally visit the same stop more than once.
        return unknown('repeated_stop_id_requires_stop_sequence')
    stop = matches[0]
    restriction = 'pickup_type' if event == 'departure' else 'drop_off_type'
    if str(stop.get(restriction, '')).strip() not in ('', '0'):
        return unknown('boarding_or_alighting_not_confirmed')
    timepoint = str(stop.get('timepoint', '')).strip()
    if timepoint not in ('', '0', '1'):
        return unknown('invalid_timepoint')
    raw_time = str(stop.get(event + '_time', '') or '').strip()
    if not raw_time:
        # GTFS permits some intermediate timepoint=0 rows to omit times.
        # This requires interpolation and is not safe for rider navigation.
        return unknown('untimed_approximate_stop_requires_interpolation' if timepoint == '0'
                       else 'missing_required_or_unmarked_stop_time')
    target = seconds(raw_time)
    if target is None:
        return unknown('malformed_stop_time')
    if target < first_departure:
        # May be legitimate at a first-stop arrival; do not invent a bound.
        return unknown('negative_offset_unverified')
    offset = target - first_departure
    return {
        'status': 'possible_window_only_not_departure',
        'earliest_seconds': start + offset,
        'latest_exclusive_seconds': end + offset,
        'headway_seconds': headway,
        'exact_times_mode': mode,
        'stop_id': str(stop_id),
        'stop_sequence': int(stop['stop_sequence']),
        'timepoint': timepoint or 'unspecified',
        'stop_time_approximate': timepoint == '0',
        'timing_verified': False,
        'live_arrival_verified': False,
    }


def transfer_feasibility(inbound, outbound, minimum_transfer_seconds):
    """Rule out impossible windows; never assert a timed transfer is guaranteed."""
    import math
    if (not isinstance(inbound, dict) or not isinstance(outbound, dict) or
            inbound.get('status') != 'possible_window_only_not_departure' or
            outbound.get('status') != 'possible_window_only_not_departure'):
        return 'unknown_do_not_navigate'
    # GTFS timepoint=0 is approximate even when it contains a clock value.
    # It cannot safely prove that a connection is impossible (or possible).
    # Both outcomes must remain unknown until independently timed.
    if any(window.get('stop_time_approximate') is True or
           window.get('timepoint') == '0' for window in (inbound, outbound)):
        return 'unknown_do_not_navigate'
    # A corrupt bound, NaN, infinity or reversed window must never become a
    # seemingly possible transfer. These are diagnostics, not departures.
    fields = (inbound.get('earliest_seconds'), inbound.get('latest_exclusive_seconds'),
              outbound.get('earliest_seconds'), outbound.get('latest_exclusive_seconds'),
              minimum_transfer_seconds)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in fields):
        return 'unknown_do_not_navigate'
    in_start, in_end, out_start, out_end, walk = fields
    if walk < 0 or in_end <= in_start or out_end <= out_start:
        return 'unknown_do_not_navigate'
    if in_start + walk >= out_end:
        return 'impossible_by_time_bounds'
    return 'possible_unverified_never_guaranteed'


def transfer_feasibility_for_service_date(inbound, outbound, minimum_transfer_seconds,
                                          inbound_service, outbound_service):
    """Conservative date-aware transfer diagnostic; NOT a rider itinerary.

    Statuses must be separately classified for the SAME GTFS service date,
    including calendar_dates exceptions. Do not infer active service from a
    clock date, or treat a possible window as an actual departure.
    """
    statuses = (inbound_service, outbound_service)
    if any(s not in ('active', 'inactive', 'uncertain') for s in statuses):
        return 'unknown_do_not_navigate'
    if 'uncertain' in statuses:
        return 'unknown_do_not_navigate'
    if 'inactive' in statuses:
        return 'inactive_service_on_selected_date'
    return transfer_feasibility(inbound, outbound, minimum_transfer_seconds)



def has_bracketing_timepoints(stops, stop_sequence, event='departure'):
    """Read-only shape check, NOT interpolation or a safe boarding time.

    An untimed intermediate stop has candidate anchors only if a timed
    timepoint exists on both sides in this exact trip sequence. Even then,
    road distance, runtime and agency approval are not verified.
    """
    if event not in ('departure', 'arrival'):
        return False
    try:
        ordered = sorted(stops, key=lambda row: int(row['stop_sequence']))
        sequences = [int(row['stop_sequence']) for row in ordered]
        target = int(stop_sequence)
    except (KeyError, TypeError, ValueError):
        return False
    if len(sequences) != len(set(sequences)) or target not in sequences:
        return False
    index = sequences.index(target)
    def anchor(row):
        if str(row.get('timepoint', '')).strip() not in ('', '1'):
            return None
        return seconds(row.get(event + '_time'))
    before = next((value for row in reversed(ordered[:index])
                   if (value := anchor(row)) is not None), None)
    after = next((value for row in ordered[index + 1:]
                  if (value := anchor(row)) is not None), None)
    return before is not None and after is not None and before <= after



def audit_frequency_anchor_order(frequencies, stop_times):
    """Read-only chronology audit of exact GTFS timepoints, never interpolation.

    Approximate timepoint=0 rows are excluded from anchor comparisons. Compare
    arrival with arrival and departure with departure in stop_sequence order;
    also reject a later exact arrival before an earlier exact departure, and
    arrival later than departure at the same exact timepoint.
    Missing values are not guessed or treated as zero.
    """
    referenced = {str(row.get('trip_id', '')).strip() for row in frequencies}
    by_trip = {}
    for row in stop_times:
        trip = str(row.get('trip_id', '')).strip()
        if trip in referenced:
            by_trip.setdefault(trip, []).append(row)
    checked_pairs = 0
    reversed_pairs = 0
    cross_event_pairs_checked = 0
    backward_cross_event_pairs = 0
    reversed_dwell = 0
    invalid_times = 0
    invalid_sequences = 0
    excluded_approximate_rows = 0
    affected = set()
    missing_trip_rows = 0
    for trip in sorted(referenced):
        stops = by_trip.get(trip, [])
        if not stops:
            missing_trip_rows += 1
            affected.add(trip)
            continue
        try:
            ordered = sorted(stops, key=lambda row: int(row['stop_sequence']))
            sequences = [int(row['stop_sequence']) for row in ordered]
            if len(set(sequences)) != len(sequences):
                raise ValueError('duplicate stop_sequence')
        except (KeyError, ValueError, TypeError):
            invalid_sequences += 1
            affected.add(trip)
            continue
        previous = {'arrival': None, 'departure': None}
        previous_departure = None
        for row in ordered:
            timepoint = str(row.get('timepoint', '')).strip()
            if timepoint == '0':
                excluded_approximate_rows += 1
                continue
            if timepoint not in ('', '1'):
                invalid_times += 1
                affected.add(trip)
                continue
            values = {}
            for event in ('arrival', 'departure'):
                raw = str(row.get(event + '_time', '') or '').strip()
                if not raw:
                    continue
                current = seconds(raw)
                if current is None:
                    invalid_times += 1
                    affected.add(trip)
                    continue
                values[event] = current
                if previous[event] is not None:
                    checked_pairs += 1
                    if current < previous[event]:
                        reversed_pairs += 1
                        affected.add(trip)
                previous[event] = current
            # Same-event monotonicity alone misses an impossible segment:
            # earlier departure 08:30, later arrival 08:20, later departure 08:45.
            if previous_departure is not None and 'arrival' in values:
                cross_event_pairs_checked += 1
                if values['arrival'] < previous_departure:
                    backward_cross_event_pairs += 1
                    affected.add(trip)
            if 'departure' in values:
                previous_departure = values['departure']
            if ('arrival' in values and 'departure' in values
                    and values['arrival'] > values['departure']):
                reversed_dwell += 1
                affected.add(trip)
    return {
        'status': 'diagnostic_only_not_rider_routing',
        'frequency_trip_templates': len(referenced),
        'ordered_anchor_pairs_checked': checked_pairs,
        'backward_anchor_pairs': reversed_pairs,
        'cross_event_pairs_checked': cross_event_pairs_checked,
        'backward_cross_event_pairs': backward_cross_event_pairs,
        'arrival_after_departure_at_stop': reversed_dwell,
        'malformed_anchor_or_timepoint_rows': invalid_times,
        'invalid_sequence_templates': invalid_sequences,
        'missing_stop_time_templates': missing_trip_rows,
        'excluded_approximate_rows': excluded_approximate_rows,
        'affected_template_count': len(affected),
        'affected_template_examples': sorted(affected)[:20],
        'interpolation_performed': False,
        'departures_verified': False,
    }

def audit_frequency_boarding_windows(frequencies, stop_times):
    """Count diagnostics only; no route or arrival predictions are published."""
    by_trip = {}
    for stop in stop_times:
        by_trip.setdefault(str(stop.get('trip_id', '')).strip(), []).append(stop)
    unknown_pairs = 0
    window_pairs = 0
    blocked_trips = set()
    reasons = {}
    bracketed_untimed = 0
    unbracketed_untimed = 0
    for freq in frequencies:
        trip = str(freq.get('trip_id', '')).strip()
        stops = by_trip.get(trip, [])
        if not stops:
            unknown_pairs += 1
            blocked_trips.add(trip)
            reasons['missing_trip_stop_times'] = reasons.get('missing_trip_stop_times', 0) + 1
            continue
        eligible = [s for s in stops if str(s.get('pickup_type', '')).strip() in ('', '0')]
        if not eligible:
            unknown_pairs += 1
            blocked_trips.add(trip)
            reasons['no_boarding_eligible_stops'] = reasons.get('no_boarding_eligible_stops', 0) + 1
            continue
        for stop in eligible:
            # Only inspect boarding-eligible stops; this does not prove a safe
            # pedestrian approach or accessible boarding side.
            result = stop_window(freq, stops, stop.get('stop_id', ''), 'departure', stop_sequence=stop.get('stop_sequence'))
            if result['status'] == 'possible_window_only_not_departure':
                window_pairs += 1
            else:
                unknown_pairs += 1
                blocked_trips.add(trip)
                reason = result['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
                if reason == 'untimed_approximate_stop_requires_interpolation':
                    if has_bracketing_timepoints(stops, stop.get('stop_sequence'), 'departure'):
                        bracketed_untimed += 1
                    else:
                        unbracketed_untimed += 1
    return {
        'status': 'diagnostic_only_not_rider_routing',
        'frequency_rows': len(frequencies),
        'window_only_boarding_pairs': window_pairs,
        'unknown_boarding_pairs': unknown_pairs,
        'blocked_template_count': len(blocked_trips),
        'blocked_template_examples': sorted(blocked_trips)[:20],
        'unknown_reasons': reasons,
        'untimed_bracket_candidates_not_verified': bracketed_untimed,
        'untimed_without_valid_brackets': unbracketed_untimed,
        'safe_walks_verified': False,
        'transfers_verified': False,
        'live_arrivals_verified': False,
    }
