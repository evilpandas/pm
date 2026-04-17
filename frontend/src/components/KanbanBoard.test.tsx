import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type ApiBoard } from "@/lib/kanban";
import { vi } from "vitest";

const buildApiBoard = (): ApiBoard => {
  const cards: ApiBoard["cards"] = {};
  initialData.columns.forEach((column) => {
    column.cardIds.forEach((cardId, cardIndex) => {
      const card = initialData.cards[cardId];
      cards[cardId] = {
        id: card.id,
        title: card.title,
        details: card.details,
        position: cardIndex,
        columnId: column.id,
      };
    });
  });

  return {
    id: "board-1",
    title: "Kanban Studio",
    columns: initialData.columns.map((column, index) => ({
      id: column.id,
      title: column.title,
      position: index,
      cardIds: [...column.cardIds],
    })),
    cards,
  };
};

const jsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

const setupFetchMock = () => {
  let board = buildApiBoard();
  global.fetch = vi.fn(async (input, init) => {
    const requestUrl = typeof input === "string" ? input : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const body = init?.body ? JSON.parse(init.body as string) : {};

    if (requestUrl.endsWith("/api/board") && method === "GET") {
      return jsonResponse(board);
    }

    if (requestUrl.endsWith("/api/board") && method === "PATCH") {
      board = { ...board, title: body.title ?? board.title };
      return jsonResponse(board);
    }

    if (requestUrl.endsWith("/api/columns") && method === "POST") {
      const newColumn = {
        id: "col-new",
        title: body.title,
        position: board.columns.length,
        cardIds: [],
      };
      board = { ...board, columns: [...board.columns, newColumn] };
      return jsonResponse(newColumn);
    }

    if (requestUrl.includes("/api/columns/") && method === "PATCH") {
      const columnId = requestUrl.split("/api/columns/")[1];
      board = {
        ...board,
        columns: board.columns.map((column) =>
          column.id === columnId
            ? { ...column, title: body.title ?? column.title }
            : column
        ),
      };
      const updated = board.columns.find((column) => column.id === columnId);
      return jsonResponse(updated ?? { status: "not found" }, updated ? 200 : 404);
    }

    if (requestUrl.endsWith("/api/cards") && method === "POST") {
      const cardId = "card-new";
      const card = {
        id: cardId,
        title: body.title,
        details: body.details || "No details yet.",
        position: 0,
        columnId: body.column_id,
      };
      board = {
        ...board,
        cards: { ...board.cards, [cardId]: card },
        columns: board.columns.map((column) =>
          column.id === body.column_id
            ? { ...column, cardIds: [...column.cardIds, cardId] }
            : column
        ),
      };
      return jsonResponse(card);
    }

    if (requestUrl.includes("/api/cards/") && method === "PATCH") {
      const cardId = requestUrl.split("/api/cards/")[1];
      const existing = board.cards[cardId];
      if (!existing) {
        return jsonResponse({ detail: "not found" }, 404);
      }
      const updated = {
        ...existing,
        title: body.title ?? existing.title,
        details: body.details ?? existing.details,
        columnId: body.column_id ?? existing.columnId,
        position: body.position ?? existing.position,
      };
      board = { ...board, cards: { ...board.cards, [cardId]: updated } };
      return jsonResponse(updated);
    }

    if (requestUrl.includes("/api/cards/") && method === "DELETE") {
      const cardId = requestUrl.split("/api/cards/")[1];
      const { [cardId]: _, ...remainingCards } = board.cards;
      board = {
        ...board,
        cards: remainingCards,
        columns: board.columns.map((column) => ({
          ...column,
          cardIds: column.cardIds.filter((id) => id !== cardId),
        })),
      };
      return jsonResponse({ status: "ok" });
    }

    if (requestUrl.endsWith("/api/chat") && method === "POST") {
      const cardId = "card-ai";
      const columnId = board.columns[0].id;
      const card = {
        id: cardId,
        title: "AI card",
        details: "Added by assistant",
        position: 0,
        columnId,
      };
      board = {
        ...board,
        cards: { ...board.cards, [cardId]: card },
        columns: board.columns.map((column) =>
          column.id === columnId
            ? { ...column, cardIds: [cardId, ...column.cardIds] }
            : column
        ),
      };
      return jsonResponse({ reply: "Added the card.", operations: [] });
    }

    return jsonResponse({ status: "ok" });
  }) as unknown as typeof fetch;
};

describe("KanbanBoard", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders five columns", () => {
    setupFetchMock();
    render(<KanbanBoard />);
    return screen.findAllByTestId(/column-/i).then((columns) => {
      expect(columns).toHaveLength(5);
    });
  });

  it("renames a column", async () => {
    setupFetchMock();
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    setupFetchMock();
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await within(column).findByText("New card")).toBeInTheDocument();

    await userEvent.click(within(column).getByText("New card"));
    const dialog = await screen.findByRole("dialog", { name: /card details/i });
    const deleteButton = within(dialog).getByRole("button", {
      name: /remove new card/i,
    });
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(within(column).queryByText("New card")).not.toBeInTheDocument();
    });
  });

  it("edits a card title and details", async () => {
    setupFetchMock();
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);

    const card = screen.getByTestId("card-card-1");
    await userEvent.click(within(card).getByText("Align roadmap themes"));
    const dialog = await screen.findByRole("dialog", { name: /card details/i });
    await userEvent.click(
      within(dialog).getByRole("button", { name: /edit align roadmap themes/i })
    );

    const titleInput = within(dialog).getByLabelText(/edit title for align roadmap themes/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Updated roadmap theme");

    const detailsInput = within(dialog).getByLabelText(
      /edit details for align roadmap themes/i
    );
    await userEvent.clear(detailsInput);
    await userEvent.type(detailsInput, "Updated details from test.");

    await userEvent.click(
      within(dialog).getByRole("button", { name: /save align roadmap themes/i })
    );

    await waitFor(() => {
      expect(within(dialog).getByText("Updated roadmap theme")).toBeInTheDocument();
      expect(
        within(dialog).getByText("Updated details from test.")
      ).toBeInTheDocument();
      expect(within(card).getByText("Updated roadmap theme")).toBeInTheDocument();
    });
  });

  it("opens a modal when clicking the card body", async () => {
    setupFetchMock();
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);

    const card = screen.getByTestId("card-card-1");
    await userEvent.click(within(card).getByText("Align roadmap themes"));

    const dialog = await screen.findByRole("dialog", { name: /card details/i });
    expect(within(dialog).getByText("Align roadmap themes")).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: /edit align roadmap themes/i })
    ).toBeInTheDocument();
  });

  it("sends a chat message and refreshes the board", async () => {
    setupFetchMock();
    render(<KanbanBoard />);
    await screen.findAllByTestId(/column-/i);

    const input = screen.getByLabelText("Chat message");
    await userEvent.type(input, "Add a new card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(await screen.findByText("Added the card.")).toBeInTheDocument();
    expect(await screen.findByText("AI card")).toBeInTheDocument();
  });
});
