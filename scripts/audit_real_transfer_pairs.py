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
                arrivals[stop_id].append((tid, sequence))
            if sequence < last and str(row.get('departure_time', '')).strip():
                departures[stop_id].append((tid, sequence))

    samples = []
    seen = set()
    for stop_id in sorted(arrivals.keys() & departures.keys()):
        # Bounded candidate search; stable order across identical GTFS feeds.
        for inbound_tid, inbound_seq in sorted(arrivals[stop_id])[:16]:
            for outbound_tid, outbound_seq in sorted(departures[stop_id])[:16]:
                if inbound_tid == outbound_tid:
                    continue
                # A transfer audit must compare distinct route labels, not
                # merely two runs of the same route at its terminal.
                if trips[inbound_tid].get('route') == trips[outbound_tid].get('route'):
                    continue
                key = (inbound_tid, inbound_seq, outbound_tid, outbound_seq, stop_id)
                if key in seen:
                    continue
                seen.add(key)
                diagnosis = diagnose_trip_transfer(
                    [eligible[inbound_tid], eligible[outbound_tid]],
                    {tid: trips[tid] for tid in (inbound_tid, outbound_tid)},
                    trip_stops[inbound_tid] + trip_stops[outbound_tid],
                    calendar, exceptions, service_date,
                    inbound_tid, stop_id, inbound_seq,
                    outbound_tid, stop_id, outbound_seq,
                    300)
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
                if len(samples) >= limit:
                    return _summary(samples, len(eligible), service_date)
    return _summary(samples, len(eligible), service_date)


def _summary(samples, eligible, service_date):
    return {
        'status': 'read_only_actual_feed_sample_not_rider_navigation',
        'service_date': service_date,
        'eligible_unique_frequency_trip_templates': eligible,
        'sample_count': len(samples),
        'sample_limitations': (
            'Shared stop IDs and headway windows do not verify walking, '
            'boarding side, accessibility, actual departures, or live arrivals.'),
        'samples': samples,
    }
