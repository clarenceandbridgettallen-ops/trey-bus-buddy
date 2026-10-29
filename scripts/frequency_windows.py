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


def stop_window(frequency, stops, stop_id, event='departure'):
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
    first_departure = seconds(ordered[0].get('departure_time'))
    if first_departure is None:
        return unknown('missing_first_stop_departure_anchor')
    matches = [row for row in ordered if str(row.get('stop_id', '')).strip() == str(stop_id)]
    if len(matches) != 1:
        return unknown('missing_or_ambiguous_stop_id')
    stop = matches[0]
    restriction = 'pickup_type' if event == 'departure' else 'drop_off_type'
    if str(stop.get(restriction, '')).strip() not in ('', '0'):
        return unknown('boarding_or_alighting_not_confirmed')
    target = seconds(stop.get(event + '_time'))
    if target is None or target < first_departure:
        return unknown('missing_or_invalid_stop_offset')
    offset = target - first_departure
    return {
        'status': 'possible_window_only_not_departure',
        'earliest_seconds': start + offset,
        'latest_exclusive_seconds': end + offset,
        'headway_seconds': headway,
        'exact_times_mode': mode,
        'stop_id': str(stop_id),
        'timepoint': str(stop.get('timepoint', '')).strip() or 'unspecified',
        'timing_verified': False,
        'live_arrival_verified': False,
    }


def transfer_feasibility(inbound, outbound, minimum_transfer_seconds):
    """Rule out impossible windows; never assert a timed transfer is guaranteed."""
    if (inbound.get('status') != 'possible_window_only_not_departure' or
            outbound.get('status') != 'possible_window_only_not_departure'):
        return 'unknown_do_not_navigate'
    if not isinstance(minimum_transfer_seconds, (int, float)) or minimum_transfer_seconds < 0:
        return 'unknown_do_not_navigate'
    if inbound['earliest_seconds'] + minimum_transfer_seconds >= outbound['latest_exclusive_seconds']:
        return 'impossible_by_time_bounds'
    return 'possible_unverified_never_guaranteed'


def audit_frequency_boarding_windows(frequencies, stop_times):
    """Count diagnostics only; no route or arrival predictions are published."""
    by_trip = {}
    for stop in stop_times:
        by_trip.setdefault(str(stop.get('trip_id', '')).strip(), []).append(stop)
    unknown_pairs = 0
    window_pairs = 0
    blocked_trips = set()
    reasons = {}
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
            result = stop_window(freq, stops, stop.get('stop_id', ''), 'departure')
            if result['status'] == 'possible_window_only_not_departure':
                window_pairs += 1
            else:
                unknown_pairs += 1
                blocked_trips.add(trip)
                reason = result['reason']
                reasons[reason] = reasons.get(reason, 0) + 1
    return {
        'status': 'diagnostic_only_not_rider_routing',
        'frequency_rows': len(frequencies),
        'window_only_boarding_pairs': window_pairs,
        'unknown_boarding_pairs': unknown_pairs,
        'blocked_template_count': len(blocked_trips),
        'blocked_template_examples': sorted(blocked_trips)[:20],
        'unknown_reasons': reasons,
        'safe_walks_verified': False,
        'transfers_verified': False,
        'live_arrivals_verified': False,
    }
