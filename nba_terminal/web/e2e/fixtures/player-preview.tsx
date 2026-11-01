// Headless-only component harness; APP integrates the production Players route separately.
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { PlayerBrowser } from "../../src/PlayerBrowser";
import "../../src/styles.css";

createRoot(document.getElementById("root")!).render(
  <MemoryRouter>
    <main style={{ maxWidth: 1400, margin: "auto", padding: 16 }}>
      <PlayerBrowser season="2025-26" phase="Playoffs" playerId={7} />
    </main>
  </MemoryRouter>,
);
