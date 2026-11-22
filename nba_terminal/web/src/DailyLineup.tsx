import { useState } from "react";
import { InfoTooltip } from "./InfoTooltip";
import {
  type DailyLineupDay,
  type DailyLineupPlayer,
  LEAGUE_CATEGORIES,
  type PlanForecast,
} from "./league-fantasy-model";

const REASONS: Record<string, string> = {
  capacity_or_position: "Bench · capacity or position fit",
  intentional_focus_bench: "Bench · avoids harm to focus categories",
  already_started_or_banked: "Locked · already started / banked",
  unavailable: "Out · unavailable",
  inactive_or_ir: "Inactive / IR",
  no_remaining_game: "No remaining game today",
  lineup_capacity_or_policy: "Bench · position or focus policy",
  before_transaction_effective_date: "Not available until transaction date",
};
function contribution(player: DailyLineupPlayer, day: DailyLineupDay) {
  return day.focus
    .map((key) => {
      const value = player.rates[key];
      if (key === "fg_pct" || key === "ft_pct") {
        const made = player.rates[key === "fg_pct" ? "fgm" : "ftm"];
        const attempts = player.rates[key === "fg_pct" ? "fga" : "fta"];
        return attempts
          ? `${made?.toFixed(1)}/${attempts.toFixed(1)} ${key === "fg_pct" ? "FG" : "FT"}`
          : null;
      }
      return value
        ? `${value.toFixed(1)} ${LEAGUE_CATEGORIES.find((c) => c.key === key)?.label}`
        : null;
    })
    .filter(Boolean)
    .join(" · ");
}
export function DailyLineup({
  generation,
  baseline,
  projected,
  hasMoves,
  readOnly,
  complete,
}: {
  generation?: string;
  baseline?: PlanForecast | null;
  projected?: PlanForecast | null;
  hasMoves: boolean;
  readOnly?: boolean;
  complete?: boolean;
}) {
  const [preview, setPreview] = useState(false);
  const [pickedDate, setPickedDate] = useState("");
  const days = ((preview && hasMoves ? projected : baseline)?.daily_lineups ?? []).filter(
    (day) => day.owner === "user",
  );
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  const day =
    days.find((d) => d.date === pickedDate) ?? days.find((d) => d.date === today) ?? days[0];
  const starters = day?.players.filter((p) => p.state !== "bench") ?? [];
  const bench = day?.players.filter((p) => p.state === "bench") ?? [];
  const playing = day?.players.filter((p) => p.playing).length ?? 0;
  return (
    <section className="ww-daily" aria-label="Daily lineup" data-plan-generation={generation}>
      <div className="ww-daily-heading">
        <h2>Daily lineup</h2>
        <InfoTooltip label="About daily lineup">
          Uses the same focus-aware decisions as the forecast, including weighted shooting and
          turnover harm. ESPN position slots and started games restrict selection. Greedy matching
          can miss a better combination. Fewer starters may reflect intentional benching to avoid
          focus-category harm. Set your lineup manually in ESPN.
        </InfoTooltip>
        {readOnly && <small>Saved · read only</small>}
      </div>
      <p className="ww-muted">
        {preview && hasMoves
          ? "After plan preview · hypothetical, applies moves on their dates"
          : "Current roster · no pickups required"}
        {complete === false && " · Partial data: recommendations need verification"}
      </p>
      {hasMoves && (
        <label className="ww-daily-preview">
          <input
            type="checkbox"
            checked={preview}
            onChange={(event) => setPreview(event.target.checked)}
          />
          Preview after planned moves
        </label>
      )}
      {!day ? (
        <p>Daily lineup unavailable until roster, schedule and position rules are verified.</p>
      ) : (
        <>
          <div className="ww-daily-controls">
            <label>
              Day{" "}
              <select
                aria-label="Lineup day"
                value={day.date}
                onChange={(event) => setPickedDate(event.target.value)}
              >
                {days.map((d) => (
                  <option key={d.date} value={d.date}>
                    {new Date(`${d.date}T12:00:00`).toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                    {d.players.filter((p) => p.playing).length > d.capacity
                      ? " · Over capacity"
                      : ""}
                  </option>
                ))}
              </select>
            </label>
            <strong>
              {starters.length}/{day.capacity} active
            </strong>
            <span className={playing > day.capacity ? "ww-daily-crowded" : "ww-muted"}>
              {playing} available & playing{playing > day.capacity ? " · Choose your starters" : ""}
            </span>
          </div>
          <small className="ww-muted">
            Focus:{" "}
            {day.focus
              .map((key) => LEAGUE_CATEGORIES.find((c) => c.key === key)?.label)
              .join(" · ")}
          </small>
          <div className="ww-daily-columns">
            {(
              [
                ["Start", starters],
                ["Bench", bench],
              ] as const
            ).map(([label, players]) => (
              <div key={label}>
                <h3>
                  {label} <small>{players.length}</small>
                </h3>
                {players.length === 0 ? (
                  <p className="ww-muted">
                    {label === "Start" ? "No eligible starts today" : "No bench players"}
                  </p>
                ) : (
                  <ul aria-label={`${label} players`}>
                    {players.map((p) => (
                      <li
                        key={p.player_id}
                        className={
                          p.state === "locked"
                            ? "ww-daily-locked"
                            : label === "Start"
                              ? "ww-daily-start"
                              : "ww-daily-bench"
                        }
                      >
                        <div>
                          <b>{p.name}</b>
                          <span>{p.assigned_slot ?? "Bench"}</span>
                        </div>
                        <small>
                          {p.team ? `${p.team} · ` : ""}
                          {p.positions
                            .filter((pos) => !["BENCH", "IR", "IR+"].includes(pos))
                            .join(" / ")}
                        </small>
                        <small>
                          {p.state === "start"
                            ? contribution(p, day) || "Selected for current focus"
                            : (REASONS[p.reason] ?? p.reason.replaceAll("_", " "))}
                        </small>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
          <p className="ww-muted ww-daily-note">
            {starters.length < day.capacity
              ? "Open slots can reflect schedules, positions, availability or intentional focus benching. "
              : ""}
            Started players stay locked; their stats are already banked. No lineup changes are sent
            to ESPN.
          </p>
        </>
      )}
    </section>
  );
}
