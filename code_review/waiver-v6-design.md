# Waiver V6 design and integration contract

Independent stage on exact base 4e9f94f51fa2ab402e2a913023bfc28a49358553. Only new presentation files are edited; ENGINE and CONNECTION remain source prerequisites. CODE_REVIEW_GUIDE.md is absent at this base.

## Applied primary references (read 2026-11-02)

- https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines — compact comparison alignment, grouped utility controls, progressive disclosure. Primary cards use repeated category cells; detailed arithmetic stays in the bottom section.
- https://www.carbondesignsystem.com/building-blocks/core/components/tooltip/guidelines — contextual nonessential help on hover/focus. InfoTooltip also supports tap to pin and Escape/blur to dismiss; actionable status remains visible outside help.
- https://atlassian.design/components/lozenge/usage — compact, consistent meaningful labels. ADD/DROP and Gain/Loss text accompany green/red accents; yellow marks actionable status and selected targets. Existing dark neutrals are retained.

## Presentation boundary

WaiverWorkspaceProps receives ordered PickupRecommendation moves, existing category strategy/player data, explicit qualified current-season samples (MPG, player GP, completed team GP), status and callbacks. It does not fetch, schedule, optimize, infer a denominator or mutate shared lifecycle. Filters serialize min_minutes, min_games, min_participation (fraction); defaults 15/2/0.5. Parent owns validation/persistence and API preferences.

Integration must map authoritative ENGINE stop metadata to WorkspaceStop; no fallback claim of global optimality or no useful free agents. Parent supplies honest remaining-adds label (unknown/unlimited distinct). Required-data/auth invalidation belongs to CONNECTION while transient updates retain prior props. Analysis slot receives all source coverage, exclusions, search diagnostics, complete plan arithmetic and reason text. TechnicalControls receives advanced overrides. RosterControls must be a compact disclosure for availability/core protection.

Cards show selected targets and every harmful category outside targets. Net comes from paired full-team arithmetic (fallback exact calculation net); never pickup contribution. Shooting Add/Drop are makes/attempts, Net is team percentage-point change. Spillover is included in true net and fully itemized below. All nine per-move calculations remain inside default-closed Full analysis & data.

## Pending combined validation

Component tests are preparation only. Parent-validated exact ENGINE and CONNECTION commits, backend fixture HTTP flows via proxy and production client, full required checks, and rendered desktop/mobile validation are prerequisites to complete delivery. No private account or live-provider verification is claimed here.

## Independent-stage evidence

- Bun: 132 tests pass; line coverage 93.88%; lint, format check, typecheck and build pass. New component tests cover true net vs pickup/drop, all harmful category spillover, qualified sample, filter serialization, stop states, retained props while updating, five-target cap, unknown sample and help dismissal.
- UV: Ruff passes; 447 tests pass; coverage report passes (97% combined measured backend coverage). No backend files changed at this stage.
- Inspected preparation captures: waiver-v6-desktop-preparation.png (1280×900), waiver-v6-mobile-preparation.png and waiver-v6-mobile-help-preparation.png (390px). Two moves fit concise cards, mobile comparisons use aligned rows, bottom details closed, no horizontal overflow. Keyboard focus/Escape and touch tap toggle pass in Chromium. Harness fixtures are explicitly synthetic; no API or live-data proof is implied.
- Own port4213 preview stopped after inspection. No primary server, user browser, credentials or transactions touched. Initial touch probe lacked hasTouch; corrected test context and repeat passed.
