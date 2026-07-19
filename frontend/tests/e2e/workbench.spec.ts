import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/?demo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Turn seed examples into training-ready data" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("completes the primary generation setup flow", async ({ page }) => {
  await page.getByRole("button", { name: "Start generating" }).click();
  await expect(page.getByRole("heading", { name: "Generate a dataset" })).toBeVisible();
  await page.getByRole("button", { name: "Check setup" }).click();
  await expect(page.getByText("Candidate cap", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start generation" }).click();
  await expect(page.getByText("Generation queued", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Follow the run" }).click();
  await expect(page.getByRole("heading", { name: "Generation runs" })).toBeVisible();
});

test("opens every workbench view, provenance details, and both themes", async ({ page }) => {
  for (const view of ["Generate", "Review", "Exports"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(page.locator("h1")).not.toBeEmpty();
  }

  await page.getByRole("button", { name: "More", exact: true }).click();
  for (const view of ["Projects", "Runs"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(page.locator("h1")).not.toBeEmpty();
  }

  await page.getByText("Recipe and provenance", { exact: true }).click();
  await expect(page.getByText("Run reference", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.locator("h1")).not.toBeEmpty();
  await expect(page.getByText("Provider secrets are never sent to the browser.")).toBeVisible();

  await page.getByRole("radio", { name: "Light Light surfaces" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("radio", { name: "Dark Dark surfaces" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("keeps supporting navigation out of the core path and exposes concise help", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Generate", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Projects", exact: true })).toBeHidden();

  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByText("Quality and candidate limits", { exact: true }).click();
  await page.locator('summary[aria-label="About minimum quality"]').click();
  await expect(
    page.getByText("Examples scoring below this value are not automatically accepted."),
  ).toBeVisible();
});

test("records a review decision and creates a downloadable export", async ({ page }) => {
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review candidates" })).toBeVisible();
  await page.getByPlaceholder("Explain the decision for future reviewers").fill(
    "Grounding is consistent with the source seed.",
  );
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByText("Candidate accepted", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Exports", exact: true }).click();
  await page.getByRole("button", { name: "New export", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create export" })).toBeVisible();
  await page.getByRole("button", { name: "Create immutable export", exact: true }).click();

  const createdExport = page.locator("article").filter({ hasText: "Fine-tuning dataset · v1" });
  await expect(createdExport).toBeVisible();
  const download = createdExport.getByRole("link", { name: "Download", exact: true });
  await expect(download).toHaveAttribute("download", "");
  await expect(download).toHaveAttribute("href", /\/api\/v1\/exports\/export-\d+\/download/);
});

test("cancels an active generation without leaving the core workbench", async ({ page }) => {
  await page.getByRole("button", { name: "More", exact: true }).click();
  await page.getByRole("button", { name: "Runs", exact: true }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel run", exact: true }).click();
  await expect(page.getByText("Run cancelled", { exact: true })).toBeVisible();
});

test("fits desktop, tablet, and mobile without horizontal overflow", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 820, height: 1180 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("h1")).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  }
});

test("mobile drawer stays hidden until opened and keeps the destination title visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar).toBeHidden();

  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(sidebar).toBeVisible();
  await sidebar.getByRole("button", { name: "Review", exact: true }).click();

  const heading = page.getByRole("heading", { name: "Review candidates" });
  await expect(heading).toBeVisible();
  const position = await heading.boundingBox();
  expect(position?.y ?? 0).toBeGreaterThanOrEqual(58);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await expect(sidebar).toBeHidden();
});
