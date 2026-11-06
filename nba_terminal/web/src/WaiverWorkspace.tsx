import { type ReactNode, useState } from "react";
import { DailyLineup } from "./DailyLineup";
import { InfoTooltip } from "./InfoTooltip";
import { MatchupForecast, type MatchupForecastProps } from "./MatchupForecast";
import {
  type Category,
  type CategoryStrategy,
  formatCategory,
  LEAGUE_CATEGORIES,
  type LeaguePlayer,
  type PickupRecommendation,
  type PlanForecast,
  type RealizedPlanImpact,
} from "./league-fantasy-model";
import { signedChange, WaiverArithmetic } from "./WaiverArithmetic";
import "./waiver-workspace.css";

export interface PickupFilters {
  min_minutes: number;
  min_games: number;
  min_participation: number;
}
export const DEFAULT_PICKUP_FILTERS: PickupFilters = {
  min_minutes: 15,
  min_games: 2,
  min_participation: 0.5,
};
export interface QualifiedSample {
  minutes: number | null;
  games: number | null;
  teamGames: number | null;
}
export type WorkspaceStop =
  | "category_outcome_guard"
  | "unknown_budget"
  | "no_remaining_dates"
  | "budget_exhausted"
  | "no_positive_continuation"
  | "search_limit"
  | "empty_qualified_pool"
  | "required_data_missing";
export interface WaiverWorkspaceProps {
  matchup: string;
  remainingAddsLabel: string;
  refreshedLabel: string;
  updating: boolean;
  readOnly?: boolean;
  resultState?: string;
  onRefresh?: () => void;
  status?: { text: string; actionLabel: string; onAction: () => void; actionHref?: string };
  targets: Category[];
  strategy?: Partial<Record<Category, CategoryStrategy>>;
  onTargetsChange: (categories: Category[]) => void;
  filters: PickupFilters;
  onFiltersChange: (filters: PickupFilters) => void;
  moves: PickupRecommendation[];
  sequenceImpact?: RealizedPlanImpact;
  /** Backend source counts in the same ordered sequence; never inferred from starts. */
  scheduleCounts?: { addRemainingGames: number | null; dropRemainingGames: number | null }[];
  players: Record<string, LeaguePlayer>;
  samples: Record<string, QualifiedSample>;
  stop?: WorkspaceStop;
  forecast?: Omit<MatchupForecastProps, "targets" | "hasMoves" | "readOnly">;
  baseline?: PlanForecast | null;
  projected?: PlanForecast | null;
  rosterControls?: ReactNode;
  analysis: ReactNode;
  technicalControls?: ReactNode;
}
const STOP_LABELS: Record<WorkspaceStop, string> = {
  category_outcome_guard:
    "Keep current roster · no qualifying plan found without worsening projected category results",
  unknown_budget: "Available adds need verification",
  no_remaining_dates: "No remaining matchup dates",
  budget_exhausted: "No adds left in this plan",
  no_positive_continuation: "No further beneficial move found in this search",
  search_limit: "Search limit reached · more moves may help",
  empty_qualified_pool: "No available pickups meet your filters",
  required_data_missing: "Plan needs updated data",
};
const number = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value)
    ? "?"
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

export function WaiverWorkspace(props: WaiverWorkspaceProps) {
  const [draft, setDraft] = useState<Category[] | null>(null);
  const editingTargets = draft ?? props.targets;
  return (
    <section
      className="waiver-workspace"
      aria-label="Waiver workspace"
      data-result-state={props.resultState}
    >
      <header className="ww-heading">
        <div>
          <h2>Waiver plan</h2>
          <p className="ww-context">
            {props.matchup} <span>· {props.remainingAddsLabel}</span>{" "}
            <span>· {props.updating ? "Updating…" : props.refreshedLabel}</span>
          </p>
        </div>
        <InfoTooltip label="About this waiver plan">
          Ordered suggestions for the remaining matchup. Net includes the drop and changes to other
          roster starts. Suggestions never submit roster changes.
        </InfoTooltip>
      </header>
      {props.onRefresh && (
        <button
          className="ww-refresh"
          type="button"
          onClick={props.onRefresh}
          disabled={props.updating}
        >
          Refresh league
        </button>
      )}
      {props.readOnly && props.moves.length > 0 && (
        <span className="ww-saved">Saved plan · read-only</span>
      )}
      {props.status && (
        <div className="ww-status" role="status">
          <span>{props.status.text}</span>
          {props.status.actionHref ? (
            <a href={props.status.actionHref}>{props.status.actionLabel}</a>
          ) : (
            <button type="button" onClick={props.status.onAction}>
              {props.status.actionLabel}
            </button>
          )}
        </div>
      )}
      <section className="ww-targets" aria-label="Target categories">
        <div className="ww-section-label">
          <h3>Your targets</h3>
          <span>Before moves</span>
          <InfoTooltip label="About target categories">
            Choose five categories. Tiles show the projected matchup before moves. The plan also
            accounts for losses across all nine categories.
          </InfoTooltip>
        </div>
        <div className="ww-target-grid">
          {props.targets.map((key) => {
            const category = LEAGUE_CATEGORIES.find((item) => item.key === key)!;
            const row = props.forecast?.complete === false ? undefined : props.strategy?.[key];
            return (
              <div className="ww-target" key={key}>
                <b>{category.label}</b>
                <span>
                  {formatCategory(row?.projected_user ?? null, key)}{" "}
                  <small>vs {formatCategory(row?.projected_opponent ?? null, key)}</small>
                </span>
              </div>
            );
          })}
        </div>
      </section>
      <div className="ww-controls">
        <details className="ww-control">
          <summary>Edit targets</summary>
          <div className="ww-popover ww-category-picker">
            {LEAGUE_CATEGORIES.map(({ key, label }) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={editingTargets.includes(key)}
                  disabled={!editingTargets.includes(key) && editingTargets.length >= 5}
                  onChange={(event) =>
                    setDraft(
                      event.target.checked
                        ? [...editingTargets, key]
                        : editingTargets.filter((item) => item !== key),
                    )
                  }
                />
                {label}
              </label>
            ))}
            <button
              type="button"
              disabled={editingTargets.length !== 5}
              onClick={() => {
                props.onTargetsChange(editingTargets);
                setDraft(null);
              }}
            >
              Apply five
            </button>
          </div>
        </details>
        <details className="ww-control">
          <summary>Pickup filters</summary>
          <div className="ww-popover ww-filter-fields">
            <label>
              Min MPG
              <input
                type="number"
                min="0"
                max="48"
                step="1"
                value={props.filters.min_minutes}
                onChange={(event) =>
                  props.onFiltersChange({
                    ...props.filters,
                    min_minutes: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              Min games
              <input
                type="number"
                min="1"
                max="82"
                step="1"
                value={props.filters.min_games}
                onChange={(event) =>
                  props.onFiltersChange({ ...props.filters, min_games: Number(event.target.value) })
                }
              />
            </label>
            <label>
              Participation %
              <input
                type="number"
                min="0"
                max="100"
                step="5"
                value={Math.round(props.filters.min_participation * 100)}
                onChange={(event) =>
                  props.onFiltersChange({
                    ...props.filters,
                    min_participation: Number(event.target.value) / 100,
                  })
                }
              />
            </label>
            <InfoTooltip label="About pickup qualification">
              Current regular-season sample only. Participation compares player games with completed
              team games. Unknown team games cannot qualify a pickup.
            </InfoTooltip>
          </div>
        </details>
        {props.rosterControls}
      </div>
      <section aria-label="Ordered pickup plan" className="ww-plan">
        <div className="ww-section-label">
          <h3>
            {props.moves.length
              ? `${props.moves.length} ${props.moves.length === 1 ? "move" : "moves"} to consider`
              : props.stop === "category_outcome_guard"
                ? "No qualifying moves"
                : "No moves yet"}
          </h3>
          <span>
            Remaining matchup{" "}
            <InfoTooltip label="About full-team net">
              Net includes pickup minus drop plus displaced or recovered starts elsewhere in your
              lineup. Shooting Add/Drop show makes/attempts; Net shows team percentage points.
            </InfoTooltip>
          </span>
        </div>
        {props.moves.length > 0 && props.sequenceImpact && (
          <SequenceImpact impact={props.sequenceImpact} targets={props.targets} />
        )}
        <ol className="ww-moves">
          {props.moves.map((move, index) => (
            <CompactMove
              key={`${move.date}:${move.add_id}:${move.drop_id}`}
              move={move}
              index={index}
              players={props.players}
              sample={props.samples[move.add_id]}
              targets={props.targets}
              scheduleCounts={props.scheduleCounts?.[index]}
              sequenceImpact={props.sequenceImpact}
            />
          ))}
        </ol>
        {props.stop && <p className="ww-stop">{STOP_LABELS[props.stop]}</p>}
      </section>
      <MatchupForecast
        {...props.forecast}
        targets={props.targets}
        hasMoves={props.moves.length > 0}
        readOnly={props.readOnly}
      />
      <DailyLineup
        baseline={props.baseline}
        projected={props.projected}
        hasMoves={props.moves.length > 0}
        readOnly={props.readOnly}
        complete={props.forecast?.complete}
      />
      <details className="ww-analysis">
        <summary>Full analysis & data</summary>
        {props.moves.map((move, index) => (
          <section key={`${index}:${move.add_id}`}>
            <h3>Move {index + 1} · all nine categories</h3>
            <WaiverArithmetic
              move={move}
              addPlayer={props.players[move.add_id]}
              dropPlayer={props.players[move.drop_id]}
            />
          </section>
        ))}
        {props.analysis}
        {props.technicalControls}
      </details>
    </section>
  );
}
function CompactMove({
  move,
  index,
  players,
  sample,
  targets,
  scheduleCounts,
  sequenceImpact,
}: {
  move: PickupRecommendation;
  index: number;
  players: Record<string, LeaguePlayer>;
  sample?: QualifiedSample;
  targets: Category[];
  scheduleCounts?: NonNullable<WaiverWorkspaceProps["scheduleCounts"]>[number];
  sequenceImpact?: RealizedPlanImpact;
}) {
  // Show selected targets and every harmful spillover; detailed nine-category math stays below.
  const categories = LEAGUE_CATEGORIES.filter(({ key }) => {
    const net = move.arithmetic?.categories[key]?.net ?? move.calculation?.[key]?.net_total;
    return targets.includes(key) || (net != null && (key === "to" ? net > 0 : net < 0));
  });
  return (
    <li className="ww-move">
      <div className="ww-move-top">
        <span className="ww-order">{index + 1}</span>
        <div className="ww-players">
          <div>
            <span className="ww-add-label">ADD</span>
            <strong>{players[move.add_id]?.name ?? move.add_id}</strong>
          </div>
          <div>
            <span className="ww-drop-label">DROP</span>
            <strong>{players[move.drop_id]?.name ?? move.drop_id}</strong>
          </div>
        </div>
        <div className="ww-timing">
          <b>Effective {move.date}</b>
        </div>
      </div>
      {move.realized && (
        <p className="ww-sample">
          Final plan: {move.realized.starts} usable starts ·{" "}
          {move.realized.dates.join(", ") || "none"}
          {move.realized.until
            ? ` · drop on ${move.realized.until}`
            : " · held through matchup end"}
          .
          {move.chain_reason && (
            <>
              {" "}
              {move.direct_comparison
                ? `${move.direct_comparison.extra_acquisitions} extra acquisition vs ${move.direct_comparison.actions.find((a) => a.drop_id === move.drop_id)?.date ?? "direct"} direct (+${(move.direct_comparison.incremental_focus_gain * 100).toFixed(2)} focus pts).`
                : "Streaming route required."}
            </>
          )}
          <InfoTooltip label={`Final contribution for move ${index + 1}`}>
            {move.chain_reason} Heuristic focus points are not win probability. These are the
            pickup’s actual selected starts in the complete dated plan. Previously banked production
            stays fixed. Step-local comparisons are in Full analysis & data.
          </InfoTooltip>
        </p>
      )}
      <div className="ww-schedule">
        <span>
          <b className="ww-add-label">ADD</b> {number(scheduleCounts?.addRemainingGames)} games left
          · {number(move.realized?.starts ?? move.add_starts)} usable starts
        </span>
        <span>
          <b className="ww-drop-label">DROP</b> {number(scheduleCounts?.dropRemainingGames)} games
          left ·{" "}
          {number(
            move.realized
              ? sequenceImpact?.lost_starts.filter(
                  (r) => r.player_id === move.drop_id && r.date >= move.date,
                ).length
              : move.drop_starts,
          )}{" "}
          usable starts
        </span>
        <InfoTooltip label={`Games and usable starts for move ${index + 1}`}>
          Games left counts remaining scheduled games from the provider. ADD usable starts are the
          pickup’s final dated starts in the complete plan, after locks, availability and slot
          limits. DROP usable starts are future baseline starts lost for that player in the complete
          plan. An intermediate player’s earlier production stays banked in the plan; zero future
          lost starts does not erase it. The sequence summary includes all displaced starts too.
          Unknown counts show ?. Legacy saved results without final-plan fields use step-local
          starts.
        </InfoTooltip>
      </div>
      <p className="ww-sample">
        Current sample · {number(sample?.minutes)} MPG · {number(sample?.games)} GP /{" "}
        {number(sample?.teamGames)} team games
      </p>
      {move.realized ? (
        <div className="ww-benefits" aria-label="Final realized pickup contribution">
          {LEAGUE_CATEGORIES.map(({ key, label }) => (
            <div key={key} className="ww-benefit">
              <b>
                {label}
                {key === "to" ? " ↓" : ""}
              </b>
              <span>
                Produced{" "}
                {key === "fg_pct"
                  ? `${number(move.realized?.primitives.fgm)}/${number(move.realized?.primitives.fga)}`
                  : key === "ft_pct"
                    ? `${number(move.realized?.primitives.ftm)}/${number(move.realized?.primitives.fta)}`
                    : number(move.realized?.primitives[key])}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="ww-benefits" aria-label="Remaining matchup add drop and net">
          {categories.map(({ key, label }) => {
            const row = move.arithmetic?.categories[key];
            const calc = move.calculation?.[key];
            const net = row?.net ?? calc?.net_total;
            const gain = net != null && (key === "to" ? net < 0 : net > 0);
            const loss = net != null && (key === "to" ? net > 0 : net < 0);
            const shooting = key.endsWith("pct");
            const shootingPart = (part: "add" | "drop") =>
              row?.makes && row.attempts
                ? `${number(row.makes[part])}/${number(row.attempts[part])}`
                : "?";
            return (
              <div key={key} className="ww-benefit">
                <b>
                  {label}
                  {key === "to" ? " ↓" : ""}
                </b>
                <span>
                  Add {shooting ? shootingPart("add") : number(row?.add ?? calc?.added_total)}
                </span>
                <span>
                  Drop {shooting ? shootingPart("drop") : number(row?.drop ?? calc?.lost_total)}
                </span>
                <strong className={gain ? "ww-gain" : loss ? "ww-loss" : ""}>
                  Net {signedChange(net, key)}
                  <small>{gain ? "Gain" : loss ? "Loss" : net === 0 ? "Even" : "Unknown"}</small>
                </strong>
              </div>
            );
          })}
        </div>
      )}
    </li>
  );
}

function SequenceImpact({ impact, targets }: { impact: RealizedPlanImpact; targets: Category[] }) {
  return (
    <section role="region" className="ww-sequence-impact" aria-label="Final plan get lose and net">
      <div className="ww-section-label">
        <b>Whole plan vs unchanged roster</b>
        <InfoTooltip label="About realized get lose and net">
          Get includes every new or recovered selected player-date. Lose includes dropped and
          displaced starts. Each is counted once across the complete dated plan, with banked actuals
          fixed. Shooting Get/Lose are makes/attempts; Net is the weighted full-team
          percentage-point change. Lower TO helps. ★ marks your selected five. Lost starts:{" "}
          {impact.lost_starts.map((r) => `${r.name} (${r.date})`).join(", ") || "none"}.
        </InfoTooltip>
      </div>
      <p className="ww-sample">
        Get {impact.added_starts.length} starts · Lose {impact.lost_starts.length} starts, including
        displaced starts
      </p>
      <div className="ww-benefits">
        {LEAGUE_CATEGORIES.map(({ key, label }) => {
          const row = impact.arithmetic.categories[key];
          const net = row.net;
          const gain = net != null && (key === "to" ? net < 0 : net > 0);
          const loss = net != null && (key === "to" ? net > 0 : net < 0);
          const part = (side: "add" | "drop") =>
            row.makes && row.attempts
              ? `${number(row.makes[side])}/${number(row.attempts[side])}`
              : number(row[side]);
          return (
            <div className="ww-benefit" key={key} data-category={key}>
              <b>
                {label}
                {key === "to" ? " ↓" : ""}
                {targets.includes(key) ? " ★" : ""}
              </b>
              <span>Get {part("add")}</span>
              <span>Lose {part("drop")}</span>
              <strong className={gain ? "ww-gain" : loss ? "ww-loss" : ""}>
                Net {signedChange(net, key)}{" "}
                <small>{gain ? "Gain" : loss ? "Loss" : net === 0 ? "Even" : "Unknown"}</small>
              </strong>
            </div>
          );
        })}
      </div>
    </section>
  );
}
