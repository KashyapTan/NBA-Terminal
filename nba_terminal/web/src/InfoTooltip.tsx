import { type ReactNode, useId, useState } from "react";

/** Focus and pointer reveal help; tap pins it until dismissed. */
export function InfoTooltip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId();
  const [pinned, setPinned] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  return (
    <span
      className="waiver-help"
      data-pinned={pinned}
      data-dismissed={dismissed}
      onMouseEnter={() => setDismissed(false)}
    >
      <button
        type="button"
        className="waiver-help-trigger"
        aria-label={label}
        aria-describedby={id}
        aria-expanded={pinned}
        onClick={() => {
          setPinned(!pinned);
          setDismissed(pinned);
        }}
        onFocus={() => setDismissed(false)}
        onBlur={() => setPinned(false)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setPinned(false);
            setDismissed(true);
          }
        }}
      >
        <span aria-hidden="true">i</span>
      </button>
      <span id={id} role="tooltip" className="waiver-help-content">
        {children}
      </span>
    </span>
  );
}
