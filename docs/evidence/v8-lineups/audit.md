# V8 initial audit (base 3d1e5c716e58d1daa7e05979fe33a2d7d5864c2a)

Isolation verified by physical cwd and Git top-level; clean detached exact base; branch mx/NBA_WAIVER_V8_LINEUPS established.

Both-team math: fantasy_optimizer._forecast initializes each side from banked actual primitives, adds eleven per-start season-rate primitives only for selected remaining starts, and _assessment sums makes/attempts for FG/FT and reverses TO margins. Adapter banked() retains source attestations; _remaining_lineup_slots reserves already-started active slots. Full plan arithmetic compares complete after/before teams, including drop and displaced-player production.

Defect: automatic focus search uses shared nine-category daily lineups, while explicit focus uses selected-five utility. Neither has a visible daily recommendation. Fix must freeze a disclosed automatic focus seed before the bounded plan search, then use that exact focus for baseline, plan, and exposed daily decisions.

Slot verification: ESPN normalizer reads settings.rosterSettings.lineupSlotCounts excluding IDs 12/13/14/15 (bench/IR), and per-player eligibleSlots. No private account or actual user's league has been accessed; ten is user-confirmed capacity, actual league position configuration remains privately unverified. Do not substitute guessed PG/SG/SF/PF/C slots. Public ESPN guidance requires eligible roster slots and distinguishes bench/IR:
https://support.espn.com/hc/en-us/articles/115003847311-Setting-Your-Lineup
https://support.espn.com/hc/en-us/articles/360054126352-Position-Eligibility

Existing matching uses deterministic marginal category edges including weighted shooting and negative TO effects, with optional benching. It is bounded greedy matching, not a global optimization proof. Preserve that disclosure and distinguish intentional benching from position/capacity constraints.
