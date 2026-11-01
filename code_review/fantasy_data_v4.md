# V4 NBA-first data review

Scope: `fantasy_nba.py`, `espn_fantasy.py`, new `fantasy_actuals.py`, focused synthetic tests.
The project refers to CODE_REVIEW_GUIDE.md, which is absent at the accepted base; reviewed
against AGENTS.md correctness, API resilience, responsiveness, provenance and source boundaries.

Findings addressed:

- NBA was only filling ESPN holes. Current NBA samples now remain primary even for GP 1/2,
  with coherent shooting pairs and explicit provenance; prior fallback remains inspectable.
- Global cache lock held over I/O. Per-key single-flight now isolates resource fetches;
  unrelated-resource concurrency and same-key deduplication have synthetic checks.
- Historical attribution could not safely use the current roster. Daily eligibility join
  now requires echoed ESPN scope and daily scoring roster/ownership/active slot; missing
  facts remain partial, preserving official score and completeness-gated fallback.
- Repeated/corrected production replaces game/player keys; started games cannot receive a
  full future-game estimate through this service's schedule. Live remainder is unmodeled.
- First 100 market rows were implicitly the pool. Pagination has explicit exhaustion,
  repeated-page/failure detection and an 800-row bound, separate from roster completeness.
- Missing cap and used are different facts: absent cap has labeled fallback 7; explicit
  zero is preserved; missing used remains unknown. IR/IR+ remain roster drop identities.
- Unknown game start timing no longer converts a possible game into a known empty schedule.

Remaining limits:

No live private ESPN historical lineup/account validation was performed. The approved NBA
research retained HTTP403 observations, not a successful live NBA feed; this implementation's
provider checks are synthetic/offline. No guarantee of NBA speed, availability, completeness
or successful reconstruction of private fantasy history. Strict schema/eligibility checks can
force ESPN fallback even where a human might infer identity/lineups. Unknown schedule timing
can conservatively invalidate a team's schedule. Market paging can change while being read.
The engine/UI integrator must consume new optional source fields and validate combined output;
this branch deliberately leaves its existing pure optimizer and frontend unchanged.

Two existing integration fixtures were minimally updated: the production mock now handles the
new historical view, and the chain asserts new normalized cap fallback provenance. No shared
planner implementation was changed. Full check results and exact commit live in the task report.
