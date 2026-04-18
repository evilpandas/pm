import { expect, test } from "@playwright/test";

const login = async (page: import("@playwright/test").Page) => {
  await page.goto("/");
  await page.getByPlaceholder("username").fill("jared");
  await page.getByPlaceholder("passphrase").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-testid^="column-"]', { timeout: 10000 });
};

test("loads the kanban board after login", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("button", { name: /log out/i })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card").last()).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);

  // Get the first card from any column
  const firstCard = page.locator('[data-testid^="card-"]').first();
  const cardId = await firstCard.getAttribute("data-testid");

  // Get a different column to move it to
  const targetColumn = page.locator('[data-testid^="column-"]').nth(3);

  const cardBox = await firstCard.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();

  // Verify card is now in the target column
  await expect(targetColumn.locator(`[data-testid="${cardId}"]`)).toBeVisible();
});

test("edits a card after creation", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright editable card");
  await firstColumn.getByPlaceholder("Details").fill("Before edit");
  await firstColumn.getByRole("button", { name: /add card/i }).click();

  // Wait for the card to appear
  const newCard = firstColumn.locator('[data-testid^="card-"]', { hasText: "Playwright editable card" }).first();
  await expect(newCard).toBeVisible();

  // Click the card to open modal
  await newCard.click();

  // Wait for modal to open and click Edit button
  const modal = page.locator('[role="dialog"][aria-modal="true"]');
  await expect(modal).toBeVisible();
  await modal.getByRole("button", { name: /^edit/i }).click();

  // Edit the card fields
  await modal.getByLabel(/edit title/i).fill("Playwright edited card");
  await modal.getByLabel(/edit details/i).fill("After edit");
  await modal.getByRole("button", { name: /^save/i }).click();

  // Close modal and verify the card was updated
  await page.keyboard.press("Escape");
  await expect(firstColumn.getByText("Playwright edited card").last()).toBeVisible();
});
