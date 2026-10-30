"""Read-only same-service-date transfer diagnostics for Coast RTA frequency templates.

Not a trip planner: possible headway windows are NOT departures, and the caller's
walking allowance is NOT a verified accessible pedestrian route.
"""
import re
from datetime import datetime
from frequency_windows import stop_window, transfer_feasibility_for_service_date
from service_calendar import audit_frequency_service_date


def diagnose_trip_transfer(frequencies, trips, stop_times, calendar, exceptions,
                           service_date, inbound_trip_id, inbound_stop_id,
                           inbound_stop_sequence, outbound_trip_id,
                           outbound_stop_id, outbound_stop_sequence,
                           minimum_transfer_seconds):
    """Evaluate two identified GTFS trip templates on one explicit service date.

    Never select a frequency row, repeated stop visit, or service date by guess.
    Never return a scheduled boarding time or certify a walking connection.
    """
    result = {
        'status': 'diagnostic_only_not_rider_routing',
        'feasibility': 'unknown_do_not_navigate',
        'service_date': service_date,
        'safe_walking_route_verified': False,
        'actual_departures_verified': False,
        'live_arrivals_verified': False,
    }

    def blocked(reason):
        return {**result, 'reason': reason}

    if not isinstance(service_date, str) or not re.fullmatch(r'\d{8}', service_date):
        return blocked('invalid_service_date')
    try:
        datetime.strptime(service_date, '%Y%m%d')
    except ValueError:
        return blocked('invalid_service_date')

    pair = (str(inbound_trip_id or '').strip(), str(outbound_trip_id or '').strip())
    if not all(pair) or pair[0] == pair[1]:
        return blocked('missing_or_identical_trip_ids')
    if not isinstance(trips, dict) or any(tid not in trips for tid in pair):
        return blocked('unknown_trip_id')
    if not isinstance(frequencies, list) or not isinstance(stop_times, list):
        return blocked('invalid_feed_records')

    # Without a separately verified pedestrian route, two different stop IDs
    # are NOT a validated transfer location, regardless of temporal overlap.
    # This is a diagnostic for same-stop transfers only, not walk transfers.
    in_stop = str(inbound_stop_id or '').strip()
    out_stop = str(outbound_stop_id or '').strip()
    if not in_stop or not out_stop:
        return blocked('missing_transfer_stop_id')
    if in_stop != out_stop:
        return blocked('different_transfer_stops_no_verified_walk')

    frequency_by_trip = {}
    for row in frequencies:
        if not isinstance(row, dict):
            return blocked('invalid_frequency_row')
        tid = str(row.get('trip_id', '')).strip()
        if tid in pair:
            frequency_by_trip.setdefault(tid, []).append(row)
    if any(len(frequency_by_trip.get(tid, [])) != 1 for tid in pair):
        return blocked('missing_or_ambiguous_frequency_row')

    statuses = []
    for tid in pair:
        audit = audit_frequency_service_date(
            [{'trip_id': tid}], trips, calendar, exceptions, service_date)
        if audit['active_rows'] == 1:
            statuses.append('active')
        elif audit['inactive_rows'] == 1:
            statuses.append('inactive')
        else:
            statuses.append('uncertain')

    inbound_rows = [r for r in stop_times if str(r.get('trip_id', '')).strip() == pair[0]]
    outbound_rows = [r for r in stop_times if str(r.get('trip_id', '')).strip() == pair[1]]
    inbound = stop_window(frequency_by_trip[pair[0]][0], inbound_rows,
                          inbound_stop_id, 'arrival', inbound_stop_sequence)
    outbound = stop_window(frequency_by_trip[pair[1]][0], outbound_rows,
                           outbound_stop_id, 'departure', outbound_stop_sequence)

    feasibility = transfer_feasibility_for_service_date(
        inbound, outbound, minimum_transfer_seconds, *statuses)
    # Even explicitly supplied approximate times are not exact boarding anchors.
    if (feasibility == 'possible_unverified_never_guaranteed' and
            (inbound.get('stop_time_approximate') or
             outbound.get('stop_time_approximate'))):
        feasibility = 'unknown_do_not_navigate'

    return {
        **result, 'feasibility': feasibility,
        'inbound_service': statuses[0], 'outbound_service': statuses[1],
        'inbound_window_status': inbound['status'],
        'outbound_window_status': outbound['status'],
        'approximate_stop_times_used': bool(
            inbound.get('stop_time_approximate') or
            outbound.get('stop_time_approximate')),
        'reason': 'headway_bounds_and_service_date_only_no_confirmed_connection',
    }
