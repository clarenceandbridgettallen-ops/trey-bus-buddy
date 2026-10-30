"""Read-only parity audit for GTFS weekly calendars and dated exceptions.

Comparing trip service IDs alone cannot detect changed weekday flags, service
date ranges, or holiday exceptions. This audit never certifies departures.
"""
from collections import Counter, defaultdict
from datetime import datetime

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
WEEKLY_FIELDS = ("start_date", "end_date") + WEEKDAYS
EXCEPTION_FIELDS = ("date", "exception_type")


def _date(value):
    try:
        return datetime.strptime(str(value or "").strip(), "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def _group(rows, fields):
    groups = defaultdict(Counter)
    missing_ids = 0
    invalid = 0
    for row in rows:
        sid = str(row.get("service_id") or "").strip()
        if not sid:
            missing_ids += 1
            continue
        key = tuple(str(row.get(field) or "").strip() for field in fields)
        groups[sid][key] += 1
        if fields == WEEKLY_FIELDS:
            start, end = _date(key[0]), _date(key[1])
            if start is None or end is None or end < start or any(v not in ("0", "1") for v in key[2:]):
                invalid += 1
        else:
            if _date(key[0]) is None or key[1] not in ("1", "2"):
                invalid += 1
    return groups, missing_ids, invalid


def compare_calendar_coverage(official_calendar, official_exceptions,
                              stored_calendar, stored_exceptions):
    """Report exact row drift without deciding whether any trip can be boarded."""
    oc, oc_missing, oc_invalid = _group(official_calendar, WEEKLY_FIELDS)
    sc, sc_missing, sc_invalid = _group(stored_calendar, WEEKLY_FIELDS)
    oe, oe_missing, oe_invalid = _group(official_exceptions, EXCEPTION_FIELDS)
    se, se_missing, se_invalid = _group(stored_exceptions, EXCEPTION_FIELDS)
    shared = oc.keys() & sc.keys()
    changed = sorted(sid for sid in shared if oc[sid] != sc[sid])
    exception_added = sum(sum((oe[sid] - se.get(sid, Counter())).values()) for sid in oe)
    exception_removed = sum(sum((se[sid] - oe.get(sid, Counter())).values()) for sid in se)
    return {
        "status": "read_only_calendar_and_exception_parity_not_service_certification",
        "official_calendar_rows": len(official_calendar),
        "stored_calendar_rows": len(stored_calendar),
        "official_exception_rows": len(official_exceptions),
        "stored_exception_rows": len(stored_exceptions),
        "official_only_service_ids": sorted(oc.keys() - sc.keys())[:20],
        "official_only_service_id_count": len(oc.keys() - sc.keys()),
        "stored_only_service_ids": sorted(sc.keys() - oc.keys())[:20],
        "stored_only_service_id_count": len(sc.keys() - oc.keys()),
        "changed_weekly_service_id_count": len(changed),
        "changed_weekly_service_id_examples": changed[:20],
        "official_only_exception_row_count": exception_added,
        "stored_only_exception_row_count": exception_removed,
        "official_missing_calendar_service_ids": oc_missing,
        "stored_missing_calendar_service_ids": sc_missing,
        "official_missing_exception_service_ids": oe_missing,
        "stored_missing_exception_service_ids": se_missing,
        "official_invalid_calendar_rows": oc_invalid,
        "stored_invalid_calendar_rows": sc_invalid,
        "official_invalid_exception_rows": oe_invalid,
        "stored_invalid_exception_rows": se_invalid,
        "schedule_times_verified": False,
        "holiday_service_verified": False,
        "safe_walking_routes_verified": False,
    }
