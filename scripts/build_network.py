#!/usr/bin/env python3
"""Generate a directed Coast RTA graph from existing GTFS-derived JSON. No walking paths inferred."""
import json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(stops_data, journeys_data):
    stops=stops_data["stops"]
    nodes={}
    for s in stops:
        if s["id"] in nodes: raise ValueError("Duplicate stop "+s["id"])
        lat,lon=float(s["lat"]),float(s["lon"])
        if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError("Invalid coordinates "+s["id"])
        nodes[s["id"]]={"id":s["id"],"name":s["name"],"lat":lat,"lon":lon,"routes":set()}
    edges=defaultdict(list)
    for trip in journeys_data["trips"]:
        ordered=sorted(trip["stops"],key=lambda x:int(x["seq"]))
        for stop in ordered:
            if stop["stop"] not in nodes: raise ValueError("Unknown stop "+stop["stop"])
            nodes[stop["stop"]]["routes"].add(trip["route"])
        for a,b in zip(ordered,ordered[1:]):
            edges[a["stop"]].append({"to":b["stop"],"trip":trip["id"],"route":trip["route"],"service":trip["service"],"direction":trip.get("direction",""),"headsign":trip.get("headsign",""),"departure":a.get("dep",""),"arrival":b.get("arr",""),"from_seq":a["seq"],"to_seq":b["seq"],"times_complete":bool(a.get("dep") and b.get("arr"))})
    return {"schema":1,"source":journeys_data.get("source"),"note":"Directed scheduled trip-order links only. Blank times are unknown. No pedestrian accessibility verified.","stop_count":len(nodes),"trip_count":len(journeys_data["trips"]),"nodes":[{**v,"routes":sorted(v["routes"])} for v in nodes.values()],"edges":dict(edges),"calendar":journeys_data["calendar"],"exceptions":journeys_data.get("exceptions",[])}
def main():
    stops=json.loads((ROOT/"data/coast-rta-stops.json").read_text())
    journeys=json.loads((ROOT/"data/coast-rta-journeys.json").read_text())
    graph=build(stops,journeys)
    path=ROOT/"data/coast-rta-network.json"
    path.write_text(json.dumps(graph,separators=(",",":"))+"\n")
    print("Built",len(graph["nodes"]),"stops and",sum(map(len,graph["edges"].values())),"directed trip links")
if __name__=="__main__":main()
