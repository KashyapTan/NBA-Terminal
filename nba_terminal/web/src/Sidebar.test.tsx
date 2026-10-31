import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, MetaProvider } from "./App";

vi.mock("./FantasyPage", () => ({ default: () => <h1>Fantasy workspace</h1> }));
vi.mock("./api", () => ({
  getMeta: vi.fn(async () => ({
    current_season: "2025-26",
    seasons: ["2025-26"],
    supported_from: "1996-97",
  })),
  getUpcoming: vi.fn(async () => ({ games: [] })),
  getGames: vi.fn(async () => ({ games: [], supported: true })),
}));

const preferenceKey = "nba-terminal.sidebar-collapsed";
function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MetaProvider>
        <AppRoutes />
      </MetaProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("workspace sidebar", () => {
  it("supports keyboard collapse, retains named routes, and expands again", async () => {
    const user = userEvent.setup();
    renderApp();
    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAttribute("aria-controls", "workspace-navigation");
    toggle.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
    expect(localStorage.getItem(preferenceKey)).toBe("true");
    const nav = screen.getByRole("navigation", { name: "Workspace" });
    expect(within(nav).getByRole("link", { name: "Game Center" })).toHaveAttribute(
      "title",
      "Game Center",
    );
    await user.click(within(nav).getByRole("link", { name: "Fantasy" }));
    expect(await screen.findByRole("heading", { name: "Fantasy workspace" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Fantasy" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await user.click(within(nav).getByRole("link", { name: "Game Center" }));
    expect(within(nav).getByRole("link", { name: "Game Center" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(localStorage.getItem(preferenceKey)).toBe("false");
    expect(document.querySelector(".app-shell")).not.toHaveClass("sidebar-collapsed");
  });

  it("restores a saved preference on a direct Fantasy visit", () => {
    localStorage.setItem(preferenceKey, "true");
    renderApp("/fantasy");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("link", { name: "Fantasy" })).toHaveAttribute("title", "Fantasy");
  });

  it("ignores an unrecognized stored value", () => {
    localStorage.setItem(preferenceKey, "invalid");
    renderApp();
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("keeps toggling and navigation usable when storage access fails", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage full");
    });
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    await user.click(screen.getByRole("link", { name: "Fantasy" }));
    expect(await screen.findByRole("heading", { name: "Fantasy workspace" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});
