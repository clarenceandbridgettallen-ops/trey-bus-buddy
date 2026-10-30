"""Read-only trip-headsign parity audit; never certifies a physical bus sign."""
from collections import Counter


def _index(rows, id_key, label_key):
    values = {}
    counts = Counter()
    malformed = 0
    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            continue
        trip_id = str(row.get(id_key) or "").strip()
        if not trip_id:
            malformed += 1
            continue
        counts[trip_id] += 1
        label = " ".join(str(row.get(label_key) or "").split())
        values[trip_id] = label
    return values, counts, malformed


def compare_headsign_coverage(official_trips, stored_trips):
    """Compare GTFS trip_headsign to stored headsign, not actual vehicle displays."""
    official, official_counts, official_bad = _index(official_trips, "trip_id", "trip_headsign")
    stored, stored_counts, stored_bad = _index(stored_trips, "id", "headsign")
    shared = official.keys() & stored.keys()
    changed = sorted(t for t in shared if official[t] != stored[t])
    newly_available = sorted(t for t in shared if official[t] and not stored[t])
    return {
        "status": "read_only_headsign_parity_not_physical_bus_sign_verification",
        "official_trip_count": len(official),
        "stored_trip_count": len(stored),
        "official_blank_headsign_count": sum(not s for s in official.values()),
        "stored_blank_headsign_count": sum(not s for s in stored.values()),
        "changed_headsign_count": len(changed),
        "changed_headsign_trip_examples": changed[:20],
        "official_filled_stored_blank_count": len(newly_available),
        "official_filled_stored_blank_examples": newly_available[:20],
        "official_only_trip_count": len(official.keys() - stored.keys()),
        "stored_only_trip_count": len(stored.keys() - official.keys()),
        "official_duplicate_trip_count": sum(n > 1 for n in official_counts.values()),
        "stored_duplicate_trip_count": sum(n > 1 for n in stored_counts.values()),
        "official_malformed_trip_rows": official_bad,
        "stored_malformed_trip_rows": stored_bad,
        "vehicle_destination_signs_verified": False,
        "safe_boarding_side_verified": False,
    }
