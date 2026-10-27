"use strict";
// Dependency-free source-level mock. NOT a live-browser, Android or walking-safety test.
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),path=require("node:path");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
const stops=JSON.parse(fs.readFileSync(path.join(root,"data/coast-rta-stops.json"),"utf8"));
const journeys=JSON.parse(fs.readFileSync(path.join(root,"data/coast-rta-journeys.json"),"utf8"));
const script=html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script&&stops.stops.length>=50&&journeys.trips.length);
const origin=stops.stops.find(s=>/Georgetown Transfer Center/i.test(s.name));
const target=stops.stops.find(s=>/Andrews Piggly Wiggly/i.test(s.name));
assert.ok(origin&&target,"Official Route 14 fixture stops absent");
const interchange=stops.stops.find(s=>s.name==="Conway Terminal");
assert.ok(interchange,"Conway transfer fixture stop absent");
// Deliberately synthetic timetables, never presented as Coast RTA departure claims.
function syntheticTransfer(secondDeparture="09:10:00",exceptions=[]){
 const service="QA-TEST";
 return {source:"synthetic regression only",calendar:[{service_id:service,start_date:"20260101",end_date:"20261231",monday:"1",tuesday:"1",wednesday:"1",thursday:"1",friday:"1",saturday:"1",sunday:"1"}],exceptions,trips:[
  {id:"QA-A",route:"TEST ROUTE A",service,stops:[{stop:origin.id,arr:"08:30:00",dep:"08:30:00"},{stop:interchange.id,arr:"09:00:00",dep:"09:00:00"}]},
  {id:"QA-B",route:"TEST ROUTE B",service,stops:[{stop:interchange.id,arr:secondDeparture,dep:secondDeparture},{stop:target.id,arr:"10:00:00",dep:"10:00:00"}]}
 ]};
}
class El{
 constructor(id="",tag="DIV"){this.id=id;this.tagName=tag;this.textContent="";this.value="";this.disabled=false;this.children=[];this.style={};this.classList={toggle(){}}}
 append(...x){this.children.push(...x)}
 replaceChildren(...x){this.children=[...x]}
 setAttribute(){}
 focus(){}
}
function boot(instant="2026-10-27T11:00:00Z",deferred=null,fixtureJourneys=null,fault=null){
 const ids=[...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(x=>x[1]);
 const els=new Map(ids.map(x=>[x,new El(x)]));
 const get=id=>{if(!els.has(id))els.set(id,new El(id));return els.get(id)};
 const document={getElementById:get,querySelectorAll:()=>ids.map(get),querySelector:()=>new El("heading","H2"),createElement:t=>new El("",t.toUpperCase()),createTextNode:t=>({textContent:t})};
 const spoken=[],speechSynthesis={cancel(){},speak:u=>spoken.push(u.text)};
 const window={scrollTo(){},speechSynthesis};
 const navigator={geolocation:{getCurrentPosition:(ok,fail)=>fault==="gps-denied"?fail({message:"Permission denied"}):ok({coords:{latitude:origin.lat,longitude:origin.lon,accuracy:14}})},clipboard:{writeText:async()=>{}}};
 class FixedDate extends Date{constructor(...a){super(...(a.length?a:[instant]))}static now(){return new Date(instant).getTime()}}
 const feature=s=>({geometry:{coordinates:[s.lon,s.lat]},properties:{name:s.name,city:"Georgetown",state:"South Carolina"}});
 const fetch=async url=>{
  const u=String(url);
  if(u.includes("coast-rta-stops.json"))return {ok:fault!=="stops-offline",json:async()=>stops};
  if(u.includes("coast-rta-journeys.json"))return {ok:fault!=="journeys-offline",json:async()=>fixtureJourneys||journeys};
  if(u.includes("/reverse?"))return {ok:true,json:deferred?()=>deferred.promise:async()=>({address:{road:"Lynch Street",city:"Georgetown"}})};
  if(u.includes("photon.komoot.io")){const q=decodeURIComponent(u.split("&q=")[1]||"").toLowerCase();if(q.includes("walmart"))return {ok:true,json:async()=>({features:[{geometry:{coordinates:[target.lon,target.lat]},properties:{name:"Walmart",housenumber:"123",street:"Test Road",city:"Andrews",state:"South Carolina"}},{geometry:{coordinates:[interchange.lon,interchange.lat]},properties:{name:"Walmart",housenumber:"456",street:"Sample Street",city:"Conway",state:"South Carolina"}}]})};return {ok:true,json:async()=>({features:q.includes("andrews")?[feature(target)]:q.includes("georgetown")?[feature(origin)]:[]})}}
  if(u.includes("nominatim.openstreetmap.org"))return {ok:true,json:async()=>[]};
  throw Error("Unexpected mock fetch: "+u);
 };
 const ctx={document,window,navigator,fetch,speechSynthesis,SpeechSynthesisUtterance:class{constructor(text){this.text=text}},Date:FixedDate,Intl,console};
 const api=vm.runInNewContext(script+"\n({state:()=>({screen,pos,destination,official,journeys})})",ctx,{timeout:5000});
 const click=async id=>{assert.equal(typeof get(id).onclick,"function","Missing handler "+id);await get(id).onclick()};
 const settle=async()=>{for(let i=0;i<12;i++)await Promise.resolve()};
 return {get,click,settle,spoken,state:api.state};
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
 const a=boot();await a.settle();
 assert.match(html,/id="dataStatus" role="status" aria-live="polite"/);
 assert.doesNotMatch(html,/#dataStatus\{display:none!important\}/);
 assert.match(a.get("dataStatus").textContent,/525 mapped stops, 143 scheduled trips/);
 assert.match(a.get("dataStatus").textContent,/Snapshot Oct 27, 2026/);
 assert.match(a.get("dataStatus").textContent,/Not live arrivals; walking routes unverified/);
 console.log("PASS: visible GTFS snapshot freshness and non-live warning");
 assert.equal(a.state().official.stops.length,stops.stops.length);
 assert.equal(a.state().journeys.trips.length,journeys.trips.length);
 await selectAndrews(a);
 assert.match(a.get("planFare").textContent,/^1 bus · 0 transfers/);
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
 const transfer=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await transfer.settle();await selectAndrews(transfer);
 assert.match(transfer.get("planFare").textContent,/^2 buses · 1 transfer · Estimated standard cash fare \$2\.00/);
 assert.equal(transfer.get("guideStart").disabled,false);
 await transfer.click("guideStart");
 assert.ok(transfer.spoken.some(s=>s.includes("WALK TO YOUR FIRST STOP")));
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,/TEST ROUTE A/);assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+origin.id));
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+interchange.id));
 await transfer.click("nextInstruction");
 assert.match(transfer.get("stepBody").textContent,new RegExp("official stop ID "+interchange.id));
 console.log("PASS: synthetic two-bus journey, one transfer, fare and mocked speech");
 const short=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:04:00"));await short.settle();await selectAndrews(short);
 assert.equal(short.get("guideStart").disabled,true);
 assert.match(short.get("planStatus").textContent,/could not confirm a scheduled bus connection/);
 console.log("PASS: synthetic transfer under five minutes is rejected");
 const removed=boot("2026-10-27T11:00:00Z",null,syntheticTransfer("09:10:00",[{service_id:"QA-TEST",date:"20261027",exception_type:"2"}]));await removed.settle();await selectAndrews(removed);
 assert.equal(removed.get("guideStart").disabled,true);
 console.log("PASS: removed service-calendar exception blocks itinerary");
 const holiday=boot("2026-11-26T12:00:00Z");await holiday.settle();await selectAndrews(holiday);
 assert.equal(holiday.get("guideStart").disabled,true);
 assert.match(holiday.get("planStatus").textContent,/No Coast RTA fixed-route service is scheduled today/);
 console.log("PASS: Thanksgiving holiday does not generate an itinerary");
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
 await nearby.click("differentStop");
 assert.match(nearby.get("stopOptions").children[0].textContent,/stop ID TL-/);
 await nearby.get("stopOptions").children[0].onclick();
 await nearby.click("chooseStop");assert.equal(nearby.state().screen,"walk");
 assert.match(nearby.get("walkLink").href,/travelmode=walking/);
 console.log("PASS: nearest official mapped stop shows unverified-walk warning and walking map link");
 const distant=boot("2026-10-27T11:00:00Z",null,syntheticTransfer());await distant.settle();await selectAndrews(distant);
 distant.state().destination.lat=target.lat+0.03; // Deliberately synthetic ~3.3 km final walk, not a real address.
 await distant.click("yesDestination");
 assert.match(distant.get("planStatus").textContent,/last stop is [0-9]+ meters straight-line/);
 assert.equal(distant.get("guideStart").disabled,true);
 console.log("PASS: synthetic distant final walk blocks guided trip");
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
 console.log("Source-level mocked regressions passed. NOT a live/Android safety certification.");
}
main().catch(e=>{console.error(e);process.exitCode=1});
