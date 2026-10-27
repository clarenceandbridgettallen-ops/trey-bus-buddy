#!/usr/bin/env python3
"""Fetch Coast RTA GTFS and cross-check published stop IDs against tracker pages."""
import csv,io,json,os,re,urllib.request,zipfile,datetime,html
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
FEED="https://coastrta.transloc.com/Secure/Admin/Reports/GTFSDownload.aspx"
TRACKER="https://coastrta.transloc.com/routes/78/stops"
VEHICLES="https://coastrta.transloc.com/subscriptions/gtfsrt/vehicles.ashx"
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"BusBuddyStopAudit/1.0 (public GTFS research)"})
 with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def main():
 raw=get(FEED)
 if not zipfile.is_zipfile(io.BytesIO(raw)):raise RuntimeError("Coast RTA feed did not return a valid ZIP")
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names={n.rsplit("/",1)[-1]:n for n in z.namelist()}
  required=["stops.txt","routes.txt","trips.txt","stop_times.txt"]
  if any(n not in names for n in required):raise RuntimeError("GTFS missing required files")
  def rows(n):return list(csv.DictReader(io.TextIOWrapper(z.open(names[n]),encoding="utf-8-sig")))
  stop_rows=rows("stops.txt");route_rows=rows("routes.txt");trips=rows("trips.txt");times=rows("stop_times.txt")
  calendars=rows("calendar.txt") if "calendar.txt" in names else []
  exceptions=rows("calendar_dates.txt") if "calendar_dates.txt" in names else []
  routes={r["route_id"]:r.get("route_short_name","") or r.get("route_long_name","") for r in route_rows}
  trip_routes={t["trip_id"]:routes.get(t["route_id"],t["route_id"]) for t in trips}
  trip_details={t["trip_id"]:{"route":routes.get(t["route_id"],t["route_id"]),"service":t.get("service_id",""),"headsign":t.get("trip_headsign",""),"direction":t.get("direction_id","")} for t in trips}
  journey_trips={}
  for t in times:
   tid=t.get("trip_id","")
   if tid in trip_details:
    journey_trips.setdefault(tid,[]).append({"stop":t.get("stop_id",""),"seq":int(t.get("stop_sequence") or 0),"arr":t.get("arrival_time",""),"dep":t.get("departure_time","")})
  journey=[{"id":tid,**trip_details[tid],"stops":sorted(rows,key=lambda x:x["seq"])} for tid,rows in journey_trips.items() if len(rows)>=2]
  ROOT.joinpath("data/coast-rta-journeys.json").write_text(json.dumps({"source":FEED,"downloaded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"trips":journey,"calendar":calendars,"exceptions":exceptions},ensure_ascii=False,separators=(",",":")))
  stop_routes={}
  for t in times:
   route=trip_routes.get(t.get("trip_id"))
   if route:stop_routes.setdefault(t["stop_id"],set()).add(route)
  stops=[]
  for s in stop_rows:
   try:lat=float(s["stop_lat"]);lon=float(s["stop_lon"])
   except (KeyError,TypeError,ValueError):continue
   if not(-90<=lat<=90 and -180<=lon<=180):continue
   stops.append({"id":s["stop_id"],"name":s.get("stop_name",""),"lat":lat,"lon":lon,"routes":sorted(stop_routes.get(s["stop_id"],[]))})
  if len(stops)<50:raise RuntimeError("Suspiciously small GTFS stop count: "+str(len(stops)))
  ROOT.joinpath("data").mkdir(exist_ok=True)
  ROOT.joinpath("data/coast-rta-stops.json").write_text(json.dumps({"source":FEED,"downloaded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"count":len(stops),"stops":stops},ensure_ascii=False,separators=(",",":")))
  audit={"downloaded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"gtfs_stop_count":len(stops),"gtfs_routes":len(routes),"tracker_route_15s_url":TRACKER,"tracker_status":"not_checked","tracker_matching_stop_ids":[],"tracker_missing_stop_ids":[]}
  try:
   vehicle_data=get(VEHICLES)
   audit["vehicle_feed"]={"reachable":True,"bytes":len(vehicle_data),"protobuf_likely":bool(len(vehicle_data)>=32 and vehicle_data[:1]!=b"<" and any(b<9 or b>126 for b in vehicle_data[:128])),"decoded":False,"live_arrivals_verified":False}
  except Exception as e:audit["vehicle_feed"]={"reachable":False,"error":str(e)}
  try:
   page=get(TRACKER).decode("utf-8","replace")
   audit["tracker_status"]="retrieved"
   # Only compare canonical GTFS-style IDs. Parenthesized numbers are not
   # necessarily GTFS stop IDs and cannot safely be called missing stops.
   decoded=html.unescape(page)
   ids={v.upper() for v in re.findall(r"\bTL-\d+\b",decoded,flags=re.I)}
   gtfs_ids={str(s["id"]).upper() for s in stops}
   audit["tracker_matching_stop_ids"]=sorted(ids & gtfs_ids)
   audit["tracker_missing_stop_ids"]=sorted(ids-gtfs_ids)
   audit["tracker_unverified_numeric_labels_count"]=len(set(re.findall(r"\((\d{1,5})\)",html.unescape(re.sub(r"<[^>]+>"," ",page)))))
   audit["tracker_status"]="partial_canonical_id_comparison" if ids else "page_retrieved_no_canonical_ids_extracted"
  except Exception as e:audit["tracker_status"]="unavailable: "+str(e)
  ROOT.joinpath("data/stop-audit.json").write_text(json.dumps(audit,indent=2))
  print(json.dumps(audit,indent=2))
if __name__=="__main__":main()
