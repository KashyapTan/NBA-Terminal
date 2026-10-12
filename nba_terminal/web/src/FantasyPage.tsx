import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getFantasySeason } from "./api";
import type { FantasyPlayer, Meta } from "./model";
import {
  CATEGORIES,
  CATEGORY_KEYS,
  DEFAULT_PREFERENCES,
  STANDARD_NINE,
  attemptSample,
  categoryShort,
  formatStat,
  isPercentageCategory,
  rankProfile,
  sortedRankings,
  statValue,
  type FantasyCategoryKey,
  type FantasyPreferences,
} from "./fantasy-model";
import "./fantasy.css";

type SortKey = "rank" | "player" | "stat" | "games" | "minutes" | "sample";
type SortState = { key: SortKey; ascending: boolean };
const STORAGE_KEY = "nba-terminal.fantasy.preferences.v1";
const WEIGHT_KEYS = [
  "points",
  "rebounds",
  "assists",
  "steals",
  "blocks",
  "threes_made",
  "field_goal_percentage",
  "free_throw_percentage",
  "turnovers",
  "three_point_percentage",
] as const;

function readPreferences(): FantasyPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_PREFERENCES;
    const value = JSON.parse(stored) as Partial<FantasyPreferences>;
    const weights = { ...DEFAULT_PREFERENCES.weights };
    for (const key of WEIGHT_KEYS) {
      const weight = value.weights?.[key];
      if (typeof weight === "number" && Number.isFinite(weight) && Math.abs(weight) <= 100)
        weights[key] = weight;
    }
    return {
      ranking: value.ranking === "points" ? "points" : "categories",
      category:
        typeof value.category === "string" &&
        CATEGORY_KEYS.some((category) => category === value.category)
          ? (value.category as FantasyPreferences["category"])
          : DEFAULT_PREFERENCES.category,
      statView: value.statView === "totals" ? "totals" : "perGame",
      minimumGames: clampMinimum(value.minimumGames),
      minimumAttempts: clampMinimum(value.minimumAttempts),
      weights,
      shortlist: Array.isArray(value.shortlist)
        ? [...new Set(value.shortlist.filter((id) => Number.isInteger(id) && id > 0))].slice(0, 100)
        : [],
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function clampMinimum(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.min(1000, Math.max(0, Math.floor(value)))
    : 0;
}

function savePreferences(value: FantasyPreferences) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // The page remains usable when browser storage is disabled or full.
  }
}

function numericInput(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function playerSample(player: FantasyPlayer, key: FantasyCategoryKey) {
  const sample = attemptSample(player, key);
  if (sample === null) return "—";
  return `${Math.round(sample).toLocaleString()} ${key === "field_goal_percentage" ? "FGA" : key === "free_throw_percentage" ? "FTA" : "3PA"}`;
}

function playerMinutes(player: FantasyPlayer) {
  if (player.minutes_total === null || !player.games || player.games <= 0) return null;
  return player.minutes_total / player.games;
}

function FantasyPage({ meta }: { meta: Meta }) {
  const [searchParams] = useSearchParams();
  const requestedSeason = searchParams.get("season");
  const season =
    requestedSeason && /^\d{4}-\d{2}$/.test(requestedSeason)
      ? requestedSeason
      : meta.current_season;
  const [preferences, setPreferences] = useState<FantasyPreferences>(readPreferences);
  const [payload, setPayload] = useState<Awaited<ReturnType<typeof getFantasySeason>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState("");
  const [compared, setCompared] = useState<number[]>([]);
  const [notice, setNotice] = useState("");
  const [sort, setSort] = useState<SortState>({ key: "stat", ascending: false });
  const [weightsOpen, setWeightsOpen] = useState(false);

  useEffect(() => savePreferences(preferences), [preferences]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getFantasySeason(season)
      .then((data) => {
        if (active) setPayload(data);
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message || "Season player stats could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [season, attempt]);

  const players = payload?.players ?? [];
  const activeCategory: FantasyCategoryKey =
    preferences.ranking === "points" ? "fantasy_points" : preferences.category;
  const percentage = isPercentageCategory(activeCategory);
  const weightedPercentages = useMemo(
    () =>
      preferences.ranking === "points"
        ? WEIGHT_KEYS.filter((key) => key.endsWith("percentage") && preferences.weights[key] !== 0)
        : [],
    [preferences.ranking, preferences.weights],
  );
  const showAttemptFilter = percentage || weightedPercentages.length > 0;
  const candidateRows = useMemo(
    () =>
      players.filter((player) => {
        if ((player.games ?? 0) < preferences.minimumGames) return false;
        if (percentage) {
          if ((attemptSample(player, activeCategory) ?? 0) < preferences.minimumAttempts)
            return false;
        } else if (
          weightedPercentages.some(
            (key) => (attemptSample(player, key) ?? 0) < preferences.minimumAttempts,
          )
        )
          return false;
        return true;
      }),
    [
      players,
      preferences.minimumGames,
      preferences.minimumAttempts,
      activeCategory,
      percentage,
      weightedPercentages,
    ],
  );
  const orderedRows = useMemo(
    () => sortedRankings(candidateRows, activeCategory, preferences.statView, preferences.weights),
    [candidateRows, activeCategory, preferences.statView, preferences.weights],
  );
  const rankMap = useMemo(
    () => new Map(orderedRows.map((player, index) => [player.player_id, index + 1])),
    [orderedRows],
  );
  const visibleRows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    const filtered = orderedRows.filter((player) => {
      if (!query) return true;
      return `${player.player_name} ${player.team_abbreviation ?? ""} ${player.team_name ?? ""}`
        .toLocaleLowerCase()
        .includes(query);
    });
    const sign = sort.ascending ? 1 : -1;
    return [...filtered].sort((left, right) => {
      let result = 0;
      if (sort.key === "player") result = left.player_name.localeCompare(right.player_name);
      if (sort.key === "rank")
        result = (rankMap.get(left.player_id) ?? 0) - (rankMap.get(right.player_id) ?? 0);
      if (sort.key === "stat")
        result =
          (statValue(left, activeCategory, preferences.statView, preferences.weights) ?? 0) -
          (statValue(right, activeCategory, preferences.statView, preferences.weights) ?? 0);
      if (sort.key === "games") result = (left.games ?? 0) - (right.games ?? 0);
      if (sort.key === "minutes") result = (playerMinutes(left) ?? 0) - (playerMinutes(right) ?? 0);
      if (sort.key === "sample")
        result =
          (attemptSample(left, activeCategory) ?? 0) - (attemptSample(right, activeCategory) ?? 0);
      return result * sign || left.player_name.localeCompare(right.player_name);
    });
  }, [
    orderedRows,
    search,
    sort,
    rankMap,
    activeCategory,
    preferences.statView,
    preferences.weights,
  ]);

  const comparePlayers = compared
    .map((id) => players.find((player) => player.player_id === id))
    .filter((player): player is FantasyPlayer => player !== undefined);
  const shortlistPlayers = preferences.shortlist
    .map((id) => players.find((player) => player.player_id === id))
    .filter((player): player is FantasyPlayer => player !== undefined);
  const currentSeasonEmpty =
    !loading &&
    !error &&
    payload?.supported !== false &&
    players.length === 0 &&
    season === meta.current_season;

  function update<K extends keyof FantasyPreferences>(key: K, value: FantasyPreferences[K]) {
    setPreferences((current) => ({ ...current, [key]: value }));
  }

  function chooseCategory(category: FantasyPreferences["category"]) {
    setPreferences((current) => ({ ...current, category, ranking: "categories" }));
    setSort({ key: "stat", ascending: category === "turnovers" });
  }

  function choosePoints() {
    setPreferences((current) => ({ ...current, ranking: "points" }));
    setSort({ key: "stat", ascending: false });
  }

  function toggleSort(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, ascending: !current.ascending }
        : { key, ascending: key === "player" },
    );
  }

  function toggleCompare(playerId: number, name: string) {
    if (compared.includes(playerId)) {
      setCompared((items) => items.filter((id) => id !== playerId));
      setNotice(`${name} removed from comparison.`);
    } else if (compared.length >= 3) {
      setNotice("Compare up to three players at a time.");
    } else {
      setCompared((items) => [...items, playerId]);
      setNotice(`${name} added to comparison.`);
    }
  }

  function toggleShortlist(playerId: number, name: string) {
    const exists = preferences.shortlist.includes(playerId);
    update(
      "shortlist",
      exists
        ? preferences.shortlist.filter((id) => id !== playerId)
        : [...preferences.shortlist, playerId].slice(-100),
    );
    setNotice(exists ? `${name} removed from your shortlist.` : `${name} saved to your shortlist.`);
  }

  const activeDefinition = CATEGORIES.find((category) => category.key === preferences.category);
  if (loading)
    return (
      <section className="fantasy-page">
        <div className="fantasy-loading" role="status">
          <span className="spinner" />
          <div>
            <b>Fantasy season stats</b>
            <p>Loading the {season} regular-season player table</p>
          </div>
        </div>
      </section>
    );
  if (error)
    return (
      <section className="fantasy-page">
        <FantasyHeader season={season} meta={meta} />
        <div className="fantasy-error" role="alert">
          <b>Fantasy stats unavailable</b>
          <p>{error} NBA Stats is the source; no values have been filled in.</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
        </div>
      </section>
    );
  if (payload?.supported === false)
    return (
      <section className="fantasy-page">
        <FantasyHeader season={season} meta={meta} />
        <div className="fantasy-state">
          <span aria-hidden="true">i</span>
          <div>
            <b>That season is outside the supported range</b>
            <p>Select an available season from the menu to view NBA Stats regular-season data.</p>
          </div>
        </div>
      </section>
    );

  return (
    <section className="fantasy-page">
      <FantasyHeader season={season} meta={meta} />
      <div className="fantasy-statusline">
        <span className="fantasy-source-dot" />
        <span>NBA Stats · regular season actuals</span>
        <span className="fantasy-status-divider">/</span>
        <span>Per-game values and percentages derived from season totals</span>
        <span className="fantasy-status-spacer" />
        <span className="fantasy-status-tag">NO PROJECTIONS</span>
      </div>

      {currentSeasonEmpty ? (
        <div className="fantasy-state season-not-started">
          <span aria-hidden="true">◷</span>
          <div>
            <b>{season} season stats are not available yet</b>
            <p>
              NBA Stats has not returned regular-season player rows for this season. No rankings or
              projections are shown.
            </p>
          </div>
        </div>
      ) : players.length === 0 ? (
        <div className="fantasy-state">
          <span aria-hidden="true">◌</span>
          <div>
            <b>No regular-season player stats returned</b>
            <p>This season has no rows in the NBA Stats response. Try another available season.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="fantasy-overview" aria-label="Season overview">
            <div>
              <span>PLAYERS IN SEASON DATA</span>
              <strong>{players.length.toLocaleString()}</strong>
              <small>NBA Stats returned rows</small>
            </div>
            <div>
              <span>SHORTLIST</span>
              <strong>{preferences.shortlist.length}</strong>
              <small>Saved on this device</small>
            </div>
            <div>
              <span>COMPARISON</span>
              <strong>
                {compared.length}
                <i> / 3</i>
              </strong>
              <small>Selected for a side-by-side view</small>
            </div>
          </div>

          <section className="fantasy-board">
            <div className="fantasy-board-header">
              <div>
                <span className="fantasy-kicker">PLAYER RANKINGS</span>
                <h2>Build your board</h2>
                <p>Choose a category to see season leaders. Turnovers rank from fewest to most.</p>
              </div>
              <div className="fantasy-view-switch" role="group" aria-label="Stat view">
                <button
                  type="button"
                  className={preferences.statView === "perGame" ? "selected" : ""}
                  onClick={() => update("statView", "perGame")}
                >
                  Per game
                </button>
                <button
                  type="button"
                  className={preferences.statView === "totals" ? "selected" : ""}
                  onClick={() => update("statView", "totals")}
                >
                  Season totals
                </button>
              </div>
            </div>

            <div className="fantasy-category-wrap">
              <div className="fantasy-category-label">STANDARD 9-CATEGORY FORMAT</div>
              <div className="fantasy-categories" role="tablist" aria-label="Fantasy category">
                {CATEGORIES.filter((category) => category.key !== "three_point_percentage").map(
                  (category) => (
                    <button
                      type="button"
                      role="tab"
                      key={category.key}
                      aria-selected={
                        preferences.ranking === "categories" &&
                        preferences.category === category.key
                      }
                      className={
                        preferences.ranking === "categories" &&
                        preferences.category === category.key
                          ? "selected"
                          : ""
                      }
                      title={category.description}
                      onClick={() => chooseCategory(category.key)}
                    >
                      {category.short}
                    </button>
                  ),
                )}
                <span className="fantasy-category-separator" />
                <button
                  type="button"
                  role="tab"
                  aria-selected={
                    preferences.ranking === "categories" &&
                    preferences.category === "three_point_percentage"
                  }
                  className={
                    preferences.ranking === "categories" &&
                    preferences.category === "three_point_percentage"
                      ? "selected extra"
                      : "extra"
                  }
                  title="Three-pointers made divided by attempts; extra category beyond the standard nine."
                  onClick={() => chooseCategory("three_point_percentage")}
                >
                  3P%
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={preferences.ranking === "points"}
                  className={
                    preferences.ranking === "points" ? "selected points-tab" : "points-tab"
                  }
                  onClick={choosePoints}
                >
                  Points scoring
                </button>
              </div>
            </div>

            <div className="fantasy-active-explainer">
              <div>
                <span className="fantasy-active-label">
                  {preferences.ranking === "points" ? "EDITABLE SCORING" : "RANKED BY"}
                </span>
                <strong>
                  {preferences.ranking === "points"
                    ? "Custom fantasy points"
                    : activeDefinition?.label}
                </strong>
                <p>
                  {preferences.ranking === "points"
                    ? "Each stat total or per-game rate is multiplied by its weight, then summed. Negative weights subtract from the score."
                    : activeDefinition?.description}
                </p>
              </div>
              <div className="fantasy-leading-stat">
                <span>LEADER</span>
                <strong>{orderedRows[0]?.player_name ?? "—"}</strong>
                <small>
                  {orderedRows[0]
                    ? `${formatStat(statValue(orderedRows[0], activeCategory, preferences.statView, preferences.weights), activeCategory)} · ${[
                        orderedRows[0].games === null
                          ? null
                          : `${Math.round(orderedRows[0].games)} GP`,
                        attemptSample(orderedRows[0], activeCategory) === null
                          ? null
                          : `${Math.round(attemptSample(orderedRows[0], activeCategory) ?? 0)} ${activeCategory === "field_goal_percentage" ? "FGA" : activeCategory === "free_throw_percentage" ? "FTA" : "3PA"}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}`
                    : "No players meet the selected filters"}
                </small>
              </div>
            </div>

            {preferences.ranking === "points" && (
              <section className="fantasy-scoring-settings">
                <button
                  type="button"
                  className="fantasy-disclosure"
                  aria-expanded={weightsOpen}
                  onClick={() => setWeightsOpen((open) => !open)}
                >
                  <span>
                    <b>Scoring weights</b>
                    <small>Example starter weights · edit for your league</small>
                  </span>
                  <span>{weightsOpen ? "−" : "+"}</span>
                </button>
                {weightsOpen && (
                  <div className="fantasy-weight-panel">
                    <p>
                      There is no single NBA fantasy points formula. These editable starter values
                      apply to{" "}
                      {preferences.statView === "totals" ? "season totals" : "per-game stats"};
                      percentage values use the made ÷ attempted rate.
                    </p>
                    <div className="fantasy-weight-grid">
                      {WEIGHT_KEYS.map((key) => (
                        <label key={key}>
                          <span>{categoryShort(key)}</span>
                          <input
                            type="number"
                            step={key.includes("percentage") ? "0.01" : "0.25"}
                            min="-100"
                            max="100"
                            aria-label={`${categoryShort(key)} scoring weight`}
                            value={preferences.weights[key]}
                            onChange={(event) =>
                              setPreferences((current) => ({
                                ...current,
                                weights: {
                                  ...current.weights,
                                  [key]: Math.max(
                                    -100,
                                    Math.min(100, numericInput(event.target.value)),
                                  ),
                                },
                              }))
                            }
                          />
                        </label>
                      ))}
                    </div>
                    <div className="fantasy-formula">
                      <b>Arithmetic</b>
                      <span>
                        Σ(stat value × weight) ·{" "}
                        {preferences.statView === "totals" ? "season totals" : "per-game values"};
                        TO uses its configured signed weight.
                      </span>
                    </div>
                  </div>
                )}
              </section>
            )}

            <div className="fantasy-controls">
              <label className="fantasy-search">
                <span aria-hidden="true">⌕</span>
                <input
                  type="search"
                  aria-label="Search players or teams"
                  placeholder="Search player or team"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
              <label>
                <span>MIN GAMES</span>
                <input
                  aria-label="Minimum games played"
                  type="number"
                  min="0"
                  max="1000"
                  value={preferences.minimumGames}
                  onChange={(event) =>
                    update("minimumGames", clampMinimum(numericInput(event.target.value)))
                  }
                />
              </label>
              {showAttemptFilter && (
                <label>
                  <span>MIN ATTEMPTS</span>
                  <input
                    aria-label={
                      percentage
                        ? `Minimum ${activeCategory === "field_goal_percentage" ? "field-goal" : activeCategory === "free_throw_percentage" ? "free-throw" : "three-point"} attempts`
                        : "Minimum attempts for weighted percentage scoring"
                    }
                    type="number"
                    min="0"
                    max="1000"
                    value={preferences.minimumAttempts}
                    onChange={(event) =>
                      update("minimumAttempts", clampMinimum(numericInput(event.target.value)))
                    }
                  />
                </label>
              )}
              <span className="fantasy-filter-count">
                {visibleRows.length.toLocaleString()} players
              </span>
            </div>

            <div className="fantasy-table-wrap">
              <table className="fantasy-table">
                <thead>
                  <tr>
                    <th>
                      <SortButton label="RANK" sortKey="rank" sort={sort} onClick={toggleSort} />
                    </th>
                    <th>
                      <SortButton
                        label="PLAYER"
                        sortKey="player"
                        sort={sort}
                        onClick={toggleSort}
                      />
                    </th>
                    <th>
                      <SortButton
                        label={
                          preferences.ranking === "points"
                            ? "FANTASY PTS"
                            : (activeDefinition?.short ?? "STAT")
                        }
                        sortKey="stat"
                        sort={sort}
                        onClick={toggleSort}
                      />
                    </th>
                    <th>
                      <SortButton label="GP" sortKey="games" sort={sort} onClick={toggleSort} />
                    </th>
                    <th>
                      <SortButton label="MPG" sortKey="minutes" sort={sort} onClick={toggleSort} />
                    </th>
                    <th>
                      <SortButton
                        label="ATTEMPTS"
                        sortKey="sample"
                        sort={sort}
                        onClick={toggleSort}
                      />
                    </th>
                    <th>COMPARE / SHORTLIST</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((player) => {
                    const selectedForCompare = compared.includes(player.player_id);
                    const inShortlist = preferences.shortlist.includes(player.player_id);
                    return (
                      <tr key={player.player_id}>
                        <td className="fantasy-rank">#{rankMap.get(player.player_id)}</td>
                        <td>
                          <b className="fantasy-player-name">{player.player_name}</b>
                          <small>
                            {player.team_abbreviation ?? player.team_name ?? "Team not listed"}
                          </small>
                        </td>
                        <td className="fantasy-value">
                          {formatStat(
                            statValue(
                              player,
                              activeCategory,
                              preferences.statView,
                              preferences.weights,
                            ),
                            activeCategory,
                          )}
                        </td>
                        <td>{player.games === null ? "—" : Math.round(player.games)}</td>
                        <td>
                          {playerMinutes(player) === null ? "—" : playerMinutes(player)?.toFixed(1)}
                        </td>
                        <td className="fantasy-sample">{playerSample(player, activeCategory)}</td>
                        <td className="fantasy-row-actions">
                          <button
                            type="button"
                            className={selectedForCompare ? "selected" : ""}
                            aria-pressed={selectedForCompare}
                            aria-label={`${selectedForCompare ? "Remove" : "Add"} ${player.player_name} ${selectedForCompare ? "from" : "to"} comparison`}
                            onClick={() => toggleCompare(player.player_id, player.player_name)}
                          >
                            {selectedForCompare ? "Comparing" : "Compare"}
                          </button>
                          <button
                            type="button"
                            className={inShortlist ? "saved" : ""}
                            aria-pressed={inShortlist}
                            aria-label={`${inShortlist ? "Remove" : "Add"} ${player.player_name} ${inShortlist ? "from" : "to"} shortlist`}
                            onClick={() => toggleShortlist(player.player_id, player.player_name)}
                          >
                            {inShortlist ? "Saved" : "Shortlist"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {visibleRows.length === 0 && (
                <div className="fantasy-table-empty">
                  <b>No players match these filters.</b>
                  <span>Lower the minimum games or attempts, or clear the search.</span>
                </div>
              )}
            </div>
            {showAttemptFilter && (
              <p className="fantasy-table-footnote">
                {percentage
                  ? "Percentage rank uses made ÷ attempts. The attempts column is the sample behind the selected rate; there is no minimum sample by default."
                  : "The minimum applies to each percentage category with a non-zero scoring weight."}
              </p>
            )}
          </section>

          <section className="fantasy-lists">
            <section className="fantasy-list-panel">
              <div className="fantasy-list-heading">
                <div>
                  <span className="fantasy-kicker">DRAFT / ROSTER TOOLS</span>
                  <h2>Your shortlist</h2>
                </div>
                <span>{preferences.shortlist.length} saved</span>
              </div>
              <p className="fantasy-list-intro">
                Pin players while you browse. The shortlist is stored in this browser on this
                device.
              </p>
              {shortlistPlayers.length === 0 ? (
                <div className="fantasy-empty-list">
                  Use <b>Shortlist</b> in the player table to save draft or roster candidates.
                </div>
              ) : (
                <div className="fantasy-shortlist">
                  {shortlistPlayers.map((player) => {
                    const profile = rankProfile(
                      player,
                      players,
                      preferences.statView,
                      preferences.weights,
                    );
                    return (
                      <div className="fantasy-shortlist-row" key={player.player_id}>
                        <div>
                          <b>{player.player_name}</b>
                          <small>
                            {player.team_abbreviation ?? player.team_name ?? "Team not listed"}
                          </small>
                        </div>
                        <div className="fantasy-strength-context">
                          {profile ? (
                            <>
                              <span>
                                Relative strength <b>{profile.strongest}</b>
                              </span>
                              <span>
                                Relative gap <b>{profile.weakest}</b>
                              </span>
                            </>
                          ) : (
                            <span>Category profile unavailable</span>
                          )}
                        </div>
                        <button
                          type="button"
                          aria-label={`Remove ${player.player_name} from shortlist`}
                          onClick={() => toggleShortlist(player.player_id, player.player_name)}
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              <small className="fantasy-context-note">
                Strength and gap compare current season category ranks across returned player rows.
                They describe observed stats, not future production.
              </small>
            </section>

            <section className="fantasy-list-panel comparison-panel">
              <div className="fantasy-list-heading">
                <div>
                  <span className="fantasy-kicker">SIDE-BY-SIDE</span>
                  <h2>Compare players</h2>
                </div>
                {comparePlayers.length > 0 && (
                  <button type="button" onClick={() => setCompared([])}>
                    Clear
                  </button>
                )}
              </div>
              {comparePlayers.length < 2 ? (
                <div className="fantasy-empty-list">
                  Select two or three players with <b>Compare</b> to review their category
                  production, sample size and relative ranks.
                </div>
              ) : (
                <div className="fantasy-compare-wrap">
                  <table className="fantasy-compare-table">
                    <thead>
                      <tr>
                        <th>PLAYER</th>
                        {STANDARD_NINE.map((key) => (
                          <th key={key}>{categoryShort(key)}</th>
                        ))}
                        <th>3P%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparePlayers.map((player) => {
                        const profile = rankProfile(
                          player,
                          players,
                          preferences.statView,
                          preferences.weights,
                        );
                        return (
                          <tr key={player.player_id}>
                            <td>
                              <b>{player.player_name}</b>
                              <small>
                                {profile
                                  ? `Strength ${profile.strongest} · gap ${profile.weakest}`
                                  : player.team_abbreviation}
                              </small>
                            </td>
                            {[...STANDARD_NINE, "three_point_percentage" as const].map((key) => {
                              const ranks = sortedRankings(
                                players,
                                key,
                                preferences.statView,
                                preferences.weights,
                              );
                              const rank =
                                ranks.findIndex((item) => item.player_id === player.player_id) + 1;
                              const sample = attemptSample(player, key);
                              return (
                                <td key={key}>
                                  <b>
                                    {formatStat(
                                      statValue(
                                        player,
                                        key,
                                        preferences.statView,
                                        preferences.weights,
                                      ),
                                      key,
                                    )}
                                  </b>
                                  <small>
                                    {rank ? `#${rank}` : "—"}
                                    {sample === null ? "" : ` · ${Math.round(sample)} att`}
                                  </small>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <small className="fantasy-context-note">
                Season actuals and in-season rank context only. Comparison is descriptive and does
                not project future results.
              </small>
            </section>
          </section>
          <div className="fantasy-live-notice" aria-live="polite">
            {notice}
          </div>
        </>
      )}
    </section>
  );
}

function FantasyHeader({ season, meta }: { season: string; meta: Meta }) {
  const [, setSearchParams] = useSearchParams();
  const seasonOptions = [
    ...meta.seasons,
    ...[season].filter((value) => value && !meta.seasons.includes(value)),
  ];
  return (
    <header className="fantasy-heading">
      <div>
        <div className="fantasy-kicker">NBA · FANTASY WORKSPACE</div>
        <h1>
          Find your next <em>edge.</em>
        </h1>
        <p>Compare real season production, build category balance and keep a shortlist.</p>
      </div>
      <label className="fantasy-season-select">
        <span>SEASON</span>
        <select
          aria-label="Fantasy season"
          value={season}
          onChange={(event) =>
            setSearchParams(event.target.value ? { season: event.target.value } : {})
          }
        >
          {seasonOptions.map((option) => (
            <option key={option} value={option}>
              {option}
              {option === meta.current_season ? " · current" : ""}
            </option>
          ))}
        </select>
      </label>
    </header>
  );
}

function SortButton({
  label,
  sortKey,
  sort,
  onClick,
}: {
  label: string;
  sortKey: SortKey;
  sort: SortState;
  onClick: (key: SortKey) => void;
}) {
  return (
    <button type="button" className="fantasy-sort-button" onClick={() => onClick(sortKey)}>
      {label}
      {sort.key === sortKey ? (
        <span aria-label={sort.ascending ? "ascending" : "descending"}>
          {sort.ascending ? " ↑" : " ↓"}
        </span>
      ) : null}
    </button>
  );
}

export default FantasyPage;
