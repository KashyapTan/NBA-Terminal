import { type ReactNode } from "react";
import { InfoTooltip } from "./InfoTooltip";
import {
  type Category,
  type CategoryStrategy,
  formatCategory,
  LEAGUE_CATEGORIES,
  type LeaguePlayer,
  type PickupRecommendation,
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
  status?: { text: string; actionLabel: string; onAction: () => void };
  targets: Category[];
  strategy?: Partial<Record<Category, CategoryStrategy>>;
  onTargetsChange: (categories: Category[]) => void;
  filters: PickupFilters;
  onFiltersChange: (filters: PickupFilters) => void;
  moves: PickupRecommendation[];
  players: Record<string, LeaguePlayer>;
  samples: Record<string, QualifiedSample>;
  stop?: WorkspaceStop;
  rosterControls?: ReactNode;
  analysis: ReactNode;
  technicalControls?: ReactNode;
}
const STOP_LABELS: Record<WorkspaceStop, string> = {
  budget_exhausted: "No adds left in this plan",
  no_positive_continuation: "No further beneficial move found in this search",
  search_limit: "Search limit reached · more moves may help",
  empty_qualified_pool: "No available pickups meet your filters",
  required_data_missing: "Plan needs updated data",
};
const number = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value)
    ? "?"
    : value.toLocaleString(undefined, { maximumFractionDigits: 1 });

export function WaiverWorkspace(props: WaiverWorkspaceProps) {
  return (
    <section className="waiver-workspace" aria-label="Waiver workspace">
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
      {props.status && (
        <div className="ww-status" role="status">
          <span>{props.status.text}</span>
          <button type="button" onClick={props.status.onAction}>
            {props.status.actionLabel}
          </button>
        </div>
      )}
      <section className="ww-targets" aria-label="Target categories">
        <div className="ww-section-label">
          <h3>Your targets</h3>
          <InfoTooltip label="About target categories">
            Choose five categories. The plan also accounts for losses across all nine categories.
          </InfoTooltip>
        </div>
        <div className="ww-target-grid">
          {props.targets.map((key) => {
            const category = LEAGUE_CATEGORIES.find((item) => item.key === key)!;
            const row = props.strategy?.[key];
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
                  checked={props.targets.includes(key)}
                  disabled={!props.targets.includes(key) && props.targets.length >= 5}
                  onChange={(event) =>
                    props.onTargetsChange(
                      event.target.checked
                        ? [...props.targets, key]
                        : props.targets.filter((item) => item !== key),
                    )
                  }
                />
                {label}
              </label>
            ))}
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
              : "No moves yet"}
          </h3>
          <span>Remaining matchup</span>
        </div>
        <ol className="ww-moves">
          {props.moves.map((move, index) => (
            <CompactMove
              key={`${move.date}:${move.add_id}:${move.drop_id}`}
              move={move}
              index={index}
              players={props.players}
              sample={props.samples[move.add_id]}
              targets={props.targets}
            />
          ))}
        </ol>
        {props.stop && <p className="ww-stop">{STOP_LABELS[props.stop]}</p>}
      </section>
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
}: {
  move: PickupRecommendation;
  index: number;
  players: Record<string, LeaguePlayer>;
  sample?: QualifiedSample;
  targets: Category[];
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
          <b>{move.date}</b>
          <span>{number(move.add_starts)} usable starts</span>
        </div>
      </div>
      <p className="ww-sample">
        Current sample · {number(sample?.minutes)} MPG · {number(sample?.games)} GP /{" "}
        {number(sample?.teamGames)} team games
      </p>
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
    </li>
  );
}
