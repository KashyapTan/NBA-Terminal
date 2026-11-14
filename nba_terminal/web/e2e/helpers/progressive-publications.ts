import { expect, type Page, type Route, type APIResponse } from "@playwright/test";

/** Gate request/response timing, never the planner contents. Every response is
 * produced by the real authenticated HTTP/provider/adapter/optimizer pipeline. */
export async function gateProgress(page: Page) {
  let open = false;
  const pending: { route: Route; release: (holdResponse: boolean) => void }[] = [];
  let delivery: (() => void) | undefined;
  await page.route("**/api/fantasy/espn/plan/*", async (route) => {
    if (route.request().method() !== "POST" || open) {
      await route.continue();
      return;
    }
    const holdResponse = await new Promise<boolean>((release) => pending.push({ route, release }));
    if (!holdResponse) {
      await route.continue().catch(() => {});
      return;
    }
    const response = await route.fetch();
    captured = response;
    await new Promise<void>((resolve) => {
      delivery = resolve;
    });
    await route.fulfill({ response }).catch(() => {});
  });
  let captured: APIResponse | undefined;
  return {
    async next(job: string, holdResponse = false) {
      await expect
        .poll(() => pending.some((p) => p.route.request().url().endsWith(`/plan/${job}`)))
        .toBe(true);
      const index = pending.findIndex((p) => p.route.request().url().endsWith(`/plan/${job}`));
      const response = holdResponse
        ? null
        : page.waitForResponse(
            (r) => r.url().endsWith(`/plan/${job}`) && r.request().method() === "POST",
          );
      pending.splice(index, 1)[0].release(holdResponse);
      if (holdResponse) {
        await expect.poll(() => !!captured).toBe(true);
        return captured!;
      }
      return (await response!)!;
    },
    deliver() {
      delivery?.();
    },
    release() {
      open = true;
      pending.splice(0).forEach((p) => p.release(false));
      delivery?.();
    },
  };
}
