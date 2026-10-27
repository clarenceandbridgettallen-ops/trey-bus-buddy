#!/usr/bin/env python3
"""Bus Buddy offline GTFS integrity and connectivity audit. Run: python3 scripts/audit_journeys.py"""
import json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
stops=json.loads((ROOT/"data/coast-rta-stops.json").read_text())["stops"]
data=json.loads((ROOT/"data/coast-rta-journeys.json").read_text())
ids={s["id"] for s in stops}
issues=[]
edges=defaultdict(set)
routes=defaultdict(set)
for trip in data["trips"]:
    sequence=trip.get("stops",[])
    if len(sequence)<2:issues.append(f"Trip {trip['id']} has fewer than 2 stops")
    for entry in sequence:
        if entry["stop"] not in ids:issues.append(f"Unknown stop {entry['stop']} in {trip['id']}")
        routes[entry["stop"]].add(trip["route"])
    for a,b in zip(sequence,sequence[1:]):
        edges[a["stop"]].add(b["stop"])
services={c["service_id"] for c in data["calendar"]}
for t in data["trips"]:
    if t["service"] not in services:issues.append(f"Trip {t['id']} has missing calendar {t['service']}")
print(f"Stops: {len(stops)}; trips: {len(data['trips'])}; calendars: {len(services)}")
print(f"Stops with scheduled trip coverage: {len(routes)}; stops without trip coverage: {len(ids-set(routes))}")
print(f"Stop-to-stop directed links: {sum(map(len,edges.values()))}")
trip_links=sum(max(0,len(t["stops"])-1) for t in data["trips"])
published_time_links=sum(
    bool(a.get("dep") and b.get("arr"))
    for t in data["trips"]
    for a,b in zip(t["stops"],t["stops"][1:])
)
print(f"Trip-sequence links: {trip_links}; links with both published endpoint times: {published_time_links}; time-incomplete links: {trip_links-published_time_links}")
if published_time_links<trip_links:
    print("NOTICE: Time-incomplete links are route-order evidence, NOT verified scheduled stop-to-stop travel times.")
print(f"Integrity issues: {len(issues)}")
for issue in issues[:30]:print("ERROR:",issue)
if issues:raise SystemExit(1)
