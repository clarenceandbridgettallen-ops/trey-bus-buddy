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
// Two current official Coast RTA pages conflict: contactless-fare-payment says 5–7 PM,
// how-to-ride says 3–6 PM. Do not assert either is the authoritative peak window.
assert.match(html,/official pages disagree on afternoon peak hours \(3–6 PM versus 5–7 PM\)/);
assert.match(html,/Do not assume a free ride: budget \$1 per boarding/);
assert.match(html,/https:\/\/coastrta\.com\/contactless-fare-payment\//);
assert.match(html,/https:\/\/coastrta\.com\/how-to-ride\//);
console.log("PASS: contradictory official peak-hour fare pages disclosed without claiming a free ride");

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
 const spoken=[],speechSynthesis={cancel(){},speak:u=>spoken.push(u.text)};
 // Exercise the supported reduced-motion path so visual transition timers cannot delay journey assertions.
  const window={scrollTo(){},speechSynthesis,matchMedia:query=>({matches:query==="(prefers-reduced-motion: reduce)"})};
 const navigator={geolocation:{getCurrentPosition:(ok,fail)=>fault==="gps-denied"?fail({message:"Permission denied"}):ok({coords:{latitude:origin.lat,longitude:origin.lon,accuracy:14}})},clipboard:{writeText:async()=>{}}};
 class FixedDate extends Date{constructor(...a){super(...(a.length?a:[clockInstant]))}static now(){return new Date(clockInstant).getTime()}}
 const feature=s=>({geometry:{coordinates:[s.lon,s.lat]},properties:{name:s.name,city:"Georgetown",state:"South Carolina"}});
 const fetch=async url=>{
  const u=String(url);
  if(u.includes("coast-rta-stops.json"))return {ok:fault!=="stops-offline",json:async()=>stops};
  if(u.includes("coast-rta-journeys.json"))return {ok:fault!=="journeys-offline",json:async()=>fault==="frequency-unverified"?structuredClone(committedJourneys):{...(fixtureJourneys||journeys),frequency_coverage:{status:"no_frequency_rows"}}};
  if(u.includes("/reverse?"))return {ok:true,json:deferred?()=>deferred.promise:async()=>({address:{road:"Lynch Street",city:"Georgetown"}})};
  if(u.includes("photon.komoot.io")){const q=decodeURIComponent(u.split("&q=")[1]||"").toLowerCase();if(q.includes("walmart"))return {ok:true,json:async()=>({features:[{geometry:{coordinates:[target.lon,target.lat]},properties:{name:"Walmart",housenumber:"123",street:"Test Road",city:"Andrews",state:"South Carolina"}},{geometry:{coordinates:[interchange.lon,interchange.lat]},properties:{name:"Walmart",housenumber:"456",street:"Sample Street",city:"Conway",state:"South Carolina"}}]})};return {ok:true,json:async()=>({features:q.includes("andrews")?[feature(target)]:q.includes("georgetown")?[feature(origin)]:[]})}}
  if(u.includes("nominatim.openstreetmap.org"))return {ok:true,json:async()=>u.includes("1228%20Belle%20Isle%20Road")?[{lat:String(origin.lat+0.01),lon:String(origin.lon+0.01),name:"Belle Isle Bistro",display_name:"1228 Belle Isle Road, Georgetown, SC"}]:[]};
  throw Error("Unexpected mock fetch: "+u);
 };
 const ctx={document,window,navigator,fetch,speechSynthesis,SpeechSynthesisUtterance:class{constructor(text){this.text=text}},Date:FixedDate,Intl,console};
 const api=vm.runInNewContext(script+"\n({state:()=>({screen,pos,destination,official,journeys}),nearbyStopCaution:nearbyDistinctStopCaution})",ctx,{timeout:5000});
 const click=async id=>{assert.equal(typeof get(id).onclick,"function","Missing handler "+id);await get(id).onclick()};
 const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve()};
 return {get,click,settle,spoken,state:api.state,nearbyStopCaution:api.nearbyStopCaution,setInstant:next=>{clockInstant=next}};
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
 const frequencyBlocked=boot("2026-10-27T11:00:00Z",null,null,"frequency-unverified");
 await frequencyBlocked.settle();await selectAndrews(frequencyBlocked);
 assert.equal(frequencyBlocked.get("guideStart").disabled,true,"Unverified frequency-based timetable must not start spoken boarding");
 assert.match(frequencyBlocked.get("planStatus").textContent,/frequency-based service.*START MY TRIP is disabled/);
 assert.match(frequencyBlocked.get("dataStatus").textContent,/frequency-based trips absent from this timetable/);
 assert.ok(frequencyBlocked.get("planSteps").children.length,"Keep itinerary preview available for review");
 await frequencyBlocked.click("guideStart");assert.equal(frequencyBlocked.state().screen,"itinerary");
 console.log("PASS: unverified Coast RTA frequency templates cannot authorize exact-time spoken boarding");
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
 // Approved v38 keeps raw feed diagnostics off the welcome screen; itinerary safety warnings remain separately tested.
 assert.match(html,/#dataStatus\{display:none!important\}/,"Technical feed diagnostics should stay off the welcome screen");
 assert.match(a.get("dataStatus").textContent,new RegExp(stops.stops.length+" mapped stops, "+journeys.trips.length+" scheduled trips"));
 const dateLabel=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",year:"numeric"}).format(new Date(journeys.downloaded_utc));
 assert.ok(a.get("dataStatus").textContent.includes("Snapshot "+dateLabel),"Displayed snapshot date must match deterministic QA fixture");
 assert.match(a.get("dataStatus").textContent,/Not live arrivals; walking routes unverified/);
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
 console.log("PASS: unavailable journey schedule is visibly disclosed and disables guided trip");
 const nearby=boot();await nearby.settle();await nearby.click("locate");await nearby.settle();await nearby.click("yesLocation");await nearby.click("goNearest");
 assert.equal(nearby.state().screen,"nearest");
 assert.match(nearby.get("stopDetails").textContent,/STRAIGHT-LINE \(not a verified walk\)/);
 assert.ok(nearby.spoken.some(s=>/mapped bus stop.*official stop ID TL-/i.test(s)),"Nearest-stop spoken guidance must distinguish duplicated names by ID");
 await nearby.click("differentStop");
 assert.match(nearby.get("stopOptions").children[0].textContent,/stop ID TL-/);
 await nearby.get("stopOptions").children[0].onclick();
 await nearby.click("chooseStop");assert.equal(nearby.state().screen,"walk");
 assert.match(nearby.get("walkStop").textContent,/official stop ID TL-/);
 assert.ok(nearby.spoken.some(s=>/Ready to walk to .*official stop ID TL-/.test(s)),"Walk-start spoken guidance must include stop ID");
 assert.match(nearby.get("walkLink").href,/travelmode=walking/);
 console.log("PASS: nearest official mapped stop shows unverified-walk warning and walking map link");
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
 console.log("Source-level mocked regressions passed. NOT a live/Android safety certification.");
}
main().catch(e=>{console.error(e);process.exitCode=1});
