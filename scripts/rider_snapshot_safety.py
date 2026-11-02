"""Read-only Bus Buddy rider snapshot timing and loop-stop audit.

Missing GTFS times are NOT bus departure estimates. Repeated stop IDs may
represent legitimate loops; preserve each trip's stop sequence.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit_snapshot(stops_data, journeys_data):
    stops = stops_data['stops']
    trips = journeys_data['trips']
    known = {str(s.get('id', '')).strip() for s in stops}
    counts = dict(stops=len(stops), trips=len(trips), stop_rows=0,
                  untimed_rows=0, partially_timed_rows=0, untimed_trips=0,
                  adjacent_links=0, fully_timed_links=0, loop_trips=0,
                  repeated_stop_visits=0, duplicate_sequences=0,
                  orphan_stop_references=0, duplicate_stop_ids=0,
                  blank_stop_ids=0, invalid_stop_sequences=0,
                  out_of_order_stop_sequences=0)
    counts['duplicate_stop_ids'] = len(stops) - len(known)
    counts['blank_stop_ids'] = sum(not str(s.get('id', '')).strip() for s in stops)
    for trip in trips:
        rows = trip.get('stops', [])
        counts['stop_rows'] += len(rows)
        seen_stops = set()
        seen_sequences = set()
        has_untimed = False
        has_loop = False
        last_valid_sequence = None
        for row in rows:
            stop_id = str(row.get('stop', '')).strip()
            sequence = str(row.get('seq', '')).strip()
            arrival = str(row.get('arr') or '').strip()
            departure = str(row.get('dep') or '').strip()
            if not arrival and not departure:
                counts['untimed_rows'] += 1
                has_untimed = True
            elif not arrival or not departure:
                counts['partially_timed_rows'] += 1
            if not stop_id or stop_id not in known:
                counts['orphan_stop_references'] += 1
            if stop_id in seen_stops:
                counts['repeated_stop_visits'] += 1
                has_loop = True
            seen_stops.add(stop_id)
            if sequence in seen_sequences:
                counts['duplicate_sequences'] += 1
            seen_sequences.add(sequence)
            # Stop sequence is the trip-specific visit identity; a missing,
            # noninteger, or descending value can silently corrupt transfers.
            if not sequence.isascii() or not sequence.isdecimal() or int(sequence) <= 0:
                counts['invalid_stop_sequences'] += 1
            else:
                current_sequence = int(sequence)
                if last_valid_sequence is not None and current_sequence < last_valid_sequence:
                    counts['out_of_order_stop_sequences'] += 1
                last_valid_sequence = current_sequence
        counts['untimed_trips'] += int(has_untimed)
        counts['loop_trips'] += int(has_loop)
        for earlier, later in zip(rows, rows[1:]):
            counts['adjacent_links'] += 1
            if earlier.get('dep') and later.get('arr'):
                counts['fully_timed_links'] += 1
    counts['time_incomplete_links'] = (counts['adjacent_links'] -
                                       counts['fully_timed_links'])
    counts['exact_departures_certified'] = False
    counts['live_arrivals_certified'] = False
    return counts


def main():
    stops = json.loads((ROOT / 'data/coast-rta-stops.json').read_text())
    journeys = json.loads((ROOT / 'data/coast-rta-journeys.json').read_text())
    result = audit_snapshot(stops, journeys)
    print(json.dumps(result, sort_keys=True, indent=2))
    blockers = ('orphan_stop_references', 'duplicate_sequences', 'duplicate_stop_ids',
                'blank_stop_ids', 'invalid_stop_sequences', 'out_of_order_stop_sequences')
    if any(result[field] for field in blockers):
        raise SystemExit('FAIL: stop inventory ID or trip stop-sequence integrity')
    if result['untimed_rows'] or result['time_incomplete_links']:
        print('SAFETY: missing times are NOT verified departures or transfers.')
    if result['loop_trips']:
        print('SAFETY: repeated stop IDs require trip-specific stop sequence.')


if __name__ == '__main__':
    main()
