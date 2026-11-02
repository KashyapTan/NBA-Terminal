import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { InfoTooltip } from "./InfoTooltip";

afterEach(cleanup);
it("links keyboard help and supports tap toggle and Escape dismissal", () => {
  render(<InfoTooltip label="Net help">Includes other roster changes.</InfoTooltip>);
  const button = screen.getByRole("button", { name: "Net help" });
  const tooltip = screen.getByRole("tooltip");
  expect(button).toHaveAttribute("aria-describedby", tooltip.id);
  button.focus();
  expect(button).toHaveFocus();
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(button);
  fireEvent.keyDown(button, { key: "Escape" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(button).toHaveFocus();
  expect(button.parentElement).toHaveAttribute("data-dismissed", "true");
  fireEvent.mouseLeave(button.parentElement!);
  expect(button.parentElement).toHaveAttribute("data-dismissed", "true");
  fireEvent.click(button);
  fireEvent.blur(button);
  expect(button).toHaveAttribute("aria-expanded", "false");
});
