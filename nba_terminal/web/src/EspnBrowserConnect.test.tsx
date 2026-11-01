import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { EspnBrowserConnect } from "./EspnBrowserConnect";
import { browserBridgeApi } from "./league-fantasy-api";
vi.mock("./league-fantasy-api", () => ({
  browserBridgeApi: { status: vi.fn(), pair: vi.fn(), cancel: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
it("pairs without secrets and refetches the app after automatic extension connection", async () => {
  vi.mocked(browserBridgeApi.status).mockResolvedValue({ enabled: false });
  vi.mocked(browserBridgeApi.pair).mockResolvedValue({ enabled: true, state: "no_espn_session" });
  const connected = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<EspnBrowserConnect onConnected={connected} />);
  await user.type(screen.getByLabelText("League ID"), "123");
  await user.type(screen.getByLabelText("Season ending year"), "2027");
  await user.click(screen.getByRole("button", { name: "Connect ESPN" }));
  expect(browserBridgeApi.pair).toHaveBeenCalledWith({ league_id: 123, season_id: 2027 });
  expect(screen.getByRole("status")).toHaveTextContent("verification");
  expect(screen.getByRole("link", { name: "Sign in at ESPN ↗" })).toHaveAttribute(
    "href",
    "https://www.espn.com/login/",
  );
  vi.mocked(browserBridgeApi.status).mockResolvedValue({ enabled: true, state: "connected" });
  window.dispatchEvent(new CustomEvent("nba-espn-bridge", { detail: { state: "connected" } }));
  await waitFor(() => expect(connected).toHaveBeenCalledOnce());
});
it("cancels pairing and exposes concrete setup artifacts and permission guidance", async () => {
  vi.mocked(browserBridgeApi.status).mockResolvedValue({
    enabled: true,
    state: "permission_denied",
  });
  vi.mocked(browserBridgeApi.cancel).mockResolvedValue({ connected: false });
  render(<EspnBrowserConnect />);
  await screen.findByText(/ESPN permission is required/);
  await userEvent.click(screen.getByRole("button", { name: "Cancel connection" }));
  expect(browserBridgeApi.cancel).toHaveBeenCalledOnce();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("One-time browser setup"));
  expect(screen.getByRole("link", { name: "Firefox extension" })).toHaveAttribute(
    "href",
    "/api/fantasy/espn/bridge/setup/firefox.zip",
  );
  expect(
    screen.getByText(/temporary loading lasts until the browser restarts/),
  ).toBeInTheDocument();
});
