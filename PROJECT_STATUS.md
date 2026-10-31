# Bus Buddy | Project status and anti-drift record
Updated: 2026-10-26
## Product vision
An entirely free, accessible Coast RTA navigation app designed first for Trey (legally blind, cerebral palsy) and then all riders. Journey: confirm actual origin → find destination by name or address inside app → confirm address → review complete accurate bus/walk itinerary and fare → spoken step-by-step guidance, transfers, alerts, help, and arrival.
## Source of truth
Repository: clarenceandbridgettallen-ops/trey-bus-buddy
Deployment: https://clarenceandbridgettallen-ops.github.io/trey-bus-buddy/
Last source version inspected: Preview v36. This is **not** an end-to-end verified release.
## Inspected evidence
- index.html: destination search, results screen, existing direct/one-transfer scheduled journey calculation.
- data/coast-rta-stops.json: 525 mapped stop records (count does not prove completeness against current agency feed).
- data/coast-rta-journeys.json: 143 trip records (count does not prove complete service coverage).
- Rider screenshots: Belle Isle Bistro and Conway Liquors can be found in some versions; HGTC Grand Strand Building 600 returned no confirmed connection despite a nearby mapped stop. Screenshot proves an error state, not whether a usable Coast RTA journey exists.
## Preserve
Existing GPS/manual location entry, confirmation, in-app place results, GTFS assets, full-trip screen, large accessible controls, spoken guidance components, Home/Back/help, and deployment. Verify every feature before labeling it fully functional. Feedback collection must be rechecked.
## Confirmed/known issues
1. Journey engine considers direct and one-transfer trips only; no complete multi-transfer search.
2. Origin and destination candidates rely on straight-line proximity; walking paths, crossings, accessibility, and stop side are unverified.
3. Failure message does not reliably distinguish no remaining departures from no possible service or incomplete data.
4. Scheduled trip coverage and service calendar interpretation need independent audit against authoritative Coast RTA GTFS.
5. Business-name coverage relies on incomplete free geocoding directories and a limited local fallback.
6. Live arrivals and spoken arrival alerts are not end-to-end verified.
## Current milestone
Diagnose repeated 'could not confirm a scheduled bus connection' using actual GTFS data and reproducible route cases. Do not increase unsafe walking limits to fake success.
## Next three priorities
1. Add deterministic routing regression tests, inspecting stop/time/calendar logic and differentiating no service from missed departures.
2. Implement timetable-based multi-transfer search with valid transfer times, future-day search, and safe walking checks.
3. Verify complete Coast RTA feed coverage, then test on Android and deployed GitHub Pages.
## Permanent regression cases
Farrow Parkway-area Walmart → Surfside Walmart; Belle Isle Bistro Georgetown; Conway Liquors; HGTC Grand Strand Building 600; direct trip; transfer trip; no departure remaining; distant final walk; ambiguous/unlisted business; offline/data failure; GPS denied.
## Never reverse without explicit evidence
- Free hosting, development and user operation. No paid APIs, subscriptions or expiring credits.
- In-app business search and confirmation, never silently choose an unrelated place.
- No ChatGPT account required by riders.
- Accessibility-first large controls, high contrast, speech and straightforward navigation.
- Never present straight-line distance as verified pedestrian directions.
- Never invent bus routes, stop times, crossings, live arrivals, fares or completed tests.
- Preserve working code and use fresh file SHAs to avoid overwriting concurrent changes.
## Run protocol
Inspect latest source and commits → diagnose one highest-priority root cause → implement smallest safe change → test code, data, real user flow and regression cases → commit → verify deployment → record evidence, failures and next action here. Label implemented/tested/deployed/verified separately.
## Completion gate
Only finished when actual origin → in-app destination → complete verified itinerary → safe boarding and transfers → spoken navigation → arrival works reliably across published Coast RTA service, including uncertain-data handling.

## Development run 2026-10-26: Transit integrity baseline
- Added `scripts/audit_journeys.py` in commit `737ac96bd422957b8a6f4e1233a78254d4821ae2`. This is an offline integrity audit; not a journey-planner fix.
- Independently checked repository JSON in the connected session: 525/525 stop IDs appear in 143 trips; zero missing stop references and zero missing calendar references.
- No Android end-to-end journey, scheduled-connection correctness, or published deployment was verified in this run.
- Next: build deterministic temporal routing tests that can identify whether service-day filtering, departures, or transfer graph traversal prevents a journey; then implement multiple transfers without inventing pedestrian paths.

## Development run 2026-10-26: Directed master network foundation
- Inspected Preview v36, stop and journey JSON, and current status. Confirmed planner only supports direct and one-transfer journeys, with straight-line proximity checks.
- Added `scripts/build_network.py` (commit d44df5ac43a3c186f380398c431c8664a78adc4e): creates directed links between consecutive ordered stops, retaining trip, route, service, direction, and time uncertainty. Running it in the repository generates `data/coast-rta-network.json`; generated output has NOT been committed or independently validated against the complete agency feed.
- Added `scripts/test_network.py` (commit 0d85810e8fcfea6a48e2492d08007c587e72d4b6). Four equivalent synthetic tests passed locally before commit: direction, blank times, missing stop, duplicate stop, invalid coordinates. GitHub Actions execution is NOT verified.
- No rider-facing code changed. Preview v36 routing failures remain. No real-world route or safe walking path verified.
- Next: run network builder against repository's actual feed; validate directed connectivity, then implement timetable-based multi-transfer route search with deterministic fixtures and preserve pedestrian-safety restrictions.

## Visual design phase 2026-10-30
- User approved a visual-only Coast RTA-inspired refresh. Changed `index.html` to Preview v37 in commit `8435412b126f4a8f1bad6b53e972eddc464ae8f3`.
- Added blue, pale sky, gold sunshine, coastal accents, refined cards/buttons, small transitions, reduced-motion preference, visible keyboard focus. Existing HTML screens and JS routing logic were preserved.
- Verified source contains v37 and stylesheet changes after commit. Browser/device visual QA and live GitHub Pages deployment are NOT yet confirmed. Next: user acceptance test on Android, check contrast/scrolling and preserve accessible behavior.

## Visual animation phase 2026-10-30
- Committed Preview v40 `79a96810db8d3ea2f09751ab8b78a5106321b0cf`: decorative inline SVG blue/gold bus drives across screen after rider confirms starting address or destination; no external animation dependency.
- Preserves route logic and original navigation. Transition is skipped for prefers-reduced-motion. Guard checks current screen/navigation version before continuing; visual overlay is aria-hidden.
- Source commit confirmed; Android interaction and live Pages deployment still need verification. Next: test address-confirmation flow, navigation interruptions, reduced-motion and screen reader focus.

## Feedback and animations phase 2026-10-30
- Preview v41 commit `4ec460f436510d937099fd84a16c9f4e061ea46d`: replaced broken copy-only feedback with embedded published Tally form `YjjDDq` and browser fallback. Form already existed, was published, and had 0 submissions at inspection. Actual user submission through embedded iframe not yet verified.
- Every normal screen navigation now gets a small decorative bus animation and entrance transition, without delaying navigation. Existing full bus drive-off remains after address confirmation. Reduced-motion preference suppresses animations.
- Feedback is collected in Tally, not sent directly to ChatGPT or email; daily automated review is NOT enabled until launch per user direction. Do not claim reports are monitored automatically. Avoid collecting precise GPS automatically.
- Existing routing and trip safety gate unchanged. Android QA and Pages deployment still need verification.

## Multi-transfer routing v42 (2026-10-30)
- Commit `692bd475b60b69942a55ceb117b39023ef2624f1` expands one-destination search to four bus legs (three transfers), including up to 200m straight-line between alighting and next boarding stops. Search examines downstream stops of each stored trip and permits final stops up to 12km straight-line away. Transfer walking remains unverified; spoken guided travel is disabled for transfers between distinct stops.
- IMPORTANT: Existing frequency-based timetable coverage is incomplete and blocks START MY TRIP; planner is only a possible route preview. Four-leg search has bounded frontier and is not exhaustive; real-world Georgetown test and browser runtime validation are pending. Do not claim it confirms service.

## Conway network audit (2026-10-30)
- Compared existing stop inventory and journeys: 525 mapped stops, 143 stored trips, 525 distinct trip-referenced stop IDs, **zero missing referenced stop IDs**. This checks internal integrity, not completeness of actual service.
- Existing Conway-serving stop associations: Route 1 Conway Local 26, Route 2 Conway/Loris 17, Route 3 Conway/Bucksport 13, Route 7 Myrtle Beach/Conway 59; variants Route 7A 29, Route 7H inbound 27 / via Oak Tree Farms 36, Route 7X 6 per direction. These are route-to-stop association counts, not unique Conway stops and not verified service frequencies.
- Additional Conway links in existing inventory: Route 4X Georgetown/Andrews variants, 11X Startek, 17X coastal connections. Conway Terminal stop TL-20, Conway Medical Center TL-53 (IB) and TL-953 (OB).
- Coast RTA published a revised maps/timetables brochure for service effective June 7, 2026: https://coastrta.com/wp-content/uploads/2026/05/Maps-timetables-05112026.EH-1.pdf . Route 1 official detailed stop list also appears at https://www.transit.land/explore/operators/o-coast~rta~sc~us/routes/r-dnpb8-rt1conwaylocal . Live Coast RTA route tracker: https://coastrta.transloc.com/routes/12/stops . Current GTFS download listed at https://coastrta.transloc.com/Secure/Admin/Reports/GTFSDownload.aspx .
- **Unresolved:** No fresh GTFS import or stop-by-stop comparison has been completed; Conway stop completeness and actual departure schedules cannot yet be certified. Source includes missing/interpolated times and frequency-based service. Do not claim all Conway stops are updated or enable automatic guided departures on this audit alone.
- Next engineering work: download and validate current Coast RTA GTFS (stops/routes/trips/stop_times/calendar/frequencies), diff against stored stop IDs and route memberships, rebuild graph and route search, test Conway Terminal ↔ Myrtle Beach and Conway Local/Loris/Bucksport, then confirm PruittHealth Conway destination with a real rider route.
