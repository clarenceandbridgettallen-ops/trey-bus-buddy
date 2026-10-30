#!/usr/bin/env python3
"""Fetch Coast RTA GTFS and cross-check published stop IDs against tracker pages."""
import csv,io,json,os,re,urllib.request,zipfile,datetime,html
from pathlib import Path
from zoneinfo import ZoneInfo
from service_calendar import audit_frequency_service_date
from frequency_windows import audit_frequency_boarding_windows, audit_frequency_anchor_order
from audit_real_transfer_pairs import audit_real_transfer_pairs
from route_direction_coverage import compare_route_direction_coverage
from calendar_coverage import compare_calendar_coverage
from headsign_coverage import compare_headsign_coverage
ROOT=Path(__file__).resolve().parent.parent
FEED="https://coastrta.transloc.com/Secure/Admin/Reports/GTFSDownload.aspx"
TRACKER="https://coastrta.transloc.com/routes/78/stops"
VEHICLES="https://coastrta.transloc.com/subscriptions/gtfsrt/vehicles.ashx"
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"BusBuddyStopAudit/1.0 (public GTFS research)"})
 with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def gtfs_seconds(value):
 m=re.fullmatch(r'(\d+):([0-5]\d):([0-5]\d)',str(value or '').strip())
 return (int(m.group(1))*3600+int(m.group(2))*60+int(m.group(3))) if m else None

def inspect_frequency_windows(rows,trip_ids):
 """Diagnostic only: validate headway windows without producing departure times."""
 modes={};headways=[];intervals={};issues=[];missing=set();first=[];last=[]
 for index,row in enumerate(rows,1):
  trip=str(row.get('trip_id','')).strip()
  mode=str(row.get('exact_times','')).strip() or '0'
  modes[mode]=modes.get(mode,0)+1
  if trip not in trip_ids:missing.add(trip)
  start=gtfs_seconds(row.get('start_time'))
  end=gtfs_seconds(row.get('end_time'))
  try:headway=int(row.get('headway_secs',''))
  except (ValueError,TypeError):headway=0
  if mode not in ('0','1') or start is None or end is None or end<=start or headway<=0:
   issues.append(index)
   continue
  headways.append(headway);first.append(start);last.append(end)
  intervals.setdefault(trip,[]).append((start,end,index))
 overlaps=[]
 for trip,windows in intervals.items():
  windows.sort()
  # Adjacent-only comparisons miss nested windows (e.g. 08-12, 09-10, 10-11).
  # Track every still-open interval to report all overlapping pairs.
  active=[]
  for start,end,index in windows:
   active=[(prior_end,prior_index) for prior_end,prior_index in active if prior_end>start]
   overlaps.extend([trip,prior_index,index] for prior_end,prior_index in active)
   active.append((end,index))
 return {'exact_times_modes':modes,'headway_secs_min':min(headways) if headways else None,
         'headway_secs_max':max(headways) if headways else None,
         'window_start_earliest_secs':min(first) if first else None,
         'window_end_latest_secs':max(last) if last else None,
         'invalid_row_numbers':issues[:20], 'invalid_row_count':len(issues),
         'overlapping_trip_windows':overlaps[:20], 'overlap_count':len(overlaps),
         'unknown_trip_ids':sorted(missing)[:20], 'unknown_trip_count':len(missing)}

def summarize_frequency_routes(rows, trip_details):
 """Read-only agency frequency coverage by route and service; no departures inferred."""
 by_route={}
 for row in rows:
  trip_id=str(row.get("trip_id","")).strip()
  trip=trip_details.get(trip_id)
  if not trip:continue
  route=str(trip.get("route","") or "(unnamed route)")
  entry=by_route.setdefault(route,{"rows":0,"trips":set(),"services":set(),"modes":{}})
  entry["rows"]+=1
  entry["trips"].add(trip_id)
  entry["services"].add(str(trip.get("service","")))
  mode=str(row.get("exact_times","")).strip() or "0"
  entry["modes"][mode]=entry["modes"].get(mode,0)+1
 result=[]
 for route,entry in sorted(by_route.items()):
  result.append({"route":route,"frequency_rows":entry["rows"],
                 "unique_trip_ids":len(entry["trips"]),
                 "service_ids":sorted(entry["services"]),
                 "exact_times_modes":entry["modes"]})
 return {"affected_routes":len(result),"routes":result}



def inspect_frequency_templates(frequency_rows, trip_details, stop_times, calendars, exceptions):
 """Read-only: identify whether frequency trip templates contain usable stop-time offsets."""
 referenced={str(row.get("trip_id","")).strip() for row in frequency_rows}
 known=referenced & set(trip_details)
 by_trip={}
 for row in stop_times:
  tid=str(row.get("trip_id","")).strip()
  if tid in known:by_trip.setdefault(tid,[]).append(row)
 services={str(row.get("service_id","")).strip() for row in calendars+exceptions}
 missing_stops=[];missing_anchor=[];entirely_untimed=[];unknown_services=[]
 missing_anchor_details=[]
 def timed(stop):
  return bool(str(stop.get("arrival_time","")).strip() or str(stop.get("departure_time","")).strip())
 for tid in sorted(known):
  stops=sorted(by_trip.get(tid,[]),key=lambda r:int(r.get("stop_sequence") or 0))
  if len(stops)<2:missing_stops.append(tid)
  if not stops or not timed(stops[0]):
   missing_anchor.append(tid)
   first_timed=next(((i,stop) for i,stop in enumerate(stops) if timed(stop)),None)
   initial=stops[0] if stops else {}
   later=first_timed[1] if first_timed else {}
   missing_anchor_details.append({
    "trip_id":tid,"route":trip_details[tid].get("route",""),
    "service_id":trip_details[tid].get("service",""),
    "first_stop_id":initial.get("stop_id",""),
    "first_stop_sequence":initial.get("stop_sequence",""),
    "first_stop_pickup_type":initial.get("pickup_type",""),
    "first_stop_timepoint":initial.get("timepoint",""),
    "leading_untimed_stops":first_timed[0] if first_timed else len(stops),
    "first_timed_stop_id":later.get("stop_id",""),
    "first_timed_stop_sequence":later.get("stop_sequence",""),
    "first_timed_stop_time":later.get("departure_time") or later.get("arrival_time") or ""
   })
  if not any(timed(s) for s in stops):
   entirely_untimed.append(tid)
  if str(trip_details[tid].get("service","")).strip() not in services:unknown_services.append(tid)
 def summary(ids):return {"count":len(ids),"example_trip_ids":ids[:10]}
 return {"known_frequency_trip_templates":len(known),
         "fewer_than_two_stops":summary(missing_stops),
         "missing_first_stop_time":summary(missing_anchor),
         "missing_first_stop_details":missing_anchor_details[:10],
         "all_stop_times_blank":summary(entirely_untimed),
         "unresolved_calendar_service":summary(unknown_services)}

def inspect_stop_record_integrity(rows, official=True):
 """Read-only record audit: ID parity can conceal duplicates or unusable coordinates.

 Counts refer to raw GTFS/snapshot rows, not verified physical boarding stops.
 Some non-platform GTFS location types may legitimately omit coordinates.
 """
 import math
 from collections import Counter
 id_field="stop_id" if official else "id"
 lat_field="stop_lat" if official else "lat"
 lon_field="stop_lon" if official else "lon"
 ids=[];missing_id_rows=0;unusable_coordinates=[]
 for index,row in enumerate(rows,1):
  sid=str(row.get(id_field,"") or "").strip()
  if sid:ids.append(sid)
  else:missing_id_rows+=1
  try:
   lat=float(row.get(lat_field))
   lon=float(row.get(lon_field))
   usable=math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180
  except (ValueError,TypeError):
   usable=False
  if not usable:unusable_coordinates.append({"row":index,"id":sid})
 counts=Counter(ids)
 duplicates=sorted(sid for sid,n in counts.items() if n>1)
 return {"raw_rows":len(rows),"distinct_nonempty_ids":len(counts),
         "missing_id_rows":missing_id_rows,
         "duplicate_id_count":len(duplicates),"duplicate_ids":duplicates[:20],
         "unusable_coordinate_rows":len(unusable_coordinates),
         "unusable_coordinate_examples":unusable_coordinates[:20]}


def compare_stop_inventory(official_rows, stored_rows):
 """Read-only comparison of official GTFS stop IDs against published snapshot.

 Counts describe data records, not verified physical bus stops or walking access.
 """
 import math
 def valid(rows, official):
  found={}
  for row in rows:
   sid=str(row.get("stop_id" if official else "id","")).strip()
   try:
    lat=float(row.get("stop_lat" if official else "lat"))
    lon=float(row.get("stop_lon" if official else "lon"))
   except (ValueError,TypeError):continue
   if sid and -90<=lat<=90 and -180<=lon<=180:
    found[sid]={"name":str(row.get("stop_name" if official else "name","")).strip(),
                "lat":lat,"lon":lon}
  return found
 new=valid(official_rows,True);old=valid(stored_rows,False)
 added=sorted(set(new)-set(old));removed=sorted(set(old)-set(new))
 moved=[];moved_over_10m=[];renamed=[]
 for sid in sorted(set(new)&set(old)):
  a=new[sid];b=old[sid]
  p1,p2=math.radians(a["lat"]),math.radians(b["lat"])
  dphi=math.radians(b["lat"]-a["lat"])
  dlambda=math.radians(b["lon"]-a["lon"])
  h=math.sin(dphi/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dlambda/2)**2
  meters=6371000*2*math.asin(min(1,math.sqrt(h)))
  if meters>10:moved_over_10m.append({"id":sid,"distance_m":round(meters,1)})
  if meters>100:moved.append({"id":sid,"distance_m":round(meters)})
  if a["name"]!=b["name"]:renamed.append({"id":sid,"old_name":b["name"],"new_name":a["name"]})
 return {"official_valid_stop_ids":len(new),"stored_valid_stop_ids":len(old),
         "new_in_official_feed_count":len(added),"new_in_official_feed_ids":added[:20],
         "not_in_official_feed_count":len(removed),"not_in_official_feed_ids":removed[:20],
         "coordinate_changes_over_10m_count":len(moved_over_10m),
         "coordinate_changes_over_10m":sorted(moved_over_10m,key=lambda x:-x["distance_m"])[:20],
         "coordinate_changes_over_100m_count":len(moved),
         "coordinate_changes_over_100m":moved[:20],
         "name_changes_count":len(renamed),"name_changes":renamed[:20]}


def compare_stop_route_memberships(official_stops, official_routes, official_trips,
                                   official_stop_times, stored_stops):
 """Read-only route membership drift audit; stop ID parity alone is insufficient.

 Route labels follow the published snapshot importer. These are GTFS variants,
 not the agency's public count of fixed routes. No walkability is inferred.
 """
 from collections import defaultdict
 official_ids={str(s.get("stop_id","")).strip() for s in official_stops
               if str(s.get("stop_id","")).strip()}
 stored_ids={str(s.get("id","")).strip() for s in stored_stops
             if str(s.get("id","")).strip()}
 route_names={str(r.get("route_id","")).strip():
              str(r.get("route_short_name","") or r.get("route_long_name","")).strip()
              for r in official_routes if str(r.get("route_id","")).strip()}
 trip_routes={str(t.get("trip_id","")).strip():str(t.get("route_id","")).strip()
              for t in official_trips if str(t.get("trip_id","")).strip()}
 official=defaultdict(set)
 unknown_stops=unknown_trips=unknown_routes=0
 for row in official_stop_times:
  sid=str(row.get("stop_id","")).strip()
  tid=str(row.get("trip_id","")).strip()
  if sid not in official_ids:
   unknown_stops+=1
   continue
  if tid not in trip_routes:
   unknown_trips+=1
   continue
  route=route_names.get(trip_routes[tid])
  if not route:
   unknown_routes+=1
   continue
  official[sid].add(route)
 stored=defaultdict(set)
 for row in stored_stops:
  sid=str(row.get("id","")).strip()
  routes=row.get("routes",[])
  if sid and isinstance(routes,list):
   stored[sid].update(str(route).strip() for route in routes
                      if str(route).strip())
 official_pairs={(sid,route) for sid,routes in official.items() for route in routes}
 stored_pairs={(sid,route) for sid,routes in stored.items() for route in routes}
 added=sorted(official_pairs-stored_pairs)
 removed=sorted(stored_pairs-official_pairs)
 examples=lambda pairs:[{"stop_id":sid,"route":route} for sid,route in pairs[:20]]
 return {
  "status":"read_only_official_gtfs_vs_stored_route_memberships",
  "official_stop_ids":len(official_ids),
  "stored_stop_ids":len(stored_ids),
  "official_stop_ids_missing_from_snapshot":sorted(official_ids-stored_ids)[:20],
  "snapshot_stop_ids_missing_from_official":sorted(stored_ids-official_ids)[:20],
  "official_route_stop_memberships":len(official_pairs),
  "stored_route_stop_memberships":len(stored_pairs),
  "official_only_membership_count":len(added),
  "official_only_membership_examples":examples(added),
  "stored_only_membership_count":len(removed),
  "stored_only_membership_examples":examples(removed),
  "unknown_stop_references":unknown_stops,
  "unknown_trip_references":unknown_trips,
  "unknown_route_references":unknown_routes,
  "safe_walking_routes_verified":False,
  "live_arrivals_verified":False,
 }

def check_frequency_coverage(file_present, frequency_rows, trip_ids):
 """Fail closed when the agency supplies frequency-based trips we cannot schedule safely.

 A GTFS frequency row may represent many departures. Importing its template
 trip as a single scheduled departure would mislead riders.
 """
 if frequency_rows:
  referenced={str(row.get("trip_id","")).strip() for row in frequency_rows}
  matched=len(referenced & set(trip_ids))
  diagnostic={"frequency_rows":len(frequency_rows),"unique_trip_ids":len(referenced),
              "known_trip_ids":matched,"example_trip_ids":sorted(referenced)[:5],
              **inspect_frequency_windows(frequency_rows,set(trip_ids))}
  print("GTFS FREQUENCY BLOCKER "+json.dumps(diagnostic,sort_keys=True),flush=True)
  raise RuntimeError(
   "Coast RTA GTFS frequencies.txt has "+str(len(frequency_rows))+
   " rows referencing "+str(matched)+" known trip IDs. "
   "Bus Buddy cannot yet expand exact_times=1 trips or safely represent "
   "exact_times=0 headways. Refusing to replace the existing published "
   "snapshot; inspect the official ZIP and implement frequency-aware routing first."
  )
 return {"file_present":bool(file_present),"row_count":0,
         "status":"empty" if file_present else "absent"}

def main():
 raw=get(FEED)
 if not zipfile.is_zipfile(io.BytesIO(raw)):raise RuntimeError("Coast RTA feed did not return a valid ZIP")
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names={n.rsplit("/",1)[-1]:n for n in z.namelist()}
  required=["stops.txt","routes.txt","trips.txt","stop_times.txt"]
  if any(n not in names for n in required):raise RuntimeError("GTFS missing required files")
  def rows(n):return list(csv.DictReader(io.TextIOWrapper(z.open(names[n]),encoding="utf-8-sig")))
  stop_rows=rows("stops.txt");route_rows=rows("routes.txt");trips=rows("trips.txt");times=rows("stop_times.txt")
  print("GTFS OFFICIAL STOP RECORD INTEGRITY "+json.dumps(inspect_stop_record_integrity(stop_rows,True),sort_keys=True),flush=True)
  calendars=rows("calendar.txt") if "calendar.txt" in names else []
  exceptions=rows("calendar_dates.txt") if "calendar_dates.txt" in names else []
  routes={r["route_id"]:r.get("route_short_name","") or r.get("route_long_name","") for r in route_rows}
  trip_routes={t["trip_id"]:routes.get(t["route_id"],t["route_id"]) for t in trips}
  trip_details={t["trip_id"]:{"route":routes.get(t["route_id"],t["route_id"]),"service":t.get("service_id",""),"headsign":t.get("trip_headsign",""),"direction":t.get("direction_id","")} for t in trips}
  frequency_rows=rows("frequencies.txt") if "frequencies.txt" in names else []
  snapshot_path=ROOT/"data/coast-rta-stops.json"
  if snapshot_path.exists():
   stored=json.loads(snapshot_path.read_text(encoding="utf-8"))
   print("GTFS STORED STOP RECORD INTEGRITY "+json.dumps(inspect_stop_record_integrity(stored.get("stops",[]),False),sort_keys=True),flush=True)
   comparison=compare_stop_inventory(stop_rows,stored.get("stops",[]))
   print("GTFS STOP INVENTORY COMPARISON "+json.dumps(comparison,sort_keys=True),flush=True)
   route_memberships=compare_stop_route_memberships(stop_rows,route_rows,trips,times,stored.get("stops",[]))
   print("GTFS STOP ROUTE MEMBERSHIP COMPARISON "+json.dumps(route_memberships,sort_keys=True),flush=True)
  else:
   print("GTFS STOP INVENTORY COMPARISON unavailable: no stored snapshot",flush=True)
  journey_snapshot_path=ROOT/"data/coast-rta-journeys.json"
  if journey_snapshot_path.exists():
   stored_journeys=json.loads(journey_snapshot_path.read_text(encoding="utf-8"))
   direction_report=compare_route_direction_coverage(route_rows,trips,stored_journeys.get("trips",[]))
   print("GTFS ROUTE DIRECTION COVERAGE COMPARISON "+json.dumps(direction_report,sort_keys=True),flush=True)
   headsign_report=compare_headsign_coverage(trips,stored_journeys.get("trips",[]))
   print("GTFS TRIP HEADSIGN COVERAGE COMPARISON "+json.dumps(headsign_report,sort_keys=True),flush=True)
   calendar_drift=compare_calendar_coverage(calendars,exceptions,stored_journeys.get("calendar",[]),stored_journeys.get("exceptions",[]))
   print("GTFS CALENDAR AND EXCEPTION PARITY "+json.dumps(calendar_drift,sort_keys=True),flush=True)
  else:
   print("GTFS ROUTE DIRECTION COVERAGE COMPARISON unavailable: no stored journey snapshot",flush=True)
  if frequency_rows:
   print("GTFS FREQUENCY ROUTES "+json.dumps(summarize_frequency_routes(frequency_rows,trip_details),sort_keys=True),flush=True)
   print("GTFS FREQUENCY TEMPLATES "+json.dumps(inspect_frequency_templates(frequency_rows,trip_details,times,calendars,exceptions),sort_keys=True),flush=True)
   print("GTFS FREQUENCY BOARDING WINDOWS "+json.dumps(audit_frequency_boarding_windows(frequency_rows,times),sort_keys=True),flush=True)
   print("GTFS FREQUENCY ANCHOR ORDER "+json.dumps(audit_frequency_anchor_order(frequency_rows,times),sort_keys=True),flush=True)
  if frequency_rows:
   # A date-scoped, read-only service audit; never a claim of exact departures.
   local_day=datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
   calendar_report=audit_frequency_service_date(frequency_rows,trip_details,calendars,exceptions,local_day)
   print("GTFS FREQUENCY SERVICE DAY "+json.dumps(calendar_report,sort_keys=True),flush=True)
   # Read-only QA against real trip IDs and same-stop sequence visits.
   # Never print a departure estimate or publish a rider itinerary.
   pair_report=audit_real_transfer_pairs(frequency_rows,trip_details,times,
                                        calendars,exceptions,local_day,limit=8)
   print("GTFS REAL TRIP PAIR DIAGNOSTIC "+json.dumps(pair_report,sort_keys=True),flush=True)
  frequency_coverage=check_frequency_coverage("frequencies.txt" in names,frequency_rows,set(trip_details))
  print("GTFS frequency coverage: "+json.dumps(frequency_coverage),flush=True)
  journey_trips={}
  for t in times:
   tid=t.get("trip_id","")
   if tid in trip_details:
    journey_trips.setdefault(tid,[]).append({"stop":t.get("stop_id",""),"seq":int(t.get("stop_sequence") or 0),"arr":t.get("arrival_time",""),"dep":t.get("departure_time","")})
  journey=[{"id":tid,**trip_details[tid],"stops":sorted(rows,key=lambda x:x["seq"])} for tid,rows in journey_trips.items() if len(rows)>=2]
  ROOT.joinpath("data/coast-rta-journeys.json").write_text(json.dumps({"source":FEED,"downloaded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"trips":journey,"calendar":calendars,"exceptions":exceptions,"frequency_coverage":{"status":"no_frequency_rows","row_count":0,"file_present":frequency_coverage["file_present"]}},ensure_ascii=False,separators=(",",":")))
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
  audit={"downloaded_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"frequency_coverage":frequency_coverage,"gtfs_stop_count":len(stops),"gtfs_routes":len(routes),"tracker_route_15s_url":TRACKER,"tracker_status":"not_checked","tracker_matching_stop_ids":[],"tracker_missing_stop_ids":[]}
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
