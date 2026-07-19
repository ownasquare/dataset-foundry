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
  for (const view of ["Projects", "Generate", "Runs"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(page.locator("h1")).not.toBeEmpty();
  }

  await page.getByText("Recipe and provenance", { exact: true }).click();
  await expect(page.getByText("Run reference", { exact: true })).toBeVisible();

  for (const view of ["Review", "Exports", "Settings"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(page.locator("h1")).not.toBeEmpty();
  }
  await expect(page.getByText("Provider secrets are never sent to the browser.")).toBeVisible();

  await page.getByRole("radio", { name: "Light Light surfaces" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("radio", { name: "Dark Dark surfaces" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
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
