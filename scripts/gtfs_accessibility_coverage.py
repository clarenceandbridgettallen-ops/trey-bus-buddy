"""Read-only GTFS accessibility metadata coverage diagnostic.

A vehicle-level or stop-level wheelchair flag does NOT verify an accessible
pedestrian approach, correct boarding side, or suitability for an individual.
"""
from collections import Counter


def _classify(value):
    raw = str(value if value is not None else "").strip()
    return {"": "unknown", "0": "unknown", "1": "accessible_flag", "2": "inaccessible_flag"}.get(raw, "invalid_flag")


def _summarize(rows, column):
    counts = Counter(_classify(row.get(column)) for row in rows)
    examples = sorted({str(row.get(column)).strip() for row in rows
                       if _classify(row.get(column)) == "invalid_flag"})[:5]
    return {"records": len(rows), "field_present": any(column in row for row in rows),
            "unknown": counts["unknown"],
            "accessible_flag": counts["accessible_flag"],
            "inaccessible_flag": counts["inaccessible_flag"],
            "invalid_flag": counts["invalid_flag"],
            "invalid_examples": examples}


def audit_gtfs_accessibility(stops, trips, feed_files):
    """Return counts, never an accessible-route or vehicle-arrival certification."""
    files = {str(name).rsplit("/", 1)[-1] for name in feed_files}
    boarding_stops = [row for row in stops
                      if str(row.get("location_type") or "0").strip() in ("", "0")]
    stop_flags = _summarize(boarding_stops, "wheelchair_boarding")
    trip_flags = _summarize(trips, "wheelchair_accessible")
    return {
        "official_stop_rows": len(stops),
        "boarding_stop_rows": len(boarding_stops),
        "non_boarding_location_rows": len(stops) - len(boarding_stops),
        "boarding_stop_wheelchair_flags": stop_flags,
        "trip_wheelchair_flags": trip_flags,
        "pathways_file_present": "pathways.txt" in files,
        "transfers_file_present": "transfers.txt" in files,
        "levels_file_present": "levels.txt" in files,
        "accessible_pedestrian_path_verified": False,
        "boarding_side_verified": False,
        "actual_vehicle_accessibility_verified": False,
        "note": "Unknown/blank flags do not mean accessible. Flags do not certify sidewalks, crossings, stop sides, or a complete journey."
    }
