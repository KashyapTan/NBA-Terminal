// Deterministic test-only league. Never imported by production UI.
import type { LeaguePlayer, LeagueSnapshot } from "./league-fantasy-model";
export function testPlayer(id: string, overrides: Partial<LeaguePlayer> = {}): LeaguePlayer {
  return {
    id,
    name: `Test player ${id}`,
    positions: ["PG", "UTIL"],
    lineup_slot: "PG",
    injury_status: null,
    injured: null,
    locked: false,
    availability: "FREEAGENT",
    eligible: true,
    current_rates: { pts: 10, minutes: 20 },
    current_games: 5,
    prior_rates: null,
    prior_games: null,
    schedule: [],
    today: false,
    remaining_games: 2,
    ...overrides,
  };
}
export function testSnapshot(): LeagueSnapshot {
  const totals = {
    pts: 100,
    reb: 20,
    ast: 20,
    stl: 3,
    blk: 3,
    threes: 10,
    to: 8,
    fgm: 10,
    fga: 20,
    ftm: 4,
    fta: 5,
  };
  return {
    schema_version: 1,
    fetched_at: "2026-10-31T12:00:00Z",
    source: "espn_unofficial",
    league: {
      id: 1,
      season_id: 2027,
      name: "Test-only league",
      team_count: 14,
      supported: true,
      unsupported_reason: null,
      lineup_slots: ["PG", "UTIL"],
      acquisition_settings: {
        weekly_add_limit: 7,
        limit_per_scoring_period: false,
        season_add_limit: null,
      },
    },
    period: {
      matchup_period_id: 1,
      scoring_period_id: 4,
      dates: ["2026-10-31", "2026-11-01"],
      remaining_dates: ["2026-11-01"],
    },
    selected_team_id: 1,
    opponent_team_id: 2,
    teams: Array.from({ length: 14 }, (_, index) => ({
      id: index + 1,
      name: index === 0 ? "Test user" : index === 1 ? "Test opponent" : `Test team ${index + 1}`,
      ownership_verified: false,
      roster:
        index === 0
          ? [
              testPlayer("rostered", {
                availability: "ONTEAM",
                today: true,
                schedule: [
                  {
                    date: "2026-10-31",
                    start_at: "2026-10-31T23:00:00Z",
                    started: false,
                    scoring_period_id: 4,
                    opponent_pro_team_id: 2,
                  },
                ],
              }),
            ]
          : [],
      totals: index === 1 ? { ...totals, pts: 90, to: 10 } : totals,
      weekly_used_adds: null,
      remaining_adds: null,
    })),
    free_agents: [
      testPlayer("free"),
      testPlayer("rostered"),
      testPlayer("waivers", { availability: "WAIVERS" }),
      testPlayer("ineligible", { eligible: false }),
    ],
    free_agents_truncated: true,
    data_gaps: ["Weekly transaction counts unavailable"],
  };
}
