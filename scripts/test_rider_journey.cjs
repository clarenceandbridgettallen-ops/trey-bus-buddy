"use strict";
// Dependency-free source-level mock. NOT a live-browser, Android or walking-safety test.
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),path=require("node:path");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
// Critical route-data and timetable warnings must remain in the accessibility tree.
// Hiding a role=status region with display:none suppresses screen-reader announcements.
assert.match(html, /id="dataStatus"[^>]*role="status"[^>]*aria-live="polite"/);
assert.ok(html.includes("#dataStatus{position:absolute!important;"),"Data status must be visually hidden, not removed from accessibility tree");
assert.ok(!html.includes("#dataStatus{display:none!important}"),"Do not hide safety status from screen readers");
console.log("PASS: Coast RTA data/frequency warnings remain available to screen readers (source-level)");
// GPS reverse lookup and typed destination errors must be announced when their
// asynchronous status text changes, without requiring the rider to find it by touch.
assert.match(html, /id="foundAddress"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/,
 "GPS address readiness must be announced to assistive technology");
assert.match(html, /id="tripStatus"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/,
 "Destination lookup timeouts and no-match messages must be announced");
console.log("PASS: GPS confirmation and destination search status updates are accessible (source-level)");
// The nearest geographic stop is not necessarily a stop served by the rider's planned route.
assert.match(html,/id="findBoarding">SHOW NEARBY STOPS \(NOT TRIP-SPECIFIC\)/);
assert.match(html,/NOT necessarily a stop served by a bus to your destination/);
assert.match(html,/id="goNearest">FIND NEARBY MAPPED STOPS/,"Nearest stop must not promise to take the rider there");
assert.match(html,/id="chooseStop">REVIEW EXTERNAL WALKING DIRECTIONS/,"Walking review must not imply a verified route");
assert.match(html,/Bus Buddy has NOT verified this walking route, accessible sidewalks, crossings, or the boarding side/,"External map warning must disclose unverified pedestrian safety");
console.log("PASS: trip planning does not mislabel nearest mapped stop as a verified route boarding stop");

const committedStops=JSON.parse(fs.readFileSync(path.join(root,"data/coast-rta-stops.json"),"utf8"));
const committedJourneys=JSON.parse(fs.readFileSync(path.join(root,"data/coast-rta-journeys.json"),"utf8"));
// Test clocks are fixed in October 2026. Keep fixture timestamps fixed as well,
// so tomorrow's official GTFS refresh cannot turn a simulated fresh snapshot into
// a >24-hour future-dated one and falsely fail otherwise valid rider regressions.
const stopStamp=Date.parse(committedStops.downloaded_utc),tripStamp=Date.parse(committedJourneys.downloaded_utc);
assert.ok(Number.isFinite(stopStamp)&&Number.isFinite(tripStamp),"Committed GTFS snapshots must have valid timestamps");
assert.ok(Math.abs(stopStamp-tripStamp)<=86400000,"Committed stop and trip snapshots must be within 24 hours");
const stops=structuredClone(committedStops),journeys=structuredClone(committedJourneys);
stops.downloaded_utc="2026-10-27T10:57:50Z";
journeys.downloaded_utc="2026-10-27T10:57:50Z";
console.log("PASS: committed stop/trip timestamp coherence and deterministic QA fixture dates");
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];

// Stop and timetable loading failures must be distinguishable from a pending download.
assert.match(script,/let scheduleLoadState="loading",stopLoadState="loading"/);
assert.match(script,/stopLoadState="failed";source="";refreshDataStatus/);
assert.match(script,/stopLoadState="ready";source="Official Coast RTA GTFS"/);
assert.match(script,/const unavailable=stopLoadState==="failed"\|\|scheduleLoadState==="failed"/);
assert.match(script,/async function fetchRouteData\(url\)/,"Local GTFS fetch must have a timeout wrapper");
assert.match(script,/controller\.abort\(\);reject\(Error\("Route data download timed out after 15 seconds"\)\)/,"Stalled GTFS requests must reject after 15 seconds even if JSON ignores abort");
assert.match(script,/stopLoadState="failed";source="";refreshDataStatus\(\);if\(destination&&screen==="itinerary"\)renderTrip\(\)/,"A stop-feed failure must update an already-visible itinerary");
assert.match(script,/scheduleLoadState="failed";[\s\S]*?if\(destination&&screen==="itinerary"\)renderTrip\(\)/,"A timetable failure must update an already-visible itinerary");

// Stale stop coordinates must remain explicitly warned about even if the journey
// timetable fails to load. The untimed fallback must also warn on stale data.
{
 const begin=script.indexOf("function transitDataTooOld(){");
 const end=script.indexOf("async function loadStops()",begin);
 assert.ok(begin>=0&&end>begin,"Freshness and status handlers must exist");
 const actual=script.slice(begin,end);
 const status=new Function("official","journeys","scheduleLoadState","reportDataStatus","snapshotDate",
  actual+";refreshDataStatus()");
 let warning="";
 status({stops:[{id:"TL-QA"}],downloaded_utc:"2020-01-01T00:00:00Z"},null,"failed",
  message=>{warning=message},()=>"Jan 1");
 assert.match(warning,/older than 7 days/,"A stale stop inventory must be announced even if timetable loading failed");
 let fresh="";
 status({stops:[{id:"TL-QA"}],downloaded_utc:new Date().toISOString()},null,"failed",
  message=>{fresh=message},()=>"Today");
 assert.doesNotMatch(fresh,/older than 7 days/,"A fresh stop inventory must not receive a false stale warning");
 const fallback=script.slice(script.indexOf("function showPossiblePattern(pattern){"),script.indexOf("function boardingDepartureStatus()"));
 assert.match(fallback,/stopInventoryTooOld\(\)\|\|transitDataTooOld\(\)/,"Untimed fallback must check both stop and timetable freshness");
 assert.match(fallback,/This possible route pattern may be outdated/,"Untimed fallback must visibly disclose stale route patterns");
 console.log("PASS: stale stop-only data and untimed route previews disclose freshness risks");
}

// Two current official Coast RTA pages conflict: contactless-fare-payment says 5–7 PM,
// how-to-ride says 3–6 PM. Do not assert either is the authoritative peak window.
assert.match(html,/official pages disagree on afternoon peak hours \(3–6 PM versus 5–7 PM\)/);
assert.match(html,/Do not assume a free ride: budget \$1 per boarding/);
assert.match(html,/https:\/\/coastrta\.com\/contactless-fare-payment\//);
assert.match(html,/https:\/\/coastrta\.com\/how-to-ride\//);
console.log("PASS: contradictory official peak-hour fare pages disclosed without claiming a free ride");
assert.match(html,/A physical card, phone, and watch can count as different payment methods even when linked to the same bank card/,"Do not imply mixing physical card and mobile wallet preserves the 24-hour cap");
console.log("PASS: contactless cap guidance warns that switching card and device can defeat capping");

assert.ok(script&&stops.stops.length>=50&&journeys.trips.length);
const origin=stops.stops.find(s=>/Georgetown Transfer Center/i.test(s.name));
const target=stops.stops.find(s=>/Andrews Piggly Wiggly/i.test(s.name));
assert.ok(origin&&target,"Official Route 14 fixture stops absent");
const interchange=stops.stops.find(s=>s.name==="Conway Terminal");
assert.ok(interchange,"Conway transfer fixture stop absent");
// Deliberately synthetic timetables, never presented as Coast RTA departure claims.
function syntheticTransfer(secondDeparture="09:10:00",exceptions=[],uncertainty="none"){
 const service="QA-TEST";
 const preInterchange=stops.stops.find(s=>s.id!==interchange.id&&/Conway/i.test(s.name));
 assert.ok(preInterchange,"Conway fixture stop for estimated departure absent");
 const firstStops=uncertainty==="arrival"?[{stop:origin.id,arr:"08:30:00",dep:"08:30:00"},{stop:interchange.id,arr:"",dep:""},{stop:origin.id,arr:"09:00:00",dep:"09:00:00"}]:[{stop:origin.id,arr:"08:30:00",dep:"08:30:00"},{stop:interchange.id,arr:"09:00:00",dep:"09:00:00"}];
 const secondStops=uncertainty==="departure"?[{stop:preInterchange.id,arr:"08:55:00",dep:"08:55:00"},{stop:interchange.id,arr:"",dep:""},{stop:target.id,arr:"10:00:00",dep:"10:00:00"}]:[{stop:interchange.id,arr:secondDeparture,dep:secondDeparture},{stop:target.id,arr:"10:00:00",dep:"10:00:00"}];
 return {source:"synthetic regression only",downloaded_utc:"2026-10-27T10:57:50Z",calendar:[{service_id:service,start_date:"20260101",end_date:"20261231",monday:"1",tuesday:"1",wednesday:"1",thursday:"1",friday:"1",saturday:"1",sunday:"1"}],exceptions,trips:[
  {id:"QA-A",route:"TEST ROUTE A",headsign:" ",service,stops:firstStops},
  {id:"QA-B",route:"TEST ROUTE B",headsign:"  Andrews  ",service,stops:secondStops}
 ]};
}
function syntheticEstimatedArrival(){
 const sample=syntheticTransfer();
 sample.trips=[{id:"QA-ESTIMATED-ARRIVAL",route:"TEST ESTIMATED ARRIVAL",service:"QA-TEST",stops:[
  {stop:origin.id,arr:"08:30:00",dep:"08:30:00"},
  {stop:target.id,arr:"",dep:""},
  {stop:interchange.id,arr:"09:30:00",dep:"09:30:00"}
 ]}];
 return sample;
}
function syntheticEstimatedBoarding(){
 const sample=syntheticTransfer();
 sample.trips=[{id:"QA-ESTIMATED-BOARD",route:"TEST ESTIMATED BOARD",service:"QA-TEST",stops:[
  {stop:interchange.id,arr:"08:00:00",dep:"08:00:00"},
  {stop:origin.id,arr:"",dep:""},
  {stop:target.id,arr:"09:30:00",dep:"09:30:00"}
 ]}];
 return sample;
}
class El{
 constructor(id="",tag="DIV"){this.id=id;this.tagName=tag;this.textContent="";this.value="";this.disabled=false;this.children=[];this.style={};this.classList={toggle(){}}}
 append(...x){this.children.push(...x)}
 replaceChildren(...x){this.children=[...x]}
 setAttribute(){}
 removeAttribute(name){if(name==="href")delete this.href}
 focus(){}
}
function boot(instant="2026-10-27T11:00:00Z",deferred=null,fixtureJourneys=null,fault=null){
 let clockInstant=instant;
 const ids=[...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(x=>x[1]);
 const els=new Map(ids.map(x=>[x,new El(x)]));
 const get=id=>{if(!els.has(id))els.set(id,new El(id));return els.get(id)};
 const document={getElementById:get,querySelectorAll:()=>ids.map(get),querySelector:()=>new El("heading","H2"),createElement:t=>new El("",t.toUpperCase()),createTextNode:t=>({textContent:t})};
 let cancellations=0;const spoken=[],speechSynthesis={cancel(){cancellations++},speak:u=>spoken.push(u.text)};
 // Exercise the supported reduced-motion path so visual transition timers cannot delay journey assertions.
  const timers=new Map();let nextTimerId=0;
  const window={scrollTo(){},speechSynthesis,matchMedia:query=>({matches:query==="(prefers-reduced-motion: reduce)"}),setTimeout:fn=>{const id=++nextTimerId;timers.set(id,fn);return id},clearTimeout:id=>timers.delete(id)};
 let delayedGpsSuccess=null;
  const navigator={geolocation:{getCurrentPosition:(ok,fail)=>fault==="gps-denied"?fail({message:"Permission denied"}):fault==="gps-hang"?undefined:fault==="gps-late"?(delayedGpsSuccess=ok):ok({coords:{latitude:origin.lat,longitude:origin.lon,accuracy:14}})},clipboard:{writeText:async()=>{}}};
 class FixedDate extends Date{constructor(...a){super(...(a.length?a:[clockInstant]))}static now(){return new Date(clockInstant).getTime()}}
 // Mock places must have the correct city; a wrong-town result is now rejected intentionally.
 const feature=s=>({geometry:{coordinates:[s.lon,s.lat]},properties:{name:s.name,city:/Andrews/i.test(s.name)?"Andrews":/Conway/i.test(s.name)?"Conway":"Georgetown",state:"South Carolina"}});
 let rejectStopDownload=null,rejectJourneyDownload=null;
 const fetch=async (url,opts={})=>{
  const u=String(url);
  if(u.includes("coast-rta-stops.json")){if(fault==="stops-delayed-failure")return new Promise((_resolve,reject)=>{rejectStopDownload=reject});if(fault==="stops-json-hang")return {ok:true,json:()=>new Promise(()=>{})};return {ok:fault!=="stops-offline",json:async()=>stops}}
  if(u.includes("coast-rta-journeys.json")){if(fault==="journeys-delayed-failure")return new Promise((_resolve,reject)=>{rejectJourneyDownload=reject});if(fault==="journeys-json-hang")return {ok:true,json:()=>new Promise(()=>{})};return {ok:fault!=="journeys-offline",json:async()=>fault==="frequency-unverified"?{...structuredClone(committedJourneys),downloaded_utc:stops.downloaded_utc}:{...(fixtureJourneys||journeys),frequency_coverage:{status:"no_frequency_rows"}}}}
  if(u.includes("/reverse?"))return {ok:true,json:deferred?()=>deferred.promise:async()=>({address:{road:"Lynch Street",city:"Georgetown"}})};
  if(u.includes("photon.komoot.io")&&fault==="geocoder-hang")return new Promise((_resolve,reject)=>{opts.signal?.addEventListener("abort",()=>reject(Error("Simulated geocoder timeout")))});
   if(u.includes("photon.komoot.io")&&fault==="geocoder-json-hang")return {ok:true,json:()=>new Promise(()=>{})};
  if(u.includes("photon.komoot.io")){const q=decodeURIComponent(u.split("&q=")[1]||"").toLowerCase();if(q.includes("2379 cypress circle conway"))return {ok:true,json:async()=>({features:[{geometry:{coordinates:[origin.lon,origin.lat]},properties:{name:"2379 Cypress Circle",housenumber:"2379",street:"Cypress Circle",city:"Georgetown",state:"South Carolina"}}]})};if(q.includes("walmart"))return {ok:true,json:async()=>({features:[{geometry:{coordinates:[target.lon,target.lat]},properties:{name:"Walmart",housenumber:"123",street:"Test Road",city:"Andrews",state:"South Carolina"}},{geometry:{coordinates:[interchange.lon,interchange.lat]},properties:{name:"Walmart",housenumber:"456",street:"Sample Street",city:"Conway",state:"South Carolina"}}]})};return {ok:true,json:async()=>({features:q.includes("andrews")?[feature(target)]:q.includes("georgetown")?[feature(origin)]:[]})}}
  if(u.includes("nominatim.openstreetmap.org"))return {ok:true,json:async()=>u.includes("1228%20Belle%20Isle%20Road")?[{lat:String(origin.lat+0.01),lon:String(origin.lon+0.01),name:"Belle Isle Bistro",display_name:"1228 Belle Isle Road, Georgetown, SC"}]:u.includes("2379%20Cypress%20Circle")?[{lat:String(interchange.lat+0.01),lon:String(interchange.lon+0.01),name:"PruittHealth - Conway at Conway Medical Center",display_name:"2379 Cypress Circle, Conway, SC 29526"}]:[]};
  throw Error("Unexpected mock fetch: "+u);
 };
 class MockAbortController{constructor(){this.listeners=[];this.signal={aborted:false,addEventListener:(name,fn)=>{if(name==="abort")this.listeners.push(fn)}}}abort(){if(this.signal.aborted)return;this.signal.aborted=true;for(const fn of this.listeners)fn()}}
 const ctx={document,window,navigator,fetch,AbortController:MockAbortController,speechSynthesis,SpeechSynthesisUtterance:class{constructor(text){this.text=text}},Date:FixedDate,Intl,console};
 const api=vm.runInNewContext(script+"\n({state:()=>({screen,pos,destination,official,journeys,stopLoadState,scheduleLoadState}),nearbyStopCaution:nearbyDistinctStopCaution,requestedCity:explicitlyRequestedCity,placeMatchesCity:placeMatchesRequestedCity,pickStartCandidate})",ctx,{timeout:5000});
 const click=async id=>{assert.equal(typeof get(id).onclick,"function","Missing handler "+id);await get(id).onclick()};
 const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve()};
 return {get,click,settle,spoken,cancelCount:()=>cancellations,state:api.state,nearbyStopCaution:api.nearbyStopCaution,requestedCity:api.requestedCity,placeMatchesCity:api.placeMatchesCity,pickStartCandidate:api.pickStartCandidate,setInstant:next=>{clockInstant=next},failStopDownload:()=>rejectStopDownload?.(Error("Simulated stop-feed outage")),failJourneyDownload:()=>rejectJourneyDownload?.(Error("Simulated journey-feed outage")),triggerTimers:()=>{for(const fn of [...timers.values()])fn()},lateGps:()=>delayedGpsSuccess?.({coords:{latitude:origin.lat,longitude:origin.lon,accuracy:14}})};
}
async function selectAndrews(a){
 await a.click("locate");await a.settle();assert.equal(a.state().screen,"found");
 assert.equal(a.get("yesLocation").disabled,false);
 await a.click("yesLocation");await a.click("goDestination");
 a.get("destinationInput").value="Andrews Piggly Wiggly";
 await a.click("findTrip");assert.equal(a.state().screen,"searchResults");
 assert.ok(a.get("placeResults").children.length);
 await a.get("placeResults").children[0].onclick();
 assert.equal(a.state().screen,"confirmDestination");
 await a.click("yesDestination");assert.equal(a.state().screen,"itinerary");
}
async function main(){
 // A free place directory may hang forever. The rider must get a bounded error and an enabled retry control.
 const hung=boot("2026-10-27T11:00:00Z",null,null,"geocoder-hang");
 await hung.settle();await hung.click("locate");await hung.settle();await hung.click("yesLocation");await hung.click("goDestination");
 hung.get("destinationInput").value="123 Unlisted Road Andrews";
 const pendingLookup=hung.click("findTrip");await hung.settle();
 assert.equal(hung.get("findTrip").disabled,true,"Search should be pending before timeout");
 hung.triggerTimers();await pendingLookup;
 assert.equal(hung.get("findTrip").disabled,false,"A timed-out geocoder must re-enable the search control");
 assert.match(hung.get("tripStatus").textContent,/Place lookup timed out after 15 seconds/,"Timeout must be explained to the rider");
 assert.equal(hung.state().screen,"destination","Timeout must not silently choose a place");
 console.log("PASS: hung place geocoder times out, explains failure, and restores search button (mocked)");
 // A successful HTTP response may still stall forever while decoding JSON.
 // AbortController alone cannot release a promise that ignores abort.
 const stuckJsonDestination=boot("2026-10-27T11:00:00Z",null,null,"geocoder-json-hang");
 await stuckJsonDestination.settle();await stuckJsonDestination.click("locate");await stuckJsonDestination.settle();
 await stuckJsonDestination.click("yesLocation");await stuckJsonDestination.click("goDestination");
 stuckJsonDestination.get("destinationInput").value="123 Unlisted Road Andrews";
 const pendingJsonDestination=stuckJsonDestination.click("findTrip");await stuckJsonDestination.settle();
 assert.equal(stuckJsonDestination.get("findTrip").disabled,true,"Destination lookup should be pending before JSON deadline");
 stuckJsonDestination.triggerTimers();await pendingJsonDestination;
 assert.equal(stuckJsonDestination.get("findTrip").disabled,false,"Hung destination JSON decoding must restore search control");
 assert.match(stuckJsonDestination.get("tripStatus").textContent,/Place lookup timed out after 15 seconds/,"Hung destination JSON decoding must explain timeout");
 assert.equal(stuckJsonDestination.state().destination,null,"Hung JSON decoding must not invent destination coordinates");
 assert.equal(stuckJsonDestination.state().screen,"destination","Hung JSON decoding must not advance to a guessed destination");
 console.log("PASS: destination JSON-body hang is bounded even when provider ignores abort (mocked)");
 // Typed START addresses need the same bounded recovery as destination lookup.
 // A hanging free provider must not leave the rider stuck on "Checking" forever.
 const hungOrigin=boot("2026-10-27T11:00:00Z",null,null,"geocoder-hang");
 await hungOrigin.settle();await hungOrigin.click("typeStart");
 hungOrigin.get("address").value="123 Unlisted Road Georgetown";
 const pendingOrigin=hungOrigin.click("useAddress");await hungOrigin.settle();
 assert.equal(hungOrigin.get("useAddress").disabled,true,"Starting-address lookup should be pending before timeout");
 hungOrigin.triggerTimers();await pendingOrigin;
 assert.equal(hungOrigin.get("useAddress").disabled,false,"Timed-out starting-address search must restore the retry control");
 assert.match(hungOrigin.get("manualStatus").textContent,/Starting-address lookup timed out after 15 seconds/,"Origin timeout must be explained");
 assert.equal(hungOrigin.state().screen,"manual","Origin timeout must not silently confirm a wrong starting location");
 assert.equal(hungOrigin.state().pos,null,"Origin timeout must not set a guessed starting coordinate");
 console.log("PASS: hung starting-address geocoder times out, restores retry, and preserves manual location confirmation (mocked)");
 // Abort alone does not guarantee recovery if a provider's response body never settles.
 // Exercise a geocoder that returns HTTP 200 but hangs forever during response.json().
 const stuckJsonOrigin=boot("2026-10-27T11:00:00Z",null,null,"geocoder-json-hang");
 await stuckJsonOrigin.settle();await stuckJsonOrigin.click("typeStart");
 stuckJsonOrigin.get("address").value="123 Unlisted Road Georgetown";
 const pendingJsonOrigin=stuckJsonOrigin.click("useAddress");await stuckJsonOrigin.settle();
 assert.equal(stuckJsonOrigin.get("useAddress").disabled,true,"Origin lookup should remain pending before JSON deadline");
 stuckJsonOrigin.triggerTimers();await pendingJsonOrigin;
 assert.equal(stuckJsonOrigin.get("useAddress").disabled,false,"Hung JSON decoding must restore the origin search control");
 assert.match(stuckJsonOrigin.get("manualStatus").textContent,/Starting-address lookup timed out after 15 seconds/,"Hung JSON decoding must show timeout warning");
 assert.equal(stuckJsonOrigin.state().pos,null,"Hung JSON decoding must not invent origin coordinates");
 assert.equal(stuckJsonOrigin.state().screen,"manual","Hung JSON decoding must not advance to location confirmation");
 console.log("PASS: origin JSON-body hang is bounded by deadline even when AbortController cannot settle the provider (mocked)");
 // Reverse-geocoding can hang after GPS succeeds. Never leave YES, THAT'S ME
 // disabled indefinitely: fall back to coordinates, not a fabricated street.
 const pendingReverse={promise:new Promise(()=>{})};
 const hungReverse=boot("2026-10-27T11:00:00Z",pendingReverse);
 await hungReverse.settle();await hungReverse.click("locate");await hungReverse.settle();
 assert.equal(hungReverse.state().screen,"found","GPS should open confirmation even if reverse geocoding hangs");
 assert.equal(hungReverse.get("yesLocation").disabled,true,"Address confirmation waits while reverse lookup is pending");
 hungReverse.triggerTimers();await hungReverse.settle();
 assert.equal(hungReverse.get("yesLocation").disabled,false,"Ten-second reverse timeout must restore location confirmation");
 assert.match(hungReverse.get("foundAddress").textContent,/street address unavailable; if unsure, choose CHANGE LOCATION/,"Do not invent an address when reverse lookup fails");
 assert.ok(hungReverse.state().pos,"Keep actual GPS coordinates after reverse-geocoder timeout");
 await hungReverse.click("yesLocation");
 assert.equal(hungReverse.state().screen,"chooseGoal","Rider can proceed after reviewing coordinates");
 console.log("PASS: hung reverse GPS address lookup releases confirmation with coordinates and no invented street (mocked)");

 // Reproduce a failure arriving AFTER the rider has already opened the itinerary.
 // The old code left the loading message in place forever; the new handlers must
 // re-render a fail-closed itinerary without requiring the rider to leave/re-enter.
 for(const fault of ["stops-delayed-failure","journeys-delayed-failure"]){
  const a=boot("2026-10-27T11:00:00Z",null,null,fault);
  await a.settle();await selectAndrews(a);
  assert.match(a.get("planStatus").textContent,/Loading Coast RTA route data/);
  if(fault==="stops-delayed-failure")a.failStopDownload();else a.failJourneyDownload();
  await a.settle();
  assert.match(a.get("planStatus").textContent,/route data could not be loaded/,"Late data failure must update the active itinerary");
  assert.equal(a.get("guideStart").disabled,true,"A failed download must not enable guided boarding");
  assert.ok(a.get("planSteps").children.some(x=>x.href==="tel:8434880865"),"A rider must get a direct Coast RTA help link");
 }
 console.log("PASS: delayed stop/timetable download failures refresh the visible itinerary and fail closed");

 // Local GTFS files can respond HTTP 200 but never finish decoding JSON.
 // Aborting fetch alone must not strand stop or timetable loading forever.
 for(const [fault,key] of [["stops-json-hang","stopLoadState"],["journeys-json-hang","scheduleLoadState"]]){
  const stuck=boot("2026-10-27T11:00:00Z",null,null,fault);
  await stuck.settle();
  assert.equal(stuck.state()[key],"loading","A hanging JSON body must initially remain loading: "+fault);
  stuck.triggerTimers();await stuck.settle();
  assert.equal(stuck.state()[key],"failed","A hanging JSON body must time out and fail closed: "+fault);
  if(fault==="stops-json-hang")assert.equal(stuck.state().official,null,"No guessed stop inventory may be loaded");
  if(fault==="journeys-json-hang")assert.equal(stuck.state().journeys,null,"No guessed timetable may be loaded");
 }
 console.log("PASS: hanging local stop/timetable JSON bodies time out and fail closed (mocked)");

 // An exact street match in a different Coast RTA town must not be offered
 // when the rider explicitly typed Andrews, Surfside Beach or another service-area community.
 const cityGuard=boot();await cityGuard.settle();
 for(const [typed,expected] of [
  ["123 Main Street Andrews","andrews"],
  ["123 Main Street Surfside Beach","surfside beach"],
  ["Walmart North Myrtle Beach","north myrtle beach"],
  ["123 Main Street Murrells Inlet","murrells inlet"],
  ["123 Main Street Georgetown","georgetown"],
  ["2379 Cypress Circle Conway","conway"],
  ["Andrews Pharmacy Myrtle Beach","myrtle beach"],
  ["Walmart",null]
 ])assert.equal(cityGuard.requestedCity(typed),expected,"Destination search must preserve explicitly requested town: "+typed);
 for(const [typed,address,expected] of [
  ["123 Main Street Andrews","123 Main Street Conway, SC",false],
  ["123 Main Street Andrews","123 Main Street Andrews, SC",true],
  ["Walmart North Myrtle Beach","Walmart Myrtle Beach, SC",false],
  ["Walmart North Myrtle Beach","Walmart North Myrtle Beach, SC",true],
  ["Walmart","Walmart Conway, SC",true]
 ])assert.equal(cityGuard.placeMatchesCity(typed,{address}),expected,"Do not accept a wrong-town geocoder candidate: "+typed);
 assert.ok(html.includes("if(!matches.some(x=>placeMatchScore(q,x)>=75&&placeMatchesRequestedCity(typed,x)))"),"Retry free geocoder if Photon found only wrong-town matches");
 assert.ok(html.includes("if(matches.some(x=>placeMatchScore(q,x)>=75&&placeMatchesRequestedCity(typed,x)))break"),"Do not stop fallback search on wrong-town matches");
 assert.ok(html.includes("const eligible=matches.filter(x=>score(x)>=75&&placeMatchesRequestedCity(typed,x))"),"Final place results must respect typed town");
 console.log("PASS: typed destination town cannot be silently replaced with another Coast RTA community");

 const frequencyBlocked=boot("2026-10-27T11:00:00Z",null,null,"frequency-unverified");
 await frequencyBlocked.settle();await selectAndrews(frequencyBlocked);
 assert.equal(frequencyBlocked.get("guideStart").disabled,true,"Unverified frequency-based timetable must not start spoken boarding");
 assert.match(frequencyBlocked.get("planStatus").textContent,/frequency-based service.*START MY TRIP is disabled/);
 assert.match(frequencyBlocked.get("planStatus").textContent,/POSSIBLE ROUTE TEMPLATE ONLY, NOT A CONFIRMED TRIP/,"Unverified frequency template must not be presented as a scheduled journey");
 assert.ok(html.includes('Confirm all service and stops with Coast RTA. "+$("planStatus").textContent'),"Unverified-frequency label must preserve existing long-walk and interpolated-time safety warnings");
 assert.match(frequencyBlocked.get("dataStatus").textContent,/frequency-based trips absent from this timetable/);
 assert.ok(frequencyBlocked.get("planSteps").children.length,"Keep itinerary preview available for review");
 const readTemplate=frequencyBlocked.get("planSteps").children.find(x=>/READ UNCONFIRMED ROUTE ALOUD/.test(x.textContent));
 assert.ok(readTemplate&&!readTemplate.disabled,"Unconfirmed timed templates need an accessible, user-requested spoken review");
 const beforeTemplateSpeech=frequencyBlocked.spoken.length;
 await readTemplate.onclick();
 assert.equal(frequencyBlocked.spoken.length,beforeTemplateSpeech+1,"Route template must speak only after rider taps the preview");
 assert.match(frequencyBlocked.spoken.at(-1),/^POSSIBLE ROUTE TEMPLATE ONLY, NOT A CONFIRMED TRIP\. Do not travel based on this preview\./,"Spoken timed-template review must begin with the safety restriction");
 assert.match(frequencyBlocked.spoken.at(-1),/stop ID TL-/,"Spoken timed-template review must include official stop IDs");
 assert.equal(frequencyBlocked.get("guideStart").disabled,true,"Spoken review must not authorize unverified boarding");
 await frequencyBlocked.click("guideStart");assert.equal(frequencyBlocked.state().screen,"itinerary");
 console.log("PASS: unverified Coast RTA frequency templates cannot authorize exact-time spoken boarding");

 // Frequency-only tests use the real trip structure and frequency metadata,\n // but share the fixed mock stop timestamp. Otherwise Oct 28 committed trips\n // and Oct 27 fixed mock stops appear >24 hours out of sync and correctly\n // block all walking links, causing a false regression failure.\n // When the non-exact frequency feed cannot supply a timed journey,
 // retain only a topology-based route-pattern idea, never a departure claim.
 const lateFrequency=boot("2026-10-28T00:41:00Z",null,null,"frequency-unverified");
 await lateFrequency.settle();await selectAndrews(lateFrequency);
 assert.match(lateFrequency.get("planStatus").textContent,/POSSIBLE ROUTE PATTERN ONLY, NOT A CONFIRMED TRIP/);
 assert.match(lateFrequency.get("planStatus").textContent,/frequency-based departures, actual transfer timing/);
 assert.equal(lateFrequency.get("guideStart").disabled,true,"A route-pattern-only result must never enable guided boarding");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/POSSIBLE BUS 1:/.test(x.textContent)),"Show stored route/stop pattern instead of inventing a departure");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/stop ID TL-/.test(x.textContent)),"Preview must identify official stop IDs");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/Selected destination:/.test(x.textContent)),"Untimed preview must repeat the rider-confirmed destination");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/Confirm the route, direction and destination sign with the driver before boarding/.test(x.textContent)),"Untimed route patterns must warn against boarding the wrong direction");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/Official destination sign not supplied|Stored destination sign:/.test(x.textContent)),"Untimed preview must distinguish missing headsigns from supplied ones");
 assert.ok(!lateFrequency.get("planSteps").children.some(x=>/OPEN WALK|VIEW FINAL WALKING ROUTE/.test(x.textContent)),"Do not offer unverified pedestrian navigation in topology-only mode");
 // Topology-only mode must still let Trey inspect both pedestrian ends without
 // pretending the route is walkable or authorizing a headway-based boarding time.
 const topologyLinks=lateFrequency.get("planSteps").children.filter(x=>x.tagName==="A"&&/^REVIEW EXTERNAL WALKING DIRECTIONS/.test(x.textContent));
 assert.ok(topologyLinks.some(x=>/TO FIRST POSSIBLE STOP/.test(x.textContent)),"Untimed route must offer a review-only walk to its possible first stop");
 assert.ok(topologyLinks.some(x=>/FROM LAST POSSIBLE STOP/.test(x.textContent)),"Untimed route must offer a review-only walk from its possible final stop");
 assert.ok(topologyLinks.every(x=>x.href.startsWith("https://www.google.com/maps/dir/?api=1&origin=")&&x.href.endsWith("&travelmode=walking")),"Only external Google Maps walking review links are allowed");
 assert.ok(lateFrequency.get("planSteps").children.some(x=>/Walking links below open an EXTERNAL map for review ONLY/.test(x.textContent)),"Review links must have a prominent safety disclaimer");
 assert.equal(lateFrequency.get("guideStart").disabled,true,"Pedestrian map review cannot enable spoken trip guidance");
 const topologySavedStamp=stops.downloaded_utc;
 stops.downloaded_utc="2026-10-01T00:00:00Z";
 let topologyBlocked=false;
 const staleClick=topologyLinks[0].onclick({preventDefault(){topologyBlocked=true}});
 assert.equal(topologyBlocked,true,"An already displayed topology walking link must recheck stop freshness on tap");
 assert.equal(staleClick,false,"Stale walking review must cancel external navigation");
 assert.match(lateFrequency.get("planStatus").textContent,/External walking review is disabled/);
 const staleTopology=boot("2026-10-28T00:41:00Z",null,null,"frequency-unverified");
 await staleTopology.settle();await selectAndrews(staleTopology);
 assert.equal(staleTopology.get("guideStart").disabled,true);
 assert.equal(staleTopology.get("planSteps").children.filter(x=>x.tagName==="A"&&/^REVIEW EXTERNAL WALKING DIRECTIONS/.test(x.textContent)).length,0,"Do not render map links for stale topology or coordinates");
 assert.ok(staleTopology.get("planSteps").children.some(x=>/External walking-review links are disabled/.test(x.textContent)));
 stops.downloaded_utc=topologySavedStamp;
 console.log("PASS: untimed route-pattern first/final walking review is external, stale-safe, and never enables guided boarding (mocked)");
 const readPreview=lateFrequency.get("planSteps").children.find(x=>/READ POSSIBLE ROUTE ALOUD/.test(x.textContent));
 assert.ok(readPreview&&!readPreview.disabled,"Untimed route preview must offer accessible speech review when speech synthesis is supported");
 const beforeRead=lateFrequency.spoken.length;
 await readPreview.onclick();
 assert.equal(lateFrequency.spoken.length,beforeRead+1,"Reading the route preview must speak only on rider request");
 assert.match(lateFrequency.spoken.at(-1),/NOT A CONFIRMED TRIP.*Do not travel based on this preview/i,"Spoken route preview must lead with a safety disclaimer");
 assert.match(lateFrequency.spoken.at(-1),/stop ID TL-/,"Spoken route preview must include official stop IDs");
 assert.match(html,/id="stopVoice"[^>]*aria-label="Stop Bus Buddy spoken instructions"/,"Voice-stop control must be accessible from the persistent mobile footer");
 const cancelBefore=lateFrequency.cancelCount();
 const spokenBeforeStop=lateFrequency.spoken.length;
 await lateFrequency.click("stopVoice");
 assert.equal(lateFrequency.cancelCount(),cancelBefore+1,"STOP VOICE must cancel the active browser speech");
 assert.equal(lateFrequency.spoken.length,spokenBeforeStop,"STOP VOICE must not speak another message");
 assert.equal(lateFrequency.state().screen,"itinerary","STOP VOICE must not discard the selected trip");
 assert.equal(lateFrequency.get("guideStart").disabled,true,"STOP VOICE must not authorize an unconfirmed trip");
 assert.equal(lateFrequency.get("guideStart").disabled,true,"Reading an unconfirmed preview must never authorize live guidance");
 assert.match(lateFrequency.get("planFare").textContent,/not a confirmed trip/);
 await lateFrequency.click("guideStart");assert.equal(lateFrequency.state().screen,"itinerary");
 console.log("PASS: late frequency-based service offers untimed stop/route-pattern review without false departures or guided navigation");

 const a=boot();await a.settle();
 // Coast RTA's two distinct mapped stops near Coalition Dr / Holly Circle are 52 m apart,
 // but the stored Route 15S trip sequence has 24 intermediate stops from Holly Circle to Coalition Dr.
 // A nearby stop ID must not be silently treated as the same boarding point or direction.
 const holly=stops.stops.find(s=>s.id==="TL-947");
 const coalition=stops.stops.find(s=>s.id==="TL-948");
 assert.ok(holly&&coalition,"Official Coalition/Holly Circle stop IDs changed: re-audit Trey boarding location");
 const nearbyWarning=a.nearbyStopCaution(holly);
 assert.match(nearbyWarning,/TL-948/,"Nearby distinct stop must be named with its official ID");
 assert.match(nearbyWarning,/boarding side, and safe crossing/,"Do not certify an unverified pedestrian route");
 assert.doesNotMatch(nearbyWarning,/opposite side|live arrival/i,"Do not invent stop side or vehicle data");
 assert.equal(a.nearbyStopCaution({id:"QA-REMOTE",name:"Remote",lat:34.9,lon:-80.9}),"");
 console.log("PASS: nearby distinct Coalition/Holly stop IDs trigger explicit non-certified boarding caution");

 // The same stop-ID caution must travel with the itinerary and spoken step text,
 // not only appear on the separate nearest-stop screen. Synthetic duplicate only.
 for(const expression of [
  "+sameNameStopCaution(first.from)+nearbyDistinctStopCaution(first.from)",
  "+sameNameStopCaution(l.from)+nearbyDistinctStopCaution(l.from)",
  "+sameNameStopCaution(l.to)+nearbyDistinctStopCaution(l.to)",
  "+sameNameStopCaution(plan.legs[i+1].from)+nearbyDistinctStopCaution(plan.legs[i+1].from)",
  "+sameNameStopCaution(plan.legs.at(-1).to)+nearbyDistinctStopCaution(plan.legs.at(-1).to)"
 ])assert.ok(html.includes(expression),"Missing distinct-stop caution in a trip instruction: "+expression);
 const syntheticNeighbor={...origin,id:"QA-NEAR-GEORGETOWN",name:"QA Nearby Separate Boarding Stop",lat:origin.lat+0.0001};
 stops.stops.push(syntheticNeighbor);
 try{
  const warnedItinerary=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());
  await warnedItinerary.settle();
  await selectAndrews(warnedItinerary);
  const cards=warnedItinerary.get("planSteps").children.filter(x=>x.tagName==="ARTICLE");
  const details=cards.map(card=>card.children.find(x=>x.tagName==="P")?.textContent||"");
  assert.ok(details.filter(x=>x.includes("QA-NEAR-GEORGETOWN")).length>=2,
   "First-stop and boarding instructions must identify nearby distinct stop IDs");
  assert.ok(details.some(x=>/boarding side, and safe crossing/.test(x)),
   "The itinerary must not certify an unknown crossing");
 }finally{
  stops.stops.pop();
 }
 console.log("PASS: synthetic journey carries nearby distinct-stop warnings into trip steps (not a live route test)");

 // Static CSS guard; actual mobile scrolling, TalkBack and focus still need device testing.
 // A sticky footer placed after <main> is invisible on long screens until scrolled into view.
 assert.match(html,/footer\{position:fixed;left:50%;/,"Home/Back/report must be fixed to the viewport");
 assert.match(html,/body\{padding-bottom:calc\(var\(--footer-height, 130px\) \+ 32px\)\}/,"Content needs clearance below the fixed footer");
 assert.match(html,/#feedback\{grid-column:1\/-1\}/,"Report button needs full-width mobile row");
 assert.match(html,/#guide #nextInstruction\{position:fixed;/,"NEXT must remain visible above the fixed footer");
 assert.match(html,/bottom:calc\(var\(--footer-height, 130px\) \+ 8px\)/,"NEXT must track measured footer height");
 assert.match(html,/function syncBottomControls\(\)/,"Footer height must adapt to zoom and text scaling");
 assert.doesNotMatch(html,/footer\{position:sticky;/,"Footer must not regress to below-the-fold sticky positioning");
 console.log("PASS: fixed mobile Home/Back/report and NEXT layout safeguards (source-only)");
 assert.match(html,/id="dataStatus" role="status" aria-live="polite"/);
 // Keep technical diagnostics visually off the welcome screen without hiding safety warnings from screen readers.
 assert.match(html,/#dataStatus\{position:absolute!important;/,"Status should remain visually hidden but accessible");
 assert.doesNotMatch(html,/#dataStatus\{display:none!important\}/,"Do not remove safety warnings from the accessibility tree");
 assert.match(a.get("dataStatus").textContent,new RegExp(stops.stops.length+" mapped stops, "+journeys.trips.length+" stored trip templates \\(not verified departures\\)"));
 const dateLabel=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric"}).format(new Date(journeys.downloaded_utc));
 assert.ok(a.get("dataStatus").textContent.includes("Snapshot "+dateLabel),"Displayed snapshot date must match deterministic QA fixture");
 assert.match(a.get("dataStatus").textContent,/Not live arrivals; walking routes unverified/);
 assert.doesNotMatch(a.get("dataStatus").textContent,/143 scheduled trips/,"Unverified frequency templates must never be labeled scheduled trips");
 assert.doesNotMatch(a.get("dataStatus").textContent,/WARNING: stored schedules are older than 7 days/,"Fresh snapshot must not be marked stale");
 const oldSnapshot=boot("2026-11-10T12:00:00Z");await oldSnapshot.settle();
 assert.match(oldSnapshot.get("dataStatus").textContent,/WARNING: stored stops or schedules are older than 7 days/,"Stale Coast RTA snapshot must show a rider-visible warning");
 await selectAndrews(oldSnapshot);
 assert.match(oldSnapshot.get("planFare").textContent,/bus/,"Retain a preview of the possible itinerary");
 assert.equal(oldSnapshot.get("guideStart").disabled,true,"Stale schedules must never authorize START MY TRIP");
 assert.match(oldSnapshot.get("planStatus").textContent,/stale, future-dated, or undated/);
 const savedStopStamp=stops.downloaded_utc;
 stops.downloaded_utc="2026-10-01T00:00:00Z";
 const staleStopsOnly=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await staleStopsOnly.settle();await selectAndrews(staleStopsOnly);
 assert.equal(staleStopsOnly.get("guideStart").disabled,true,"Fresh journeys cannot mask stale stop coordinates");
 const staleMapLinks=staleStopsOnly.get("planSteps").children.filter(x=>x.tagName==="A"&&/WALK|WALKING/i.test(x.textContent));
 assert.equal(staleMapLinks.length,0,"Stale coordinates must not offer itinerary walking-map links");
 assert.ok(staleStopsOnly.get("planSteps").children.some(x=>/Walking map links are disabled/.test(x.textContent)),"Itinerary must explain missing walking links");
 console.log("PASS: stale stop coordinates hide both itinerary walking-map links");
 assert.match(staleStopsOnly.get("dataStatus").textContent,/stored stops or schedules are older than 7 days/);
 await staleStopsOnly.click("home");await staleStopsOnly.click("locate");await staleStopsOnly.settle();
 await staleStopsOnly.click("yesLocation");await staleStopsOnly.click("goNearest");
 assert.equal(staleStopsOnly.state().screen,"nearest","Keep stale mapped-stop preview visible for verification");
 assert.equal(staleStopsOnly.get("chooseStop").disabled,true,"Stale stop coordinates must not open walking directions");
 assert.match(staleStopsOnly.get("stopDetails").textContent,/Walking directions are disabled/);
 await staleStopsOnly.click("chooseStop"); // Mock invokes the handler even for a disabled button.
 assert.equal(staleStopsOnly.state().screen,"nearest","Guard the walking-link handler if stale data changes after rendering");
 assert.ok(staleStopsOnly.spoken.some(s=>/mapped stop inventory is not current/i.test(s)),"Spoken warning must not encourage walking to a stale stop");
 console.log("PASS: stale stop inventory blocks nearest-stop walking link and warns in speech");
 stops.downloaded_utc=savedStopStamp;
 const freshWalk=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await freshWalk.settle();await selectAndrews(freshWalk);
 const freshLinks=freshWalk.get("planSteps").children.filter(x=>x.tagName==="A"&&/WALK|WALKING/i.test(x.textContent));
 assert.equal(freshLinks.length,2,"Fresh itinerary should retain both walking-map links for pedestrian review");
 assert.ok(freshLinks.every(x=>/^REVIEW EXTERNAL WALKING DIRECTIONS/.test(x.textContent)),"Both itinerary walking links must be explicitly external and review-only");
 assert.ok(freshWalk.get("planSteps").children.some(x=>/Bus Buddy has NOT verified accessible sidewalks, safe crossings, the boarding side/.test(x.textContent)),"Visible itinerary must warn about unverified pedestrian access and boarding side");
 // A different mapped boarding stop needs its own pedestrian-review link, not a
 // guessed crossing or a claim that the transfer can safely be made.
 const walkingFixture=syntheticTransfer();
 walkingFixture.trips[1].stops[0].stop="TL-365"; // 4th Ave (CNB), near Conway Terminal TL-20
 const walkingTransfer=boot("2026-10-27T11:00:00Z",null,walkingFixture);
 await walkingTransfer.settle();await selectAndrews(walkingTransfer);
 const transferLinks=walkingTransfer.get("planSteps").children.filter(x=>x.tagName==="A"&&/WALKING DIRECTIONS FOR TRANSFER/.test(x.textContent));
 assert.equal(transferLinks.length,1,"Distinct-stop transfer needs one external pedestrian review link");
 assert.match(transferLinks[0].href,/^https:\/\/www\.google\.com\/maps\/dir\/\?api=1&origin=/);
 assert.match(transferLinks[0].href,/&destination=.*&travelmode=walking$/);
 assert.ok(walkingTransfer.get("planSteps").children.some(x=>/Transfer 1:.*stop ID TL-20.*stop ID TL-365.*NOT verified safe crossings/.test(x.textContent)),
  "Transfer review must identify both mapped stop IDs and warn about crossing/accessibility uncertainty");
 assert.equal(walkingTransfer.get("guideStart").disabled,true,"Unverified inter-stop walking must never authorize spoken boarding");
 stops.downloaded_utc="2026-10-01T00:00:00Z";
 let transferPrevented=false;
 const transferClickResult=transferLinks[0].onclick({preventDefault(){transferPrevented=true}});
 assert.equal(transferPrevented,true,"Transfer map link must reject stale stop coordinates at click time");
 assert.equal(transferClickResult,false);
 assert.match(walkingTransfer.get("planStatus").textContent,/Transfer walking directions are disabled/);
 stops.downloaded_utc=savedStopStamp;
 console.log("PASS: distinct-stop transfer walking link is external, review-only, and stale-safe (mocked)");
 // An existing transfer link must also fail closed if the trip schedule is refreshed
 // separately from the stop inventory while the rider is reviewing the itinerary.
 const savedTransferJourneyStamp=walkingTransfer.state().journeys.downloaded_utc;
 walkingTransfer.state().journeys.downloaded_utc="2026-10-25T10:57:50Z";
 let transferMismatchPrevented=false;
 const transferMismatchResult=transferLinks[0].onclick({preventDefault(){transferMismatchPrevented=true}});
 assert.equal(transferMismatchPrevented,true,"Existing transfer walking link must block mismatched GTFS snapshot generations");
 assert.equal(transferMismatchResult,false);
 assert.match(walkingTransfer.get("planStatus").textContent,/Transfer walking directions are disabled/);
 walkingTransfer.state().journeys.downloaded_utc=savedTransferJourneyStamp;
 console.log("PASS: already-rendered transfer walking links block mismatched GTFS generations (mocked)");


 stops.downloaded_utc="2026-10-01T00:00:00Z";
 let prevented=false;
 const clickResult=freshLinks[0].onclick({preventDefault(){prevented=true}});
 assert.equal(prevented,true,"Walking link must recheck freshness if stop data ages after rendering");
 assert.equal(clickResult,false);
 assert.match(freshWalk.get("planStatus").textContent,/no longer current/);
 stops.downloaded_utc=savedStopStamp;
 console.log("PASS: fresh itinerary retains map links and guards stale click-time coordinates");
 // Both files can be individually recent but represent different GTFS refresh generations.
 const savedJourneyStamp=journeys.downloaded_utc;
 journeys.downloaded_utc="2026-10-25T10:57:50Z"; // Synthetic 48-hour mismatch, still within the seven-day age limit.
 const mismatchedSnapshots=boot();await mismatchedSnapshots.settle();await selectAndrews(mismatchedSnapshots);
 assert.equal(mismatchedSnapshots.get("guideStart").disabled,true,"Different recent GTFS snapshot generations must not authorize spoken boarding");
 assert.match(mismatchedSnapshots.get("dataStatus").textContent,/refreshed more than 24 hours apart/);
 assert.match(mismatchedSnapshots.get("planStatus").textContent,/snapshot times differ by more than 24 hours/);
 assert.match(mismatchedSnapshots.get("planFare").textContent,/bus/,"Mismatched snapshots may retain an itinerary preview");
 const mismatchWalkLinks=mismatchedSnapshots.get("planSteps").children.filter(x=>x.tagName==="A"&&/WALKING DIRECTIONS/.test(x.textContent));
 assert.equal(mismatchWalkLinks.length,0,"Mismatched GTFS snapshot generations must not offer pedestrian-review links tied to an unverified route pattern");
 assert.ok(mismatchedSnapshots.get("planSteps").children.some(x=>/Walking map links are disabled because Coast RTA stop or timetable snapshots/.test(x.textContent)),"Mismatched snapshot preview must explain why walking links are unavailable");
 const savedFreshJourneyStamp=freshWalk.state().journeys.downloaded_utc;
 freshWalk.state().journeys.downloaded_utc="2026-10-25T10:57:50Z"; // The already-rendered synthetic journey has its own timetable object.
 let mismatchClickPrevented=false;
 const mismatchClick=freshLinks[0].onclick({preventDefault(){mismatchClickPrevented=true}});
 assert.equal(mismatchClickPrevented,true,"Already-rendered walking links must reject a later timetable/stop snapshot mismatch");
 assert.equal(mismatchClick,false,"Snapshot mismatch must cancel external walking navigation");
 assert.match(freshWalk.get("planStatus").textContent,/Walking map links are disabled/);
 freshWalk.state().journeys.downloaded_utc=savedFreshJourneyStamp;

 journeys.downloaded_utc=savedJourneyStamp;
 console.log("PASS: mismatched stop and schedule refresh timestamps disable guided trip without hiding preview");
 console.log("PASS: old schedule or stop snapshots keep preview but disable spoken boarding");
 console.log("PASS: stored GTFS older than seven days triggers visible service-freshness warning");
 console.log("PASS: visible GTFS snapshot freshness and non-live warning");
 assert.equal(a.state().official.stops.length,stops.stops.length);
 assert.equal(a.state().journeys.trips.length,journeys.trips.length);
 await selectAndrews(a);
 assert.match(a.get("planFare").textContent,/^1 bus · 0 transfers/);
  assert.equal(a.get("guideStart").disabled,false,"When official and interpolated departures tie, prefer the published direct boarding from the confirmed origin");
  assert.doesNotMatch(a.get("planStatus").textContent,/time is interpolated/i,"Published Route 14 departure must not be replaced by a tied interpolated boarding");
 await a.click("openFare");assert.equal(String(a.get("boardings").value),"1");
 assert.equal(a.get("fareTotal").textContent,"$1.00 estimated");
 // Boardings are whole events. Decimal input must never underquote the fare.
 a.get("payment").value="tap";
 a.get("boardings").value="2.5";a.get("boardings").oninput();
 assert.equal(a.get("fareTotal").textContent,"$3.00 estimated","Round fractional boarding counts up, not down");
 a.get("boardings").value="9";a.get("boardings").oninput();
 assert.equal(a.get("fareTotal").textContent,"$3.50 estimated","Same-device contactless 24-hour cap");
 a.get("payment").value="cash";a.get("payment").onchange();
 assert.equal(a.get("fareTotal").textContent,"$9.00 estimated","Cash does not receive contactless fare cap");
 a.get("boardings").value="2.5";a.get("boardings").oninput();
 assert.equal(a.get("fareTotal").textContent,"$3.00 estimated","Cash fare also rounds to whole boardings");
 a.get("boardings").value="25";a.get("boardings").oninput();
 assert.equal(a.get("fareTotal").textContent,"$20.00 estimated","Fare calculator caps the supported input range at 20");
 a.get("boardings").value="1";a.get("payment").value="tap";a.get("payment").onchange();
 console.log("PASS: fare calculator whole-boardings, cash, contactless cap, and input bounds (mocked)");
 await a.click("fareDone");await a.click("guideStart");
 assert.equal(a.state().screen,"guide");
 assert.ok(a.spoken.some(s=>s.includes("WALK TO YOUR FIRST STOP")));
 await a.click("nextInstruction");assert.match(a.get("stepBody").textContent,new RegExp("official stop ID "+origin.id));
 await a.click("nextInstruction");assert.match(a.get("stepBody").textContent,/Get off at .*official stop ID TL-/);
 await a.click("nextInstruction");assert.match(a.get("stepBody").textContent,/Walk from .*official stop ID TL-/);
 await a.click("home");
 assert.equal(a.state().screen,"welcome");assert.equal(a.state().destination,null);
 console.log("PASS: GPS → place search → Route 14 → fare → mocked speech/Next → Home");
 const m=boot();await m.settle();await m.click("typeStart");
 m.get("address").value="Georgetown Transfer Center";await m.click("useAddress");
 assert.equal(m.state().screen,"found");assert.equal(m.get("yesLocation").disabled,false);
 console.log("PASS: typed origin → location confirmation");
 // Origin search must reject a same-number/street match in another named Coast RTA town.
 const cityOrigin=boot();await cityOrigin.settle();
 const wrongOrigin={lat:origin.lat,lon:origin.lon,name:"2379 Cypress Circle",address:"2379 Cypress Circle Georgetown South Carolina"};
 const correctOrigin={lat:interchange.lat,lon:interchange.lon,name:"2379 Cypress Circle",address:"2379 Cypress Circle Conway South Carolina"};
 assert.equal(cityOrigin.pickStartCandidate("2379 Cypress Circle Conway",[wrongOrigin]),null,
  "Typed Conway origin must not silently accept an otherwise matching Georgetown street");
 assert.equal(cityOrigin.pickStartCandidate("2379 Cypress Circle Conway",[wrongOrigin,correctOrigin]).address,correctOrigin.address,
  "Typed Conway origin should select only the correctly named town");
 await cityOrigin.click("typeStart");
 cityOrigin.get("address").value="2379 Cypress Circle Conway";await cityOrigin.click("useAddress");
 assert.equal(cityOrigin.state().screen,"found","Wrong-town Photon origin must fall back to the second free geocoder");
 assert.match(cityOrigin.get("foundAddress").textContent,/2379 Cypress Circle, Conway/);
 assert.doesNotMatch(cityOrigin.get("foundAddress").textContent,/Georgetown/);
 console.log("PASS: typed origin rejects wrong-town street match and uses correct-town free-geocoder fallback (mocked)");
 let resolve;const pending={promise:new Promise(r=>{resolve=r})};
 const stale=boot("2026-10-27T11:00:00Z",pending);await stale.settle();
 await stale.click("locate");assert.equal(stale.get("yesLocation").disabled,true);
 await stale.click("home");resolve({address:{road:"Old Street",city:"Georgetown"}});
 await stale.settle();assert.equal(stale.state().screen,"welcome");
 assert.equal(stale.get("yesLocation").disabled,true);
 console.log("PASS: abandoned GPS lookup cannot enable confirmation");
 const late=boot("2026-10-28T00:41:00Z");await late.settle();await selectAndrews(late);
 assert.equal(late.get("guideStart").disabled,true);
 assert.match(late.get("planStatus").textContent,/No reachable scheduled departures remain today/);
 console.log("PASS: no fabricated late-night departures");
 const expired=boot();await expired.settle();await selectAndrews(expired);
 assert.equal(expired.get("guideStart").disabled,false);
 expired.setInstant("2026-10-28T00:41:00Z"); // Rider leaves a valid itinerary open until after service ends.
 await expired.click("guideStart");
 assert.equal(expired.state().screen,"itinerary","Expired trip must not open spoken guidance");
 assert.equal(expired.get("guideStart").disabled,true);
 assert.match(expired.get("planStatus").textContent,/No reachable scheduled departures remain today/);
 console.log("PASS: starting an old itinerary rechecks time and blocks expired boarding");

 const activeAged=boot();await activeAged.settle();await selectAndrews(activeAged);
 await activeAged.click("guideStart");assert.equal(activeAged.state().screen,"guide");
 activeAged.setInstant("2026-11-05T12:00:00Z"); // Synthetic age-out while spoken guidance is open.
 await activeAged.click("nextInstruction");
 assert.equal(activeAged.state().screen,"itinerary","Next must not continue instructions from stale GTFS");
 assert.equal(activeAged.get("guideStart").disabled,true);
 assert.match(activeAged.get("planStatus").textContent,/Guided instructions stopped because the stored Coast RTA data is no longer reliable/);
 assert.ok(activeAged.spoken.some(s=>/Guided trip instructions stopped/.test(s)));
 console.log("PASS: active spoken navigation stops when GTFS ages out before Next");
 const activeMissed=boot();await activeMissed.settle();await selectAndrews(activeMissed);
 await activeMissed.click("guideStart");assert.equal(activeMissed.state().screen,"guide");
 activeMissed.setInstant("2026-10-27T12:31:00Z"); // 8:31 AM EDT, after the published 8:30 AM first boarding.
 await activeMissed.click("nextInstruction");
 assert.equal(activeMissed.state().screen,"itinerary","NEXT must not instruct boarding after the first scheduled departure has passed");
 assert.match(activeMissed.get("planStatus").textContent,/first scheduled boarding departure has passed while guidance was open/);
 assert.match(activeMissed.get("planStatus").textContent,/cannot verify whether you boarded/);
 console.log("PASS: NEXT halts unconfirmed pre-boarding guidance after scheduled departure passes");
 const activeMissedSpeech=boot();await activeMissedSpeech.settle();await selectAndrews(activeMissedSpeech);
 await activeMissedSpeech.click("guideStart");await activeMissedSpeech.click("nextInstruction");
 assert.equal(activeMissedSpeech.state().screen,"guide");
 activeMissedSpeech.setInstant("2026-10-27T12:31:00Z");
 await activeMissedSpeech.click("readInstruction");
 assert.equal(activeMissedSpeech.state().screen,"itinerary","READ TO ME must not repeat an expired boarding instruction");
 assert.match(activeMissedSpeech.get("planStatus").textContent,/first scheduled boarding departure has passed while guidance was open/);
 console.log("PASS: READ TO ME halts expired boarding guidance without inventing live status");

 const midnightGuide=boot();await midnightGuide.settle();await selectAndrews(midnightGuide);
 await midnightGuide.click("guideStart");assert.equal(midnightGuide.state().screen,"guide");
 midnightGuide.setInstant("2026-10-28T11:00:00Z"); // New local transit service date, snapshots still fresh.
 await midnightGuide.click("readInstruction");
 assert.equal(midnightGuide.state().screen,"itinerary","Read-to-me must not continue prior-day directions");
 assert.match(midnightGuide.get("planStatus").textContent,/Guided instructions stopped because the local transit service date changed/);
 console.log("PASS: read-to-me stops at service-date rollover and requires itinerary review");

 const transfer=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await transfer.settle();await selectAndrews(transfer);
 assert.match(transfer.get("planFare").textContent,/^2 buses · 1 transfer · Estimated standard cash fare \$2\.00/);
 assert.equal(transfer.get("guideStart").disabled,false);
 await transfer.click("guideStart");
 assert.ok(transfer.spoken.some(s=>s.includes("WALK TO YOUR FIRST STOP")));
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,/TEST ROUTE A/);assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+origin.id));
 assert.match(transfer.get("stepBody").textContent,/official trip destination sign unavailable/,"Whitespace-only GTFS headsign must not be announced as a destination");
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+interchange.id));
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+interchange.id));
 await transfer.click("nextInstruction"); // After TRANSFER, inspect BOARD BUS 2.
 assert.match(transfer.get("stepBody").textContent,/toward Andrews around/,"Valid headsign must be trimmed before being spoken");
 console.log("PASS: whitespace GTFS headsign fallback and trimmed destination sign");
 console.log("PASS: synthetic two-bus journey, one transfer, fare and mocked speech");

 // A second boarding deadline must be checked before announcing the transfer
 // and again while the transfer or second boarding instruction is on screen.
 const missedTransfer=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await missedTransfer.settle();await selectAndrews(missedTransfer);
 await missedTransfer.click("guideStart");await missedTransfer.click("nextInstruction");await missedTransfer.click("nextInstruction"); // GET OFF first bus
 missedTransfer.setInstant("2026-10-27T13:11:00Z"); // 9:11 AM EDT, after synthetic 9:10 transfer departure
 await missedTransfer.click("nextInstruction");
 assert.equal(missedTransfer.state().screen,"itinerary","NEXT must not announce a transfer after its scheduled boarding time passed");
 assert.match(missedTransfer.get("planStatus").textContent,/next scheduled boarding departure has passed while guidance was open/);
 console.log("PASS: NEXT blocks entry to a transfer step after the second bus departure");
 const missedTransferSpeech=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await missedTransferSpeech.settle();await selectAndrews(missedTransferSpeech);
 await missedTransferSpeech.click("guideStart");for(let i=0;i<3;i++)await missedTransferSpeech.click("nextInstruction"); // TRANSFER
 missedTransferSpeech.setInstant("2026-10-27T13:11:00Z");
 await missedTransferSpeech.click("readInstruction");
 assert.equal(missedTransferSpeech.state().screen,"itinerary","READ TO ME must not repeat a transfer instruction after its bus departed");
 assert.match(missedTransferSpeech.get("planStatus").textContent,/next scheduled boarding departure has passed while guidance was open/);
 console.log("PASS: READ TO ME blocks expired transfer instructions");
 const missedSecondBoard=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await missedSecondBoard.settle();await selectAndrews(missedSecondBoard);
 await missedSecondBoard.click("guideStart");for(let i=0;i<4;i++)await missedSecondBoard.click("nextInstruction"); // BOARD BUS 2
 missedSecondBoard.setInstant("2026-10-27T13:11:00Z");
 await missedSecondBoard.click("nextInstruction");
 assert.equal(missedSecondBoard.state().screen,"itinerary","NEXT must not continue an expired second boarding step");
 console.log("PASS: second boarding instruction expires when its scheduled departure passes");

 const estimatedBoard=boot("2026-10-27T11:00:00Z",null,syntheticEstimatedBoarding());await estimatedBoard.settle();await selectAndrews(estimatedBoard);
 assert.match(estimatedBoard.get("planFare").textContent,/^1 bus/,"Keep possible itinerary visible as an unverified preview");
 assert.match(estimatedBoard.get("planStatus").textContent,/first boarding time is interpolated/i);
 assert.equal(estimatedBoard.get("guideStart").disabled,true,"Unverified first departure must block spoken navigation");
 await estimatedBoard.click("guideStart");assert.equal(estimatedBoard.state().screen,"itinerary");
 console.log("PASS: estimated first boarding departure remains a preview and cannot start spoken guidance");
 const estimatedArrival=boot("2026-10-27T11:00:00Z",null,syntheticEstimatedArrival());await estimatedArrival.settle();await selectAndrews(estimatedArrival);
 assert.match(estimatedArrival.get("planFare").textContent,/^1 bus/,"Keep uncertain arrival visible as a preview");
 assert.match(estimatedArrival.get("planStatus").textContent,/boarding or alighting time is interpolated/i);
 assert.equal(estimatedArrival.get("guideStart").disabled,true,"Unpublished destination arrival must block spoken guidance");
 await estimatedArrival.click("guideStart");assert.equal(estimatedArrival.state().screen,"itinerary");
 const publishedArrival=syntheticEstimatedArrival();
 publishedArrival.trips.push({id:"QA-PUBLISHED-ARRIVAL",route:"TEST PUBLISHED ARRIVAL",service:"QA-TEST",stops:[
  {stop:origin.id,arr:"08:40:00",dep:"08:40:00"},
  {stop:target.id,arr:"09:40:00",dep:"09:40:00"}
 ]});
 const safeArrival=boot("2026-10-27T11:00:00Z",null,publishedArrival);await safeArrival.settle();await selectAndrews(safeArrival);
 assert.equal(safeArrival.get("guideStart").disabled,false,"Prefer published arrival over earlier interpolated alighting time");
 await safeArrival.click("guideStart");assert.equal(safeArrival.state().screen,"guide");
 await safeArrival.click("nextInstruction");assert.match(safeArrival.get("stepBody").textContent,/TEST PUBLISHED ARRIVAL/);
 console.log("PASS: interpolated arrival blocks speech and published-time alternative wins");
 const short=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:04:00"));await short.settle();await selectAndrews(short);
 assert.equal(short.get("guideStart").disabled,true);
 assert.match(short.get("planStatus").textContent,/could not confirm a scheduled bus connection/);
  assert.match(short.get("planStatus").textContent,/checks up to three transfers/,"A failed search must disclose the current three-transfer search limit");
  assert.match(short.get("planStatus").textContent,/does not mean Coast RTA has no service/,"A failed search must not be mistaken for proof of no service");
 console.log("PASS: synthetic transfer under five minutes is rejected");
 // A distinct mapped transfer stop near Conway Terminal is NOT a verified walk.
 // This is a synthetic trip fixture, not an actual Coast RTA connection.
 const crossStopFixture=syntheticTransfer("09:15:00");
 const otherConwayStop=stops.stops.find(s=>s.id==="TL-365");
 assert.ok(otherConwayStop&&otherConwayStop.id!==interchange.id,"Distinct nearby Conway transfer stop fixture missing");
 crossStopFixture.trips[1].stops[0].stop=otherConwayStop.id;
 const crossStop=boot("2026-10-27T11:00:00Z",null,crossStopFixture);await crossStop.settle();await selectAndrews(crossStop);
 assert.match(crossStop.get("planFare").textContent,/^2 buses · 1 transfer/,"Keep cross-stop route as preview");
 assert.match(crossStop.get("planStatus").textContent,/WARNING: This itinerary requires walking between different transfer stops/);
 assert.match(crossStop.get("planStatus").textContent,/up to [0-9]+ meters straight-line/);
 assert.match(crossStop.get("planStatus").textContent,/No safe or accessible pedestrian route, crossing, or boarding side has been verified/);
 assert.equal(crossStop.get("guideStart").disabled,true,"Cross-stop transfer must never authorize spoken guidance");
 await crossStop.click("guideStart");
 assert.equal(crossStop.state().screen,"itinerary","Disabled cross-stop trip must remain in preview");
 console.log("PASS: synthetic cross-stop transfer displays prominent walking safety warning and blocks guided trip");
 const uncertainArrival=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:10:00",[],"arrival"));await uncertainArrival.settle();await selectAndrews(uncertainArrival);
 assert.equal(uncertainArrival.get("guideStart").disabled,true,"Interpolated transfer arrival must not be advertised as a confirmed connection");
 assert.match(uncertainArrival.get("planStatus").textContent,/could not confirm a scheduled bus connection/);
 console.log("PASS: interpolated transfer arrival cannot authorize guided connection");
 const uncertainDeparture=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:10:00",[],"departure"));await uncertainDeparture.settle();await selectAndrews(uncertainDeparture);
 assert.equal(uncertainDeparture.get("guideStart").disabled,true,"Interpolated onward departure must not be advertised as a confirmed connection");
 assert.match(uncertainDeparture.get("planStatus").textContent,/could not confirm a scheduled bus connection/);
 console.log("PASS: interpolated onward departure cannot authorize guided connection");
 const removed=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:10:00",[{service_id:"QA-TEST",date:"20261027",exception_type:"2"}]));await removed.settle();await selectAndrews(removed);
 assert.equal(removed.get("guideStart").disabled,true);
 console.log("PASS: removed service-calendar exception blocks itinerary");
 const holiday=boot("2026-11-26T12:00:00Z");await holiday.settle();await selectAndrews(holiday);
 assert.equal(holiday.get("guideStart").disabled,true);
 assert.match(holiday.get("planStatus").textContent,/No Coast RTA fixed-route service is scheduled today/);
 console.log("PASS: Thanksgiving holiday does not generate an itinerary");

 // Coast RTA's published non-service holidays must remain fail-closed
 // even though the current official GTFS snapshot has no dated exceptions.
 // All fixture timestamps are 10 AM in America/New_York, not live bus times.
 for(const [label,instant] of [
  ["Christmas Day 2026","2026-12-25T15:00:00Z"],
  ["New Year's Day 2027","2027-01-01T15:00:00Z"],
  ["Thanksgiving Day 2027","2027-11-25T15:00:00Z"]
 ]){
  const closed=boot(instant);await closed.settle();await selectAndrews(closed);
  assert.equal(closed.get("guideStart").disabled,true,label+" must not enable guided boarding");
  assert.match(closed.get("planStatus").textContent,/No Coast RTA fixed-route service is scheduled today/,label+" must explain the holiday closure");
  assert.match(closed.get("planFare").textContent,/No scheduled bus service/,label+" must not quote an active trip fare");
 }
 console.log("PASS: Christmas and New Year's Day holiday closures, plus next-year Thanksgiving, block guided journeys");
 const denied=boot("2026-10-27T11:00:00Z",null,null,"gps-denied");await denied.settle();await denied.click("locate");await denied.settle();
 assert.equal(denied.state().screen,"problem");
 assert.match(denied.get("problemText").textContent,/Permission denied/);
 assert.equal(denied.get("locate").disabled,false);
 await denied.click("enterInstead");assert.equal(denied.state().screen,"manual");
 console.log("PASS: GPS permission denied offers typed location fallback");
  const hungGps=boot("2026-10-27T11:00:00Z",null,null,"gps-hang");await hungGps.settle();
  await hungGps.click("locate");assert.equal(hungGps.get("locate").disabled,true);
  hungGps.triggerTimers();
  assert.equal(hungGps.state().screen,"problem","GPS watchdog must release a stalled location request");
  assert.equal(hungGps.get("locate").disabled,false,"GPS retry must not remain disabled");
  assert.equal(hungGps.state().pos,null,"No location may be fabricated on timeout");
  assert.match(hungGps.get("problemText").textContent,/GPS did not respond within 30 seconds/);
  await hungGps.click("enterInstead");assert.equal(hungGps.state().screen,"manual");
  const lateGps=boot("2026-10-27T11:00:00Z",null,null,"gps-late");await lateGps.settle();
  await lateGps.click("locate");lateGps.triggerTimers();assert.equal(lateGps.state().screen,"problem");
  lateGps.lateGps();await lateGps.settle();
  assert.equal(lateGps.state().screen,"problem","Late GPS success must not override timeout warning");
  assert.equal(lateGps.state().pos,null,"Late GPS result must not silently set a location");
  console.log("PASS: GPS watchdog restores retry and ignores late callbacks (mocked Android GPS stall)");
 const offline=boot("2026-10-27T11:00:00Z",null,null,"stops-offline");await offline.settle();
 assert.equal(offline.state().official,null);
 assert.match(offline.get("dataStatus").textContent,/stop data unavailable/i);
 await offline.click("locate");await offline.settle();await offline.click("yesLocation");await offline.click("goNearest");
 assert.equal(offline.state().screen,"problem");
 assert.match(offline.get("problemText").textContent,/Official Coast RTA stop data is unavailable/);
 console.log("PASS: unavailable official stop data blocks unverified nearest-stop recommendation");
 const schedulesDown=boot("2026-10-27T11:00:00Z",null,null,"journeys-offline");await schedulesDown.settle();
 assert.match(schedulesDown.get("dataStatus").textContent,/trip schedules unavailable/i);
 await selectAndrews(schedulesDown);
 assert.equal(schedulesDown.get("guideStart").disabled,true);
 assert.match(schedulesDown.get("planStatus").textContent,/route data could not be loaded/i,"A failed timetable must not leave a permanent Loading message");
 assert.match(schedulesDown.get("planStatus").textContent,/Do not start a trip/i,"A failed timetable must fail closed");
 assert.match(schedulesDown.get("planFare").textContent,/Fare unavailable; no trip verified/);
 assert.equal(schedulesDown.get("planSteps").children.length,1,"Failed timetable must offer one actionable contact option, not stale route steps");
 assert.equal(schedulesDown.get("planSteps").children[0].href,"tel:8434880865");
 console.log("PASS: unavailable journey schedule shows actionable failure, clears stale steps, and disables guided trip");
 const nearby=boot();await nearby.settle();await nearby.click("locate");await nearby.settle();await nearby.click("yesLocation");await nearby.click("goNearest");
 assert.equal(nearby.state().screen,"nearest");
 assert.match(nearby.get("stopDetails").textContent,/STRAIGHT-LINE \(not a verified walk\)/);
 assert.ok(nearby.spoken.some(s=>/mapped bus stop.*official stop ID TL-/i.test(s)),"Nearest-stop spoken guidance must distinguish duplicated names by ID");
 await nearby.click("differentStop");
 assert.match(nearby.get("stopOptions").children[0].textContent,/stop ID TL-/);
 await nearby.get("stopOptions").children[0].onclick();
 await nearby.click("chooseStop");assert.equal(nearby.state().screen,"walk");
 assert.match(nearby.get("walkStop").textContent,/official stop ID TL-/);
 assert.ok(nearby.spoken.some(s=>/Review external walking directions for .*official stop ID TL-/.test(s)),"Walking-review spoken guidance must include stop ID");
  assert.ok(nearby.spoken.some(s=>/walking route, accessible crossings, and boarding side are not verified/i.test(s)),"Spoken review must disclose unverified pedestrian safety");
 assert.match(nearby.get("walkLink").href,/travelmode=walking/);
 console.log("PASS: nearest official mapped stop shows unverified-walk warning and walking map link");
 // Conway Terminal has many route patterns; a two-pattern preview must not imply exclusivity.
 assert.ok(html.includes("CHECK ALL OFFICIAL COAST RTA ROUTES"));
 assert.ok(html.includes("https://coastrta.com/routes-and-schedules/"));
 const routeHub=boot();await routeHub.settle();await routeHub.click("locate");await routeHub.settle();await routeHub.click("yesLocation");
 Object.assign(routeHub.state().pos,{lat:interchange.lat,lon:interchange.lon});
 await routeHub.click("goNearest");
 assert.equal(routeHub.get("stopName").textContent,"Conway Terminal");
 assert.match(routeHub.get("stopDetails").textContent,new RegExp(interchange.routes.length+" stored route patterns"));
 assert.match(routeHub.get("stopDetails").textContent,/additional patterns not shown/);
 assert.match(routeHub.get("stopDetails").textContent,/official Coast RTA route guide/);
 console.log("PASS: high-connection stops disclose route-pattern count and link to agency schedules");
 nearby.setInstant("2026-11-05T12:00:00Z"); // Simulate the stored stop inventory aging while the walk screen remains open.
 let blockedWalk=false;
 const blockedResult=nearby.get("walkLink").onclick({preventDefault(){blockedWalk=true}});
 assert.equal(blockedWalk,true,"Opening a displayed walking link must recheck stop freshness");
 assert.equal(blockedResult,false,"Stale walking-map navigation must be cancelled");
 assert.equal(nearby.get("walkLink").href,undefined,"Stale walking-map link must lose its destination");
 assert.match(nearby.get("walkStop").textContent,/Walking directions are disabled/);
 assert.ok(nearby.spoken.some(s=>/Stop locations are no longer current/i.test(s)));
 console.log("PASS: nearest-stop walking map link rechecks freshness at click time");
 const distant=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await distant.settle();await selectAndrews(distant);
 distant.state().destination.lat=target.lat+0.03; // Deliberately synthetic ~3.3 km final walk, not a real address.
 await distant.click("yesDestination");
 assert.match(distant.get("planStatus").textContent,/last stop is [0-9]+ meters straight-line/);
 assert.equal(distant.get("guideStart").disabled,true);
 const distantWalkingLinks=distant.get("planSteps").children.filter(x=>x.tagName==="A"&&/WALK|WALKING ROUTE/.test(x.textContent));
 assert.equal(distantWalkingLinks.length,0,"Do not offer walking-map links for an itinerary with an unconfirmed distant final leg");
 assert.ok(distant.get("planSteps").children.some(x=>/Walking map links are disabled because the final stop/.test(x.textContent)),"Explain why walking links are withheld");
 console.log("PASS: synthetic distant final walk blocks guided trip and both walking-map links");
 const ambiguous=boot();await ambiguous.settle();await ambiguous.click("locate");await ambiguous.settle();await ambiguous.click("yesLocation");await ambiguous.click("goDestination");
 ambiguous.get("destinationInput").value="Walmart";await ambiguous.click("findTrip");
 assert.equal(ambiguous.state().screen,"searchResults");
 assert.equal(ambiguous.get("placeResults").children.length,2);
 assert.equal(ambiguous.state().destination,null);
 const candidates=ambiguous.get("placeResults").children;
 assert.notEqual(candidates[0].children[1].textContent,candidates[1].children[1].textContent);
 await candidates[1].onclick();assert.equal(ambiguous.state().screen,"confirmDestination");
 assert.match(ambiguous.get("destinationAddress").textContent,/456 Sample Street/);
 await ambiguous.click("noDestination");assert.equal(ambiguous.state().screen,"searchResults");assert.equal(ambiguous.state().destination,null,"Rejected destination must not persist");
 await candidates[0].onclick();assert.equal(ambiguous.state().screen,"confirmDestination");
 await ambiguous.click("back");assert.equal(ambiguous.state().screen,"searchResults");assert.equal(ambiguous.state().destination,null,"Back from destination confirmation must clear abandoned choice");
 console.log("PASS: rejecting or backing out of a suggested destination clears the selection");
 const unknown=boot();await unknown.settle();await unknown.click("locate");await unknown.settle();await unknown.click("yesLocation");await unknown.click("goDestination");
 unknown.get("destinationInput").value="ZZZ Unknown Shop";await unknown.click("findTrip");
 assert.equal(unknown.state().screen,"destination");
 assert.equal(unknown.state().destination,null);
 assert.match(unknown.get("tripStatus").textContent,/couldn't find that business name/);
 console.log("PASS: unlisted business does not fabricate a destination");
 const changed=boot();await changed.settle();await selectAndrews(changed);
 await changed.click("changeTrip");assert.equal(changed.state().screen,"destination");assert.equal(changed.state().destination,null,"Changing trip must clear old destination");
 assert.equal(changed.get("guideStart").disabled,true,"Old guidance must be disabled while selecting a new destination");
 await changed.click("back");assert.equal(changed.state().screen,"chooseGoal","Back must not reopen a stale itinerary");
 console.log("PASS: change trip clears old destination, disables old guidance, and avoids stale itinerary history");

 const publishedAlternative=syntheticEstimatedBoarding();
 publishedAlternative.trips.push({id:"QA-PUBLISHED-ALTERNATIVE",route:"TEST PUBLISHED ALTERNATIVE",service:"QA-TEST",stops:[
  {stop:origin.id,arr:"09:00:00",dep:"09:00:00"},
  {stop:target.id,arr:"10:00:00",dep:"10:00:00"}
 ]});
 const preferred=boot("2026-10-27T11:00:00Z",null,publishedAlternative);await preferred.settle();await selectAndrews(preferred);
 assert.equal(preferred.get("guideStart").disabled,false,"A later published-time departure must not be hidden by an earlier interpolated one");
 assert.match(preferred.get("planStatus").textContent,/Scheduled itinerary preview/);
 await preferred.click("guideStart");assert.equal(preferred.state().screen,"guide");
 await preferred.click("nextInstruction");
 assert.match(preferred.get("stepBody").textContent,/TEST PUBLISHED ALTERNATIVE/);
 console.log("PASS: later published-time boarding beats an earlier interpolated preview");
 // Synthetic near-miss at 07:08 local: the old three-minute lead accepted this as reachable.
 // Ten minutes is only a conservative screening floor, not an accessible walking guarantee.
 const soonFixture=syntheticTransfer();
 soonFixture.trips=[{id:"QA-TOO-SOON",route:"TEST TOO SOON",service:"QA-TEST",stops:[
  {stop:origin.id,arr:"07:08:00",dep:"07:08:00"},
  {stop:target.id,arr:"08:00:00",dep:"08:00:00"}
 ]}];
 const soon=boot("2026-10-27T11:00:00Z",null,soonFixture);await soon.settle();await selectAndrews(soon);
 assert.equal(soon.get("guideStart").disabled,true,"Do not authorize a bus leaving in eight minutes even from the mapped boarding stop");
 assert.match(soon.get("planStatus").textContent,/No reachable scheduled departures remain today/);
 console.log("PASS: eight-minute departure fails conservative boarding lead-time screening");

 const laterFixture=syntheticTransfer();
 laterFixture.trips=[...soonFixture.trips,{id:"QA-BOARDING-WINDOW",route:"TEST LATER BOARDING",service:"QA-TEST",stops:[
  {stop:origin.id,arr:"07:25:00",dep:"07:25:00"},
  {stop:target.id,arr:"08:20:00",dep:"08:20:00"}
 ]}];
 const later=boot("2026-10-27T11:00:00Z",null,laterFixture);await later.settle();await selectAndrews(later);
 assert.equal(later.get("guideStart").disabled,false,"Later published departure must remain selectable");
 await later.click("guideStart");assert.equal(later.state().screen,"guide");
 await later.click("nextInstruction");assert.match(later.get("stepBody").textContent,/TEST LATER BOARDING/);
 console.log("PASS: later published boarding remains selectable after conservative screening");

 // Duplicate labels are not interchangeable boarding points. These are real
 // committed stop IDs, but the navigation interactions remain mocked.
 const bucksportA=stops.stops.find(s=>s.id==="TL-651");
 const bucksportB=stops.stops.find(s=>s.id==="TL-733");
 assert.ok(bucksportA&&bucksportB&&bucksportA.name.trim()===bucksportB.name.trim(),"Bucksport same-name fixture missing");
 const nameRisk=boot();await nameRisk.settle();await nameRisk.click("locate");await nameRisk.settle();
 await nameRisk.click("yesLocation");
 Object.assign(nameRisk.state().pos,{lat:bucksportA.lat,lon:bucksportA.lon});
 await nameRisk.click("goNearest");
 assert.equal(nameRisk.state().screen,"nearest");
 assert.match(nameRisk.spoken.at(-1),/not necessarily a boarding stop for your destination/);
 assert.equal(nameRisk.get("stopName").textContent.trim(),"Bucksport Marina");
 assert.match(nameRisk.get("stopDetails").textContent,/Another mapped Coast RTA stop shares this name more than 1 km away/);
 assert.match(nameRisk.spoken.at(-1),/Confirm the official stop ID and exact location with Coast RTA/);
 const andrewsA=stops.stops.find(s=>s.id==="TL-285");
 const andrewsB=stops.stops.find(s=>s.id==="TL-940");
 assert.ok(andrewsA&&andrewsB&&andrewsA.name===andrewsB.name,"Andrews boarding-side fixture missing");
 const sideRisk=boot();await sideRisk.settle();await sideRisk.click("locate");await sideRisk.settle();
 await sideRisk.click("yesLocation");
 Object.assign(sideRisk.state().pos,{lat:andrewsA.lat,lon:andrewsA.lon});
 await sideRisk.click("goNearest");
 assert.match(sideRisk.get("stopDetails").textContent,/may have different boarding sides/);
 assert.match(sideRisk.spoken.at(-1),/correct side with Coast RTA/);
 const routeRisk=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await routeRisk.settle();await selectAndrews(routeRisk);
 assert.ok(routeRisk.get("planSteps").children.some(p=>p.children?.some(n=>/Multiple mapped Coast RTA stops share this name/.test(n.textContent||""))),"Itinerary must disclose same-name alighting-stop ambiguity");
 console.log("PASS: far-apart and nearby same-name stops trigger visible and spoken stop-ID/boarding-side cautions (mocked)");
 const spacedName=boot();await spacedName.settle();await spacedName.click("locate");await spacedName.settle();await spacedName.click("yesLocation");await spacedName.click("goDestination");
 spacedName.get("destinationInput").value="Belle Isle  Bistro";
 await spacedName.click("findTrip");
 assert.equal(spacedName.state().screen,"searchResults","Extra spaces in a typed business name must still trigger the known-address fallback");
 assert.ok(spacedName.get("placeResults").children.length,"Known-address fallback must return a selectable, confirmable result");
 assert.match(spacedName.get("placeResults").children[0].children[0].textContent,/Belle Isle Bistro/);
 console.log("PASS: repeated spaces in typed Belle Isle Bistro still reach confirmable known-address fallback (mocked)");
 // The official facility uses PruittHealth, but riders often type Pruitt Health.
 // Both names must reach the same confirmed Conway address, not an unrelated city.
 for(const typedName of ["Pruitt Health","PruittHealth Conway"]){
  const care=boot();await care.settle();await care.click("locate");await care.settle();
  await care.click("yesLocation");await care.click("goDestination");
  care.get("destinationInput").value=typedName;await care.click("findTrip");
  assert.equal(care.state().screen,"searchResults","Spaced/unspaced PruittHealth name must return selectable results: "+typedName);
  const entries=care.get("placeResults").children;
  assert.ok(entries.length,"Expected a confirmed Conway place result: "+typedName);
  assert.match(entries[0].children[1].textContent,/2379 Cypress Circle, Conway, SC/);
  await entries[0].onclick();
  assert.equal(care.state().screen,"confirmDestination");
  assert.match(care.get("destinationAddress").textContent,/2379 Cypress Circle, Conway, SC/);
 }
 console.log("PASS: spaced and unspaced PruittHealth business names resolve to the same confirmable Conway address (mocked)");
 // The Nov 1, 2026 US Eastern DST fall-back repeats 1:30 AM. Neither
 // occurrence may turn headway-only Coast RTA data into exact boarding guidance.
 // These are synthetic clock checks, not proof of service or phone navigation.
 for(const [label,instant] of [
  ["first 1:30 AM (EDT)","2026-11-01T05:30:00Z"],
  ["second 1:30 AM (EST)","2026-11-01T06:30:00Z"]
 ]){
  const fold=boot(instant,null,null,"frequency-unverified");
  await fold.settle();await selectAndrews(fold);
  assert.equal(fold.state().screen,"itinerary",label+" must still reach the review screen");
  assert.equal(fold.get("guideStart").disabled,true,label+" must never authorize headway-only boarding");
  await fold.click("guideStart");
  assert.equal(fold.state().screen,"itinerary",label+" must not start guidance when clicked");
 }
 console.log("PASS: both repeated 1:30 AM DST clock hours refuse frequency-unverified guided boarding (mocked)");
 console.log("Source-level mocked regressions passed. NOT a live/Android safety certification.");
}
// Regression: merging two frontier paths by only (stop, last route) loses a valid
// third transfer when the paths used different earlier routes. All stops/routes
// here are synthetic; this does not certify Coast RTA service or safe walking.
{
 const begin=script.indexOf("function possibleRoutePattern(){");
 const end=script.indexOf("function showPossiblePattern(",begin);
 assert.ok(begin>=0&&end>begin,"Untimed multi-transfer planner source missing");
 const isolated=script.slice(begin,end);
 const stop=(id,lat)=>({id,name:id,lat,lon:0,routes:[]});
 const trip=(route,from,to)=>({route,service:"QA",stops:[{stop:from},{stop:to}]});
 const candidate=new Function("official","journeys","pos","destination","distance","serviceSet",isolated+";return possibleRoutePattern();")(
  {stops:[stop("S",0),stop("X",10000),stop("Y",20000),stop("Z",30000)]},
  {trips:[trip("A","S","X"),trip("B","S","X"),trip("C","X","Y"),trip("A","Y","Z")]},
  {lat:0,lon:0},{lat:30000,lon:0},(a,b)=>Math.abs(a.lat-b.lat),()=>new Set(["QA"]));
 assert.deepEqual(candidate?.legs.map(leg=>leg.trip.route),["B","C","A"],
  "Distinct earlier-route histories must survive pruning to permit three-bus transfer patterns");
 console.log("PASS: synthetic three-bus fallback preserves alternate earlier-route history (not a confirmed trip)");
}
// Reverse GPS lookup must never invent a South Carolina street address for
// coordinates in another state, or claim an address when the provider gives none.
async function testReverseGeocodeAddressSafety(){
 const begin=script.indexOf("async function reverse(lat,lon){");
 const end=script.indexOf("async function gotPosition(",begin);
 assert.ok(begin>=0&&end>begin,"GPS reverse-geocoding handler missing");
 const isolated=script.slice(begin,end);
 const Controller=class{constructor(){this.signal={aborted:false}}abort(){this.signal.aborted=true}};
 const fakeWindow={setTimeout:()=>1,clearTimeout:()=>{}};
 async function reverseMock(address){
  const fetch=async()=>({ok:true,json:async()=>({address})});
  const fn=new Function("fetch","AbortController","window",isolated+";return reverse;")(fetch,Controller,fakeWindow);
  return fn(34.5,-78.5);
 }
 const outOfState=await reverseMock({house_number:"15",road:"Main Street",city:"Tabor City",state:"North Carolina"});
 assert.match(outOfState,/Tabor City, North Carolina/);
 assert.doesNotMatch(outOfState,/South Carolina/);
 const noStreet=await reverseMock({city:"Georgetown",state:"South Carolina"});
 assert.match(noStreet,/street address unavailable/,"Do not claim a street address from city-only results");
 const valid=await reverseMock({house_number:"7",road:"King Street",city:"Georgetown",state:"South Carolina"});
 assert.match(valid,/7 King Street, Georgetown, South Carolina/);
 console.log("PASS: GPS reverse lookup preserves provider state and refuses missing street address (mocked)");
}
testReverseGeocodeAddressSafety().then(main).catch(e=>{console.error(e);process.exitCode=1});
