import type { Game } from "./model";

export type GameDateGroup = { date: string; games: Game[] };

export function groupGamesByDate(
  games: Game[],
  direction: "ascending" | "descending",
): GameDateGroup[] {
  const groups = new Map<string, Game[]>();
  for (const game of games) {
    const group = groups.get(game.date);
    if (group) group.push(game);
    else groups.set(game.date, [game]);
  }
  const dates = [...groups.keys()].sort();
  if (direction === "descending") dates.reverse();
  return dates.map((date) => ({ date, games: groups.get(date) ?? [] }));
}
