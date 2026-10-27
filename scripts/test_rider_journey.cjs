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
class El{
 constructor(id="",tag="DIV"){this.id=id;this.tagName=tag;this.textContent="";this.value="";this.disabled=false;this.children=[];this.style={};this.classList={toggle(){}}}
 append(...x){this.children.push(...x)}
 replaceChildren(...x){this.children=[...x]}
 setAttribute(){}
 focus(){}
}
function boot(instant="2026-10-27T11:00:00Z",deferred=null){
 const ids=[...html.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(x=>x[1]);
 const els=new Map(ids.map(x=>[x,new El(x)]));
 const get=id=>{if(!els.has(id))els.set(id,new El(id));return els.get(id)};
 const document={getElementById:get,querySelectorAll:()=>ids.map(get),querySelector:()=>new El("heading","H2"),createElement:t=>new El("",t.toUpperCase()),createTextNode:t=>({textContent:t})};
 const spoken=[],speechSynthesis={cancel(){},speak:u=>spoken.push(u.text)};
 const window={scrollTo(){},speechSynthesis};
 const navigator={geolocation:{getCurrentPosition:ok=>ok({coords:{latitude:origin.lat,longitude:origin.lon,accuracy:14}})},clipboard:{writeText:async()=>{}}};
 class FixedDate extends Date{constructor(...a){super(...(a.length?a:[instant]))}static now(){return new Date(instant).getTime()}}
 const feature=s=>({geometry:{coordinates:[s.lon,s.lat]},properties:{name:s.name,city:"Georgetown",state:"South Carolina"}});
 const fetch=async url=>{
  const u=String(url);
  if(u.includes("coast-rta-stops.json"))return {ok:true,json:async()=>stops};
  if(u.includes("coast-rta-journeys.json"))return {ok:true,json:async()=>journeys};
  if(u.includes("/reverse?"))return {ok:true,json:deferred?()=>deferred.promise:async()=>({address:{road:"Lynch Street",city:"Georgetown"}})};
  if(u.includes("photon.komoot.io")){const q=decodeURIComponent(u.split("&q=")[1]||"").toLowerCase();return {ok:true,json:async()=>({features:q.includes("andrews")?[feature(target)]:q.includes("georgetown")?[feature(origin)]:[]})}}
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
 assert.equal(a.state().official.stops.length,stops.stops.length);
 assert.equal(a.state().journeys.trips.length,journeys.trips.length);
 await selectAndrews(a);
 assert.match(a.get("planFare").textContent,/^1 bus · 0 transfers/);
 await a.click("openFare");assert.equal(String(a.get("boardings").value),"1");
 assert.equal(a.get("fareTotal").textContent,"$1.00 estimated");
 await a.click("fareDone");await a.click("guideStart");
 assert.equal(a.state().screen,"guide");
 assert.ok(a.spoken.some(s=>s.includes("WALK TO YOUR FIRST STOP")));
 await a.click("nextInstruction");await a.click("home");
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
 console.log("Source-level mocked regressions passed. NOT a live/Android safety certification.");
}
main().catch(e=>{console.error(e);process.exitCode=1});
