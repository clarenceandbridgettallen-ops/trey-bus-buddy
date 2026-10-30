"""Read-only sample of *actual agency GTFS trip pairs* sharing one stop ID.

This is a QA audit, not a route planner. A shared stop ID does not establish
a safe pedestrian crossing, correct boarding side, an accessible platform,
or an actual vehicle arrival. Never return a predicted departure.
"""
from collections import defaultdict
from trip_transfer_diagnostic import diagnose_trip_transfer


def audit_real_transfer_pairs(frequencies, trips, stop_times, calendar, exceptions,
                              service_date, limit=8):
    """Evaluate a bounded, deterministic sample of real feed trip/stop IDs.

    A frequency template with multiple windows is excluded rather than
    selecting an arbitrary frequency record. Only explicitly timed,
    non-approximate stop visits are candidate endpoints. Diagnostic results
    remain unverified and must never be sent to the rider-facing planner.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0 or limit > 25:
        raise ValueError('limit must be an integer between 0 and 25')
    if not isinstance(trips, dict):
        raise TypeError('trips must be indexed by trip_id')
    frequency_by_trip = defaultdict(list)
    for row in frequencies:
        if isinstance(row, dict):
            frequency_by_trip[str(row.get('trip_id', '')).strip()].append(row)
    eligible = {tid: rows[0] for tid, rows in frequency_by_trip.items()
                if tid in trips and len(rows) == 1}
    if limit == 0:
        return _summary([], len(eligible), service_date)
    trip_stops = defaultdict(list)
    for row in stop_times:
        if isinstance(row, dict):
            tid = str(row.get('trip_id', '')).strip()
            if tid in eligible:
                trip_stops[tid].append(row)

    arrivals, departures = defaultdict(list), defaultdict(list)
    restricted_alighting_visits = 0
    restricted_boarding_visits = 0
    for tid, rows in trip_stops.items():
        try:
            sequences = [int(row['stop_sequence']) for row in rows]
        except (KeyError, TypeError, ValueError):
            continue
        if len(sequences) < 2 or len(set(sequences)) != len(sequences):
            continue
        first, last = min(sequences), max(sequences)
        for row, sequence in zip(rows, sequences):
            stop_id = str(row.get('stop_id', '')).strip()
            if not stop_id or str(row.get('timepoint', '')).strip() not in ('', '1'):
                continue
            # An arrival at a trip's first stop is not evidence of arriving
            # on a bus; a departure at its last stop is not onward travel.
            if sequence > first and str(row.get('arrival_time', '')).strip():
                if str(row.get('drop_off_type', '')).strip() in ('', '0'):
                    arrivals[stop_id].append((tid, sequence))
                else:
                    restricted_alighting_visits += 1
            if sequence < last and str(row.get('departure_time', '')).strip():
                if str(row.get('pickup_type', '')).strip() in ('', '0'):
                    departures[stop_id].append((tid, sequence))
                else:
                    restricted_boarding_visits += 1

    # Select one candidate per stop first. The old lexicographic first-N
    # selection repeatedly audited the same transfer center (TL-1), which
    # made the sample appear broader than it was. This is a QA sampler only.
    def representative_visits(visits):
        first_per_route, repeats, seen_routes = [], [], set()
        for visit in sorted(visits):
            route = str(trips[visit[0]].get('route', ''))
            if route not in seen_routes:
                seen_routes.add(route)
                first_per_route.append(visit)
            elif len(repeats) < 16:
                repeats.append(visit)
        return (first_per_route + repeats)[:16]

    candidates_by_stop = {}
    for stop_id in sorted(arrivals.keys() & departures.keys()):
        candidates = []
        for inbound_tid, inbound_seq in representative_visits(arrivals[stop_id]):
            for outbound_tid, outbound_seq in representative_visits(departures[stop_id]):
                if inbound_tid == outbound_tid:
                    continue
                if trips[inbound_tid].get('route') == trips[outbound_tid].get('route'):
                    continue
                candidates.append((stop_id, inbound_tid, inbound_seq,
                                   outbound_tid, outbound_seq))
                if len(candidates) >= 32:
                    break
            if len(candidates) >= 32:
                break
        if candidates:
            candidates_by_stop[stop_id] = candidates

    selected, selected_route_pairs = [], set()
    for stop_id, candidates in candidates_by_stop.items():
        # Prefer a previously unseen route pair, then a new stop. A stop
        # identity still says nothing about its pedestrian accessibility.
        chosen = next((c for c in candidates
                       if (str(trips[c[1]].get('route', '')),
                           str(trips[c[3]].get('route', ''))) not in selected_route_pairs),
                      candidates[0])
        selected.append(chosen)
        selected_route_pairs.add((str(trips[chosen[1]].get('route', '')),
                                  str(trips[chosen[3]].get('route', ''))))
        if len(selected) >= limit:
            break

    # Only after covering available distinct stops do we sample additional
    # pairs at those stops. Never treat a headway overlap as a real transfer.
    if len(selected) < limit:
        for depth in range(32):
            for stop_id, candidates in candidates_by_stop.items():
                if depth < len(candidates):
                    candidate = candidates[depth]
                    if candidate not in selected:
                        selected.append(candidate)
                        if len(selected) >= limit:
                            break
            if len(selected) >= limit:
                break

    samples = []
    for stop_id, inbound_tid, inbound_seq, outbound_tid, outbound_seq in selected:
        diagnosis = diagnose_trip_transfer(
            [eligible[inbound_tid], eligible[outbound_tid]],
            {tid: trips[tid] for tid in (inbound_tid, outbound_tid)},
            trip_stops[inbound_tid] + trip_stops[outbound_tid],
            calendar, exceptions, service_date,
            inbound_tid, stop_id, inbound_seq,
            outbound_tid, stop_id, outbound_seq, 300)
        samples.append({
            'stop_id': stop_id,
            'inbound_trip_id': inbound_tid,
            'inbound_stop_sequence': inbound_seq,
            'inbound_route': trips[inbound_tid].get('route', ''),
            'outbound_trip_id': outbound_tid,
            'outbound_stop_sequence': outbound_seq,
            'outbound_route': trips[outbound_tid].get('route', ''),
            'feasibility': diagnosis['feasibility'],
            'reason': diagnosis.get('reason', ''),
            'inbound_service': diagnosis.get('inbound_service', 'unverified'),
            'outbound_service': diagnosis.get('outbound_service', 'unverified'),
        })
    return _summary(samples, len(eligible), service_date,
                    restricted_alighting_visits, restricted_boarding_visits)


def _summary(samples, eligible, service_date,
             restricted_alighting_visits=0, restricted_boarding_visits=0):
    return {
        'status': 'read_only_actual_feed_sample_not_rider_navigation',
        'service_date': service_date,
        'eligible_unique_frequency_trip_templates': eligible,
        'sample_count': len(samples),
        'distinct_transfer_stop_ids_sampled': len({s['stop_id'] for s in samples}),
        'distinct_route_pairs_sampled': len({
            (s['inbound_route'], s['outbound_route']) for s in samples}),
        'restricted_alighting_visits_excluded': restricted_alighting_visits,
        'restricted_boarding_visits_excluded': restricted_boarding_visits,
        'sample_limitations': (
            'Shared stop IDs and headway windows do not verify walking, '
            'boarding side, accessibility, actual departures, or live arrivals. '
            'GTFS pickup/drop-off restrictions are excluded, not validated on site.'),
        'samples': samples,
    }
