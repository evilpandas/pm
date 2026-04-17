import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "@/app/page";
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

const setupFetchMock = () => {
  const board = buildApiBoard();
  global.fetch = vi.fn(async (input) => {
    const requestUrl = typeof input === "string" ? input : input.url;
    if (requestUrl.endsWith("/api/board")) {
      return new Response(JSON.stringify(board), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
};

describe("Home login flow", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the login form by default", () => {
    setupFetchMock();
    render(<Home />);
    expect(screen.getByText(/welcome back to kanban studio/i)).toBeInTheDocument();
    expect(screen.queryByTestId(/column-/i)).not.toBeInTheDocument();
  });

  it("shows an error on invalid credentials", async () => {
    setupFetchMock();
    render(<Home />);
    await userEvent.type(screen.getByPlaceholderText("user"), "wrong");
    await userEvent.type(screen.getByPlaceholderText("password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
  });

  it("allows login and logout", async () => {
    setupFetchMock();
    render(<Home />);
    await userEvent.type(screen.getByPlaceholderText("user"), "user");
    await userEvent.type(screen.getByPlaceholderText("password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    const columns = await screen.findAllByTestId(/column-/i);
    expect(columns).toHaveLength(5);
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(screen.getByText(/welcome back to kanban studio/i)).toBeInTheDocument();
  });
});
