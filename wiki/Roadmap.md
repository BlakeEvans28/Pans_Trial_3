# Roadmap

This roadmap summarizes the most reasonable next steps based on the current project state and the checked-in reports.

The written report recommends productization rather than redesign. The core rules work; the next work should make the game easier to learn, easier to host, easier to share, and easier to package for a small public audience.

## Near-Term Gameplay and UX

- Add a stronger first-run tutorial so new players can learn the draft, Traversing, and Appeasing Pan without outside explanation.
- Add a simple solo tutorial opponent or guided scenario for onboarding.
- Keep improving leave, reconnect, and status messaging in two-player sessions.
- Continue polishing request popups, board readability, and mobile-sized layouts.

## Deployment and Publishing

- Host a public one-link browser demo backed by the Python room server.
- Move hosted multiplayer onto stable HTTPS by default.
- Package a clean public demo build for class review, friends, and wider testing.
- Prepare trailer, screenshots, and store-facing material for a later public release.
- Use the web demo as the lead platform before testing itch.io, Steam, and mobile/tablet release paths.

## Balance and Design Iteration

- Continue running AI-vs-AI balance studies after major rule changes.
- Review seat fairness, request usage, and endgame pacing after each balance pass.
- Tune AI behavior so single-player mode becomes a stronger strategic test.

## Product Expansion

- Explore a web-first launch followed by desktop storefront release.
- Consider cosmetic board themes or visual packs that do not affect competitive fairness.
- Evaluate a mobile or tablet release once the browser and desktop flows are stable.
- Keep monetization cosmetic, access-based, or convenience-based so paid content does not damage competitive trust.

## Engineering Extensions

- Strengthen reconnect and state recovery further for hosted multiplayer.
- Keep the engine and UI cleanly separated as new features land.
- Expand automated coverage when new requests, UI flows, or hosting modes are added.

## Long-Term Opportunities

- Additional AI profiles or self-play experiments
- Classroom or educational use as a rules-engineering example
- Small tournament or community playtesting events built around the browser version

## Priority Order

If time is limited, the most valuable sequence is:

1. first-run tutorial polish
2. public hosted browser demo
3. stronger AI and balance iteration
4. platform expansion and release packaging

## Report Links

- [Publication Case](Publication-Case)
- [Testing and Balance](Testing-and-Balance)
- [Media and References](Media-and-References)
