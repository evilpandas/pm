import { expect, test } from "@playwright/test";

const boardResponse = {
  id: "board-1",
  title: "Kanban Studio",
  columns: [
    { id: "col-backlog", title: "Backlog", position: 0, cardIds: ["card-1", "card-2"] },
    { id: "col-discovery", title: "Discovery", position: 1, cardIds: ["card-3"] },
    { id: "col-progress", title: "In Progress", position: 2, cardIds: ["card-4", "card-5"] },
    { id: "col-review", title: "Review", position: 3, cardIds: ["card-6"] },
    { id: "col-done", title: "Done", position: 4, cardIds: ["card-7", "card-8"] },
  ],
  cards: {
    "card-1": {
      id: "card-1",
      title: "Align roadmap themes",
      details: "Draft quarterly themes with impact statements and metrics.",
      position: 0,
      columnId: "col-backlog",
    },
    "card-2": {
      id: "card-2",
      title: "Gather customer signals",
      details: "Review support tags, sales notes, and churn feedback.",
      position: 1,
      columnId: "col-backlog",
    },
    "card-3": {
      id: "card-3",
      title: "Prototype analytics view",
      details: "Sketch initial dashboard layout and key drill-downs.",
      position: 0,
      columnId: "col-discovery",
    },
    "card-4": {
      id: "card-4",
      title: "Refine status language",
      details: "Standardize column labels and tone across the board.",
      position: 0,
      columnId: "col-progress",
    },
    "card-5": {
      id: "card-5",
      title: "Design card layout",
      details: "Add hierarchy and spacing for scanning dense lists.",
      position: 1,
      columnId: "col-progress",
    },
    "card-6": {
      id: "card-6",
      title: "QA micro-interactions",
      details: "Verify hover, focus, and loading states.",
      position: 0,
      columnId: "col-review",
    },
    "card-7": {
      id: "card-7",
      title: "Ship marketing page",
      details: "Final copy approved and asset pack delivered.",
      position: 0,
      columnId: "col-done",
    },
    "card-8": {
      id: "card-8",
      title: "Close onboarding sprint",
      details: "Document release notes and share internally.",
      position: 1,
      columnId: "col-done",
    },
  },
};

const mockApi = async (page: import("@playwright/test").Page) => {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (url.endsWith("/api/board") && method === "GET") {
      await route.fulfill({ json: boardResponse });
      return;
    }

    if (url.endsWith("/api/cards") && method === "POST") {
      const body = request.postDataJSON() as { title: string; details?: string };
      await route.fulfill({
        json: {
          id: "card-new",
          title: body.title,
          details: body.details || "No details yet.",
          position: 0,
          columnId: "col-backlog",
        },
      });
      return;
    }

    if (url.includes("/api/cards/") && method === "PATCH") {
      const body = request.postDataJSON() as { title?: string; details?: string };
      const cardId = url.split("/api/cards/")[1];
      await route.fulfill({
        json: {
          id: cardId,
          title: body.title ?? "Untitled card",
          details:
            body.details ??
            "No details yet.",
          position: 0,
          columnId: "col-backlog",
        },
      });
      return;
    }

    await route.fulfill({ json: { status: "ok" } });
  });
};

const login = async (page: import("@playwright/test").Page) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByPlaceholder("user").fill("user");
  await page.getByPlaceholder("password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
};

test("loads the kanban board after login", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
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
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("edits a card after creation", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();

  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright editable card");
  await firstColumn.getByPlaceholder("Details").fill("Before edit");
  await firstColumn.getByRole("button", { name: /add card/i }).click();

  const newCard = firstColumn.getByTestId("card-card-new");
  await expect(newCard).toBeVisible();

  await newCard.getByRole("button", { name: /edit playwright editable card/i }).click();
  await newCard.getByLabel(/edit title for playwright editable card/i).fill("Playwright edited card");
  await newCard.getByLabel(/edit details for playwright editable card/i).fill("After edit");
  await newCard.getByRole("button", { name: /save playwright editable card/i }).click();

  await expect(firstColumn.getByText("Playwright edited card")).toBeVisible();
  await expect(firstColumn.getByText("After edit")).toBeVisible();
});
