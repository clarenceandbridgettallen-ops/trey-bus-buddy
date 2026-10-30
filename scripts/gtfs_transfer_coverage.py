"""Read-only audit of official GTFS transfers.txt; never certifies rider transfers.

GTFS transfer rules are directed and can be stop-, route-, or trip-specific.
Even a recommended/timed transfer does not prove a safe pedestrian route,
correct boarding side, an actual connection, or a live bus arrival.
"""
from collections import Counter

KEY_FIELDS = ('from_stop_id', 'to_stop_id', 'from_trip_id', 'to_trip_id',
              'from_route_id', 'to_route_id')
VALID_TYPES = {'0', '1', '2', '3', '4', '5'}


def audit_gtfs_transfers(rows, stops, routes, trips, file_present=True):
    """Return a deterministic, bounded summary; no itinerary or ETA output."""
    stop_ids = {str(row.get('stop_id') or '').strip() for row in stops if isinstance(row, dict)} - {''}
    route_ids = {str(row.get('route_id') or '').strip() for row in routes if isinstance(row, dict)} - {''}
    trip_routes = {str(row.get('trip_id') or '').strip(): str(row.get('route_id') or '').strip()
                   for row in trips if isinstance(row, dict) and str(row.get('trip_id') or '').strip()}
    type_counts = Counter()
    problems = Counter()
    examples = []
    seen = set()
    cross_stop = 0
    route_or_trip_scoped = 0
    minimum_seconds = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            problems['malformed_row'] += 1
            if len(examples) < 12: examples.append({'row': index, 'issue': 'malformed_row'})
            continue
        key = tuple(str(row.get(field) or '').strip() for field in KEY_FIELDS)
        typ = str(row.get('transfer_type') or '').strip() or '0'
        type_counts[typ] += 1
        issues = set()
        if typ not in VALID_TYPES: issues.add('invalid_transfer_type')
        if key in seen: issues.add('duplicate_rule_key')
        seen.add(key)
        if key[0] and key[1] and key[0] != key[1]: cross_stop += 1
        if any(key[2:]): route_or_trip_scoped += 1
        for pos, ids, kind in ((0, stop_ids, 'stop'), (1, stop_ids, 'stop'),
                               (4, route_ids, 'route'), (5, route_ids, 'route')):
            if key[pos] and key[pos] not in ids: issues.add('unknown_' + kind + '_reference')
        for pos in (2, 3):
            if key[pos] and key[pos] not in trip_routes: issues.add('unknown_trip_reference')
        for trip_pos, route_pos in ((2, 4), (3, 5)):
            if key[trip_pos] and key[route_pos] and trip_routes.get(key[trip_pos]) not in (None, key[route_pos]):
                issues.add('trip_route_mismatch')
        if typ in ('0', '1', '2', '3') and (not key[0] or not key[1]):
            issues.add('missing_transfer_stop')
        if typ in ('4', '5') and (not key[2] or not key[3]):
            issues.add('missing_linked_trip')
        raw_min = str(row.get('min_transfer_time') or '').strip()
        if typ == '2' and not raw_min:
            issues.add('missing_required_min_transfer_time')
        if raw_min:
            try:
                seconds = int(raw_min)
                if seconds < 0: raise ValueError('negative')
                minimum_seconds.append(seconds)
            except (ValueError, TypeError):
                issues.add('invalid_min_transfer_time')
        for issue in sorted(issues): problems[issue] += 1
        if issues and len(examples) < 12:
            examples.append({'row': index, 'issues': sorted(issues),
                             'from_stop_id': key[0], 'to_stop_id': key[1], 'transfer_type': typ})
    return {
        'status': 'read_only_official_transfer_rules_not_rider_navigation',
        'transfers_file_present': bool(file_present),
        'transfer_rows': len(rows),
        'transfer_type_counts': dict(sorted(type_counts.items())),
        'cross_stop_rules': cross_stop,
        'route_or_trip_scoped_rules': route_or_trip_scoped,
        'min_transfer_time_seconds_min': min(minimum_seconds) if minimum_seconds else None,
        'min_transfer_time_seconds_max': max(minimum_seconds) if minimum_seconds else None,
        'issue_counts': dict(sorted(problems.items())),
        'issue_examples': examples,
        'official_stop_count': len(stop_ids),
        'official_trip_count': len(trip_routes),
        'safe_pedestrian_connection_verified': False,
        'boarding_side_verified': False,
        'timed_transfer_guaranteed': False,
        'actual_vehicle_arrival_verified': False,
        'note': 'GTFS transfers.txt is directional and may have trip/route overrides. '
                'Types 0/1 are not evidence of a guaranteed accessible transfer; '
                'type 3 forbids transfer, type 2 requires a minimum time, '
                'and types 4/5 concern linked in-seat transfers.'
    }
