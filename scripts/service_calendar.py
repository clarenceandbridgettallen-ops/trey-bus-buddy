"""Conservative, read-only GTFS calendar classification for Bus Buddy audits.

No clock times or vehicle arrivals are generated. Unknown/conflicting data remains
unknown rather than being treated as a service that is safe to board.
"""
from datetime import datetime

WEEKDAYS = ('monday','tuesday','wednesday','thursday','friday','saturday','sunday')


def audit_frequency_service_date(frequencies, trips, calendar, exceptions, service_date):
    """Classify frequency rows as active, inactive or uncertain for YYYYMMDD.

    Calendar exceptions override weekly rules. Duplicate contradictory calendar
    records or exceptions are uncertain, never guessed active.
    """
    day = datetime.strptime(service_date, '%Y%m%d').date()
    base = {}
    bad_calendar = 0
    for row in calendar:
        sid = str(row.get('service_id', '')).strip()
        try:
            start = datetime.strptime(str(row.get('start_date', '')), '%Y%m%d').date()
            end = datetime.strptime(str(row.get('end_date', '')), '%Y%m%d').date()
            flags = [str(row.get(w, '')).strip() for w in WEEKDAYS]
            if not sid or end < start or any(f not in ('0','1') for f in flags):
                raise ValueError('invalid weekly calendar')
        except (ValueError, TypeError):
            bad_calendar += 1
            if sid:
                base[sid] = None
            continue
        status = start <= day <= end and flags[day.weekday()] == '1'
        if sid in base and base[sid] != status:
            base[sid] = None
        else:
            base.setdefault(sid, status)
    overrides = {}
    bad_exceptions = 0
    for row in exceptions:
        sid = str(row.get('service_id', '')).strip()
        try:
            exception_day = datetime.strptime(str(row.get('date', '')), '%Y%m%d').date()
            kind = str(row.get('exception_type', '')).strip()
            if not sid or kind not in ('1','2'):
                raise ValueError('invalid calendar exception')
        except (ValueError, TypeError):
            bad_exceptions += 1
            if sid:
                overrides[sid] = None
            continue
        if exception_day != day:
            continue
        status = kind == '1'
        if sid in overrides and overrides[sid] != status:
            overrides[sid] = None
        else:
            overrides.setdefault(sid, status)
    counts = {'active': 0, 'inactive': 0, 'uncertain': 0}
    unknown = set()
    affected = set()
    for row in frequencies:
        trip_id = str(row.get('trip_id', '')).strip()
        trip = trips.get(trip_id)
        if not trip:
            counts['uncertain'] += 1
            unknown.add('(unknown trip: '+trip_id+')')
            continue
        sid = str(trip.get('service', '')).strip()
        affected.add(sid)
        status = overrides.get(sid, base.get(sid))
        if status is None:
            counts['uncertain'] += 1
            unknown.add(sid)
        elif status:
            counts['active'] += 1
        else:
            counts['inactive'] += 1
    return {
        'service_date': service_date,
        'frequency_rows': len(frequencies),
        'active_rows': counts['active'],
        'inactive_rows': counts['inactive'],
        'uncertain_rows': counts['uncertain'],
        'frequency_service_ids': len(affected),
        'uncertain_service_ids': sorted(unknown)[:20],
        'invalid_calendar_rows': bad_calendar,
        'invalid_exception_rows': bad_exceptions,
        'status': 'diagnostic_only_not_departure_times',
    }
