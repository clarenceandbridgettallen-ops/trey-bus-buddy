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
