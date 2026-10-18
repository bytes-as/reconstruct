import { expect, test } from "@playwright/test";

for (const width of [375, 1280]) {
  test(`home renders at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Landfall" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Did the warning land?" })).toBeVisible();
    await expect(page.getByText("Built for Graph Hacks with FalkorDB")).toBeVisible();
    await expect(page.getByText("Graph up")).toBeVisible();
    await page.getByRole("button", { name: "68071-3355-9" }).click();
    await page.getByRole("button", { name: "Check" }).click();
    await expect(page).toHaveURL(/\/ndc\/68071-3355-9\?strict=0/);
    await page.goto("/");
    await page.screenshot({ path: `tests/screenshots/home-${width}.png`, fullPage: true });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflow).toBe(false);
  });
}
