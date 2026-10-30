"""Read-only route/direction/service and trip-ID drift audit for official Coast RTA GTFS.

This does not verify a service date, departure, transfer, walk or live arrival.
GTFS direction_id is optional and is not a compass direction.
"""
from collections import Counter


def compare_route_direction_coverage(official_routes, official_trips, stored_trips):
    """Compare official trip route/direction/headsign/service with stored snapshot."""
    names = {
        str(row.get("route_id", "")).strip():
        str(row.get("route_short_name") or row.get("route_long_name") or row.get("route_id") or "").strip()
        for row in official_routes if str(row.get("route_id", "")).strip()
    }

    def direction(value):
        value = str(value if value is not None else "").strip()
        return value if value else "(unspecified)"

    official, stored = {}, {}
    unknown_routes = 0
    for row in official_trips:
        tid = str(row.get("trip_id", "")).strip()
        route_id = str(row.get("route_id", "")).strip()
        if not tid:
            continue
        if route_id not in names:
            unknown_routes += 1
            continue
        if tid not in official:
            official[tid] = (
                names[route_id], direction(row.get("direction_id")),
                str(row.get("trip_headsign") or "").strip(),
                str(row.get("service_id") or "").strip()
            )
    for row in stored_trips:
        tid = str(row.get("id", "")).strip()
        if tid and tid not in stored:
            stored[tid] = (
                str(row.get("route") or "").strip(),
                direction(row.get("direction")),
                str(row.get("headsign") or "").strip(),
                str(row.get("service") or "").strip()
            )

    official_pairs = {(fields[0], fields[1]) for fields in official.values()}
    stored_pairs = {(fields[0], fields[1]) for fields in stored.values()}
    common = sorted(official.keys() & stored.keys())
    mismatches = [
        {"trip_id": tid, "official_route": official[tid][0],
         "stored_route": stored[tid][0], "official_direction": official[tid][1],
         "stored_direction": stored[tid][1]}
        for tid in common if official[tid][:2] != stored[tid][:2]
    ]
    service_changes = [
        {"trip_id": tid, "official_service_id": official[tid][3],
         "stored_service_id": stored[tid][3]}
        for tid in common if official[tid][3] != stored[tid][3]
    ]
    headsign_changes = [
        {"trip_id": tid, "official_headsign": official[tid][2],
         "stored_headsign": stored[tid][2]}
        for tid in common if official[tid][2] != stored[tid][2]
    ]
    def examples(pairs):
        return [{"route": route, "direction_id": dr} for route, dr in sorted(pairs)[:20]]

    return {
        "status": "read_only_route_direction_and_trip_identity_audit",
        "official_unique_trip_ids": len(official),
        "stored_unique_trip_ids": len(stored),
        "unknown_official_route_references": unknown_routes,
        "duplicate_official_trip_ids": sum(n - 1 for n in Counter(
            str(t.get("trip_id", "")).strip() for t in official_trips
            if str(t.get("trip_id", "")).strip()).values() if n > 1),
        "duplicate_stored_trip_ids": sum(n - 1 for n in Counter(
            str(t.get("id", "")).strip() for t in stored_trips
            if str(t.get("id", "")).strip()).values() if n > 1),
        "official_route_direction_pairs": len(official_pairs),
        "stored_route_direction_pairs": len(stored_pairs),
        "official_only_pair_count": len(official_pairs - stored_pairs),
        "official_only_pair_examples": examples(official_pairs - stored_pairs),
        "stored_only_pair_count": len(stored_pairs - official_pairs),
        "stored_only_pair_examples": examples(stored_pairs - official_pairs),
        "official_only_trip_count": len(official.keys() - stored.keys()),
        "official_only_trip_examples": sorted(official.keys() - stored.keys())[:20],
        "stored_only_trip_count": len(stored.keys() - official.keys()),
        "stored_only_trip_examples": sorted(stored.keys() - official.keys())[:20],
        "shared_trip_route_direction_mismatch_count": len(mismatches),
        "shared_trip_route_direction_mismatch_examples": mismatches[:20],
        "shared_trip_service_id_mismatch_count": len(service_changes),
        "shared_trip_service_id_mismatch_examples": service_changes[:20],
        "official_missing_service_id_trip_count": sum(not x[3] for x in official.values()),
        "stored_missing_service_id_trip_count": sum(not x[3] for x in stored.values()),
        "shared_trip_headsign_change_count": len(headsign_changes),
        "shared_trip_headsign_change_examples": headsign_changes[:20],
        "official_unspecified_direction_trip_count": sum(
            fields[1] == "(unspecified)" for fields in official.values()),
        "stored_unspecified_direction_trip_count": sum(
            fields[1] == "(unspecified)" for fields in stored.values()),
        "schedule_times_verified": False,
        "safe_walking_routes_verified": False,
        "live_arrivals_verified": False,
    }
