import type { FantasyPlayer } from "./model";

export type StatView = "perGame" | "totals";
export type FantasyCategoryKey =
  | "points"
  | "rebounds"
  | "assists"
  | "steals"
  | "blocks"
  | "threes_made"
  | "field_goal_percentage"
  | "free_throw_percentage"
  | "turnovers"
  | "three_point_percentage"
  | "fantasy_points";

export type FantasyWeights = Record<Exclude<FantasyCategoryKey, "fantasy_points">, number>;

export type FantasyPreferences = {
  ranking: "categories" | "points";
  category: Exclude<FantasyCategoryKey, "fantasy_points">;
  statView: StatView;
  minimumGames: number;
  minimumAttempts: number;
  minimumMinutesPerGame: number;
  minimumTotalMinutes: number;
  weights: FantasyWeights;
  shortlist: number[];
};

export type CategoryDefinition = {
  key: Exclude<FantasyCategoryKey, "fantasy_points">;
  label: string;
  short: string;
  description: string;
  attempts: "field_goal_attempts" | "free_throw_attempts" | "three_attempts" | null;
  lowerIsBetter?: boolean;
};

export const CATEGORIES: CategoryDefinition[] = [
  {
    key: "points",
    label: "Points",
    short: "PTS",
    description: "Points scored in regular-season games.",
    attempts: null,
  },
  {
    key: "rebounds",
    label: "Rebounds",
    short: "REB",
    description: "Total rebounds credited by NBA Stats.",
    attempts: null,
  },
  {
    key: "assists",
    label: "Assists",
    short: "AST",
    description: "Assists credited by NBA Stats.",
    attempts: null,
  },
  {
    key: "steals",
    label: "Steals",
    short: "STL",
    description: "Steals credited by NBA Stats.",
    attempts: null,
  },
  {
    key: "blocks",
    label: "Blocks",
    short: "BLK",
    description: "Blocks credited by NBA Stats.",
    attempts: null,
  },
  {
    key: "threes_made",
    label: "Three-pointers made",
    short: "3PM",
    description: "Made three-point field goals.",
    attempts: "three_attempts",
  },
  {
    key: "field_goal_percentage",
    label: "Field-goal percentage",
    short: "FG%",
    description: "Field goals made divided by field-goal attempts.",
    attempts: "field_goal_attempts",
  },
  {
    key: "free_throw_percentage",
    label: "Free-throw percentage",
    short: "FT%",
    description: "Free throws made divided by free-throw attempts.",
    attempts: "free_throw_attempts",
  },
  {
    key: "turnovers",
    label: "Turnovers",
    short: "TO",
    description: "Turnovers are ranked ascending because fewer is better.",
    attempts: null,
    lowerIsBetter: true,
  },
  {
    key: "three_point_percentage",
    label: "Three-point percentage",
    short: "3P%",
    description: "Three-point field goals made divided by three-point attempts.",
    attempts: "three_attempts",
  },
];

export const CATEGORY_KEYS = CATEGORIES.map((category) => category.key);
export const STANDARD_NINE: Exclude<FantasyCategoryKey, "fantasy_points">[] = [
  "points",
  "rebounds",
  "assists",
  "steals",
  "blocks",
  "threes_made",
  "field_goal_percentage",
  "free_throw_percentage",
  "turnovers",
];

export const DEFAULT_WEIGHTS: FantasyWeights = {
  points: 1,
  rebounds: 1,
  assists: 1.25,
  steals: 2.5,
  blocks: 2.5,
  threes_made: 0.5,
  field_goal_percentage: 0,
  free_throw_percentage: 0,
  turnovers: -1,
  three_point_percentage: 0,
};

export const DEFAULT_PREFERENCES: FantasyPreferences = {
  ranking: "categories",
  category: "points",
  statView: "perGame",
  minimumGames: 0,
  minimumAttempts: 0,
  minimumMinutesPerGame: 0,
  minimumTotalMinutes: 0,
  weights: DEFAULT_WEIGHTS,
  shortlist: [],
};

const PERCENTAGE_KEYS = new Set<FantasyCategoryKey>([
  "field_goal_percentage",
  "free_throw_percentage",
  "three_point_percentage",
]);

export function statValue(
  player: FantasyPlayer,
  category: FantasyCategoryKey,
  view: StatView,
  weights: FantasyWeights = DEFAULT_WEIGHTS,
): number | null {
  if (category === "fantasy_points") return fantasyPoints(player, view, weights);
  if (category === "field_goal_percentage")
    return ratio(player.field_goals_made, player.field_goal_attempts);
  if (category === "free_throw_percentage")
    return ratio(player.free_throws_made, player.free_throw_attempts);
  if (category === "three_point_percentage")
    return ratio(player.threes_made, player.three_attempts);

  const raw = player[category];
  if (raw === null || !Number.isFinite(raw)) return null;
  if (view === "totals") return raw;
  if (player.games === null || !Number.isFinite(player.games) || player.games <= 0) return null;
  return raw / player.games;
}

export function fantasyPoints(
  player: FantasyPlayer,
  view: StatView,
  weights: FantasyWeights,
): number | null {
  let score = 0;
  for (const [key, weight] of Object.entries(weights) as [keyof FantasyWeights, number][]) {
    if (!Number.isFinite(weight) || weight === 0) continue;
    const value = statValue(player, key, view, weights);
    if (value === null) return null;
    score += value * weight;
  }
  return score;
}

export function attemptSample(player: FantasyPlayer, category: FantasyCategoryKey): number | null {
  const definition = CATEGORIES.find((item) => item.key === category);
  return definition?.attempts ? player[definition.attempts] : null;
}

export function isPercentageCategory(category: FantasyCategoryKey): boolean {
  return PERCENTAGE_KEYS.has(category);
}

export function sortedRankings(
  players: FantasyPlayer[],
  category: FantasyCategoryKey,
  view: StatView,
  weights: FantasyWeights,
): FantasyPlayer[] {
  const direction = category === "turnovers" ? 1 : -1;
  return players
    .filter((player) => statValue(player, category, view, weights) !== null)
    .slice()
    .sort((left, right) => {
      const difference =
        (statValue(left, category, view, weights) || 0) -
        (statValue(right, category, view, weights) || 0);
      return difference * direction || left.player_name.localeCompare(right.player_name);
    });
}

export function rankProfile(
  player: FantasyPlayer,
  players: FantasyPlayer[],
  view: StatView,
  weights: FantasyWeights,
): { strongest: string; weakest: string } | null {
  const ranks = STANDARD_NINE.flatMap((key) => {
    const ordered = sortedRankings(players, key, view, weights);
    const index = ordered.findIndex((row) => row.player_id === player.player_id);
    if (index < 0) return [];
    return [{ key, rank: index + 1, count: ordered.length }];
  });
  if (ranks.length === 0) return null;
  const strongest = [...ranks].sort((a, b) => a.rank / a.count - b.rank / b.count)[0];
  const weakest = [...ranks].sort((a, b) => b.rank / b.count - a.rank / a.count)[0];
  return {
    strongest: `${categoryShort(strongest.key)} #${strongest.rank}`,
    weakest: `${categoryShort(weakest.key)} #${weakest.rank}`,
  };
}

export function categoryShort(category: FantasyCategoryKey): string {
  return category === "fantasy_points"
    ? "FP"
    : (CATEGORIES.find((item) => item.key === category)?.short ?? category);
}

export function formatStat(value: number | null, category: FantasyCategoryKey): string {
  if (value === null || !Number.isFinite(value)) return "—";
  if (PERCENTAGE_KEYS.has(category)) return `${(value * 100).toFixed(1)}%`;
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1);
}

function ratio(made: number | null, attempts: number | null): number | null {
  if (
    made === null ||
    attempts === null ||
    !Number.isFinite(made) ||
    !Number.isFinite(attempts) ||
    made < 0 ||
    attempts <= 0 ||
    made > attempts
  )
    return null;
  return made / attempts;
}

export function minutesPerGame(player: FantasyPlayer): number | null {
  if (
    player.minutes_total === null ||
    !Number.isFinite(player.minutes_total) ||
    player.minutes_total < 0 ||
    player.games === null ||
    !Number.isFinite(player.games) ||
    player.games <= 0
  )
    return null;
  return player.minutes_total / player.games;
}

export function meetsPlayingTime(
  player: FantasyPlayer,
  limits: Pick<
    FantasyPreferences,
    "minimumGames" | "minimumMinutesPerGame" | "minimumTotalMinutes"
  >,
): boolean {
  const meets = (value: number | null, minimum: number) =>
    minimum <= 0 || (value !== null && Number.isFinite(value) && value >= minimum);
  return (
    meets(player.games, limits.minimumGames) &&
    meets(minutesPerGame(player), limits.minimumMinutesPerGame) &&
    meets(player.minutes_total, limits.minimumTotalMinutes)
  );
}
