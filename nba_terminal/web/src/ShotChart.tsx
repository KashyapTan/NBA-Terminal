import { useEffect, useId, useMemo, useState, type CSSProperties } from "react";
import type { PlayerAnalysis, Shot } from "./model";

type ResultFilter = "all" | "made" | "missed";
type PeriodFilter = "all" | number;
type PerspectiveStyle = CSSProperties & {
  "--court-rotation": string;
  "--court-tilt": string;
};

function useReducedMotionPreference() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!query) return;
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);
  return reduced;
}

function gameClock(shot: Shot) {
  if (shot.minutes_remaining == null) return "";
  const seconds = String(shot.seconds_remaining ?? 0).padStart(2, "0");
  return " · " + shot.minutes_remaining + ":" + seconds;
}

function ShotTooltip({ shot, index }: { shot: Shot; index: number }) {
  const pointType = shot.shot_type?.startsWith("3")
    ? "3PT"
    : shot.shot_type?.startsWith("2")
      ? "2PT"
      : "Field goal";
  return (
    <div className="shot-chart__tooltip" role="status" aria-live="polite">
      <strong>{(shot.made ? "Made" : "Missed") + " · " + pointType}</strong>
      <span>
        {(shot.description || shot.event_type || "Shot attempt") +
          (shot.distance == null ? "" : " · " + shot.distance + " ft")}
      </span>
      <small>
        {(shot.period == null ? "Period unavailable" : "Q" + shot.period + gameClock(shot)) +
          (shot.zone ? " · " + shot.zone : "") +
          " · Attempt " +
          (index + 1)}
      </small>
    </div>
  );
}

function Court({
  shots,
  hovered,
  setHovered,
}: {
  shots: Shot[];
  hovered: number | null;
  setHovered: (index: number | null) => void;
}) {
  const id = useId().replaceAll(":", "");
  return (
    <svg
      className="shot-chart__court"
      viewBox="0 0 500 470"
      role="group"
      aria-label="NBA half court with plotted shot locations. Court dimensions follow the NBA shot chart coordinate grid."
      preserveAspectRatio="xMidYMid meet"
    >
      <title>NBA half court shot chart</title>
      <defs>
        <clipPath id={"court-floor-" + id}>
          <rect x="0" y="0" width="500" height="470" />
        </clipPath>
      </defs>
      <rect className="shot-chart__floor" x="0" y="0" width="500" height="470" />
      <g className="shot-chart__lines">
        <rect x="1" y="1" width="498" height="468" />
        <path d="M 0 280 H 500 M 170 280 V 470 M 330 280 V 470" />
        <path className="shot-chart__arc" d="M 30.5 333 A 237.5 237.5 0 0 1 469.5 333" />
        <path d="M 30.5 333 V 470 M 469.5 333 V 470" />
        <path d="M 190 280 A 60 60 0 0 1 310 280" />
        <path className="shot-chart__dashed" d="M 190 280 A 60 60 0 0 0 310 280" />
        <path d="M 210 422.5 A 40 40 0 0 1 290 422.5" />
        <path d="M 220 430 H 280" />
        <path className="shot-chart__center-mark" d="M 190 0 A 60 60 0 0 0 310 0" />
        <path d="M 166 268 H 178 M 322 268 H 334 M 166 292 H 178 M 322 292 H 334" />
      </g>
      <circle className="shot-chart__hoop" cx="250" cy="422.5" r="7.5" />
      <g clipPath={"url(#court-floor-" + id + ")"} aria-label="Shot attempts">
        {shots.map((shot, index) => {
          // NBA ShotChartDetail uses tenths of a foot, with the rim at (0, 0).
          // Keep source coordinates intact; clipping only hides points outside the drawn floor.
          const x = 250 + shot.x;
          const y = 422.5 - shot.y;
          const type = shot.shot_type?.startsWith("3")
            ? "three-point"
            : shot.shot_type?.startsWith("2")
              ? "two-point"
              : "field-goal";
          const label =
            (shot.made ? "Made " : "Missed ") +
            type +
            " shot" +
            (shot.description ? ", " + shot.description : "") +
            (shot.distance == null ? "" : ", " + shot.distance + " feet") +
            (shot.period == null ? "" : ", period " + shot.period + gameClock(shot));
          return (
            <circle
              key={shot.x + ":" + shot.y + ":" + (shot.period ?? "?") + ":" + index}
              cx={x}
              cy={y}
              r={hovered === index ? 8.5 : 6.5}
              className={
                "shot-chart__mark " +
                (shot.made ? "is-made" : "is-missed") +
                (hovered === index ? " is-active" : "")
              }
              tabIndex={0}
              role="button"
              aria-label={label}
              onPointerEnter={() => setHovered(index)}
              onPointerLeave={(event) => {
                if (document.activeElement !== event.currentTarget) setHovered(null);
              }}
              onFocus={() => setHovered(index)}
              onBlur={() => setHovered(null)}
              onClick={() => setHovered(index)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setHovered(index);
                }
              }}
            >
              <title>{label}</title>
            </circle>
          );
        })}
      </g>
    </svg>
  );
}

export function ShotChart({ analysis }: { analysis: PlayerAnalysis }) {
  const reducedMotion = useReducedMotionPreference();
  const [period, setPeriod] = useState<PeriodFilter>("all");
  const [resultFilter, setResultFilter] = useState<ResultFilter>("all");
  const [rotation, setRotation] = useState(0);
  const [tilt, setTilt] = useState(42);
  const [flat, setFlat] = useState(reducedMotion);
  const [hovered, setHovered] = useState<number | null>(null);
  const chartId = useId().replaceAll(":", "");

  useEffect(() => {
    if (reducedMotion) setFlat(true);
  }, [reducedMotion]);

  const periods = useMemo(
    () =>
      [
        ...new Set(
          analysis.shots
            .map((shot) => shot.period)
            .filter((value): value is number => value != null),
        ),
      ].sort((a, b) => a - b),
    [analysis.shots],
  );
  const shots = useMemo(
    () =>
      analysis.shots
        .map((shot, sourceIndex) => ({ shot, sourceIndex }))
        .filter(({ shot }) => period === "all" || shot.period === period)
        .filter(
          ({ shot }) =>
            resultFilter === "all" || (resultFilter === "made" ? shot.made : !shot.made),
        ),
    [analysis.shots, period, resultFilter],
  );
  const visibleShots = shots.map(({ shot }) => shot);
  const makes = visibleShots.filter((shot) => shot.made).length;
  const currentShot = hovered == null ? null : analysis.shots[hovered];
  const style: PerspectiveStyle = {
    "--court-rotation": rotation + "deg",
    "--court-tilt": flat ? "0deg" : tilt + "deg",
  };
  const chartUnavailable = analysis.shot_chart_state !== "available" || analysis.shots.length === 0;

  function reset() {
    setPeriod("all");
    setResultFilter("all");
    setRotation(0);
    setTilt(42);
    setFlat(reducedMotion);
    setHovered(null);
  }

  return (
    <section className="shot-chart" aria-labelledby={"shot-chart-title-" + chartId}>
      <header className="shot-chart__header">
        <div>
          <div className="shot-chart__eyebrow">SHOT MAP · GAME {analysis.game_id}</div>
          <h3 id={"shot-chart-title-" + chartId}>Where the attempts came from</h3>
          <p>Real NBA Stats locations · 1 chart unit = 0.1 ft · rim centered at 0, 0</p>
        </div>
        <div className="shot-chart__totals" aria-live="polite">
          <strong>
            {visibleShots.length}
            <small> / {analysis.shots.length} shots</small>
          </strong>
          <span>
            {makes} made · {visibleShots.length - makes} missed
          </span>
        </div>
      </header>

      {chartUnavailable ? (
        <div
          className="shot-chart__unavailable"
          role={analysis.shot_chart_state === "error" ? "alert" : "status"}
        >
          <span className="shot-chart__unavailable-mark" aria-hidden="true">
            ⌖
          </span>
          <div>
            <strong>
              {analysis.shot_chart_state === "error"
                ? "Shot chart could not be loaded"
                : "Shot chart unavailable"}
            </strong>
            <p>
              {analysis.shot_chart_state === "error"
                ? "The game line is available, but NBA Stats did not return coordinates. No locations are estimated."
                : "NBA Stats did not provide shot coordinates for this player and game. No locations are estimated."}
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="shot-chart__controls" aria-label="Shot chart controls">
            <label>
              <span>Period</span>
              <select
                aria-label="Shot period"
                value={period}
                onChange={(event) => {
                  const value = event.target.value;
                  setPeriod(value === "all" ? "all" : Number(value));
                  setHovered(null);
                }}
              >
                <option value="all">All periods</option>
                {periods.map((item) => (
                  <option value={item} key={item}>
                    {item <= 4 ? "Quarter " + item : "Overtime " + (item - 4)}
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="shot-chart__filter">
              <legend>Shot result</legend>
              {(["all", "made", "missed"] as const).map((item) => (
                <button
                  type="button"
                  key={item}
                  className={resultFilter === item ? "is-selected" : ""}
                  aria-pressed={resultFilter === item}
                  onClick={() => {
                    setResultFilter(item);
                    setHovered(null);
                  }}
                >
                  {item === "all" ? "All" : item === "made" ? "Makes" : "Misses"}
                </button>
              ))}
            </fieldset>
            <button
              type="button"
              className="shot-chart__view-button"
              aria-pressed={!flat}
              onClick={() => setFlat((value) => !value)}
            >
              Perspective
            </button>
            <button type="button" className="shot-chart__reset" onClick={reset}>
              Reset chart
            </button>
          </div>

          {!flat && (
            <div className="shot-chart__camera-controls">
              <label>
                Rotation
                <input
                  aria-label="Court rotation"
                  type="range"
                  min="-25"
                  max="25"
                  value={rotation}
                  onChange={(event) => setRotation(Number(event.target.value))}
                />
                <output>{rotation}°</output>
              </label>
              <label>
                Tilt
                <input
                  aria-label="Court tilt"
                  type="range"
                  min="32"
                  max="58"
                  value={tilt}
                  onChange={(event) => setTilt(Number(event.target.value))}
                />
                <output>{tilt}°</output>
              </label>
              {reducedMotion && (
                <small>
                  Reduced motion is enabled. Use Perspective to turn on the angled view.
                </small>
              )}
            </div>
          )}

          <div className={"shot-chart__scene" + (flat ? " is-flat" : "")} style={style}>
            <div className="shot-chart__stage">
              <div className="shot-chart__plane">
                <Court
                  shots={visibleShots}
                  hovered={
                    hovered == null
                      ? null
                      : shots.findIndex(({ sourceIndex }) => sourceIndex === hovered)
                  }
                  setHovered={(visibleIndex) => {
                    setHovered(
                      visibleIndex == null ? null : (shots[visibleIndex]?.sourceIndex ?? null),
                    );
                  }}
                />
              </div>
            </div>
            {currentShot && <ShotTooltip shot={currentShot} index={hovered ?? 0} />}
          </div>
          <div className="shot-chart__footer">
            <div className="shot-chart__legend">
              <span>
                <i className="is-made" />
                Made
              </span>
              <span>
                <i className="is-missed" />
                Missed
              </span>
            </div>
            <p>
              Focus a shot marker or point to it for the play detail. Switch to 2D for a flat chart.
            </p>
          </div>
        </>
      )}
    </section>
  );
}
