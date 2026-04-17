"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import {
  findCardLocation,
  mapBoardResponse,
  moveCard,
  type ApiBoard,
  type BoardData,
} from "@/lib/kanban";

export const KanbanBoard = () => {
  const [board, setBoard] = useState<BoardData | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [modalCardId, setModalCardId] = useState<string | null>(null);
  const [isModalEditing, setIsModalEditing] = useState(false);
  const [modalTitle, setModalTitle] = useState("");
  const [modalDetails, setModalDetails] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [chatMessages, setChatMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [chatInput, setChatInput] = useState("");
  const [chatError, setChatError] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);
  const isMounted = useRef(true);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board?.cards ?? {}, [board]);

  const loadBoard = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setIsLoading(true);
    }
    setErrorMessage("");
    try {
      const response = await fetch("/api/board");
      if (!response.ok) {
        throw new Error("Failed to load board");
      }
      const payload = (await response.json()) as ApiBoard;
      if (isMounted.current) {
        setBoard(mapBoardResponse(payload));
      }
    } catch (error) {
      if (isMounted.current) {
        setErrorMessage("Unable to load the board right now.");
      }
    } finally {
      if (isMounted.current && showLoading) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const nextColumns = moveCard(
      board.columns,
      active.id as string,
      over.id as string
    );
    setBoard({ ...board, columns: nextColumns });

    const nextLocation = findCardLocation(nextColumns, active.id as string);
    if (!nextLocation) {
      return;
    }

    fetch(`/api/cards/${active.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        column_id: nextLocation.columnId,
        position: nextLocation.position,
      }),
    })
      .then((response) => {
        if (!response.ok) {
          setErrorMessage("Unable to move the card. Try again.");
        }
      })
      .catch(() => {
        setErrorMessage("Unable to move the card. Try again.");
      });
  };

  const handleRenameColumn = async (columnId: string, title: string) => {
    if (!board) {
      return;
    }

    setBoard({
      ...board,
      columns: board.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    });

    try {
      const response = await fetch(`/api/columns/${columnId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!response.ok) {
        setErrorMessage("Unable to rename the column.");
      }
    } catch (error) {
      setErrorMessage("Unable to rename the column.");
    }
  };

  const handleAddCard = async (
    columnId: string,
    title: string,
    details: string
  ) => {
    if (!board) {
      return;
    }

    try {
      const response = await fetch("/api/cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ column_id: columnId, title, details }),
      });

      if (!response.ok) {
        setErrorMessage("Unable to add the card.");
        return;
      }

      const card = (await response.json()) as {
        id: string;
        title: string;
        details: string;
      };

      setBoard((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          cards: {
            ...prev.cards,
            [card.id]: {
              id: card.id,
              title: card.title,
              details: card.details,
            },
          },
          columns: prev.columns.map((column) =>
            column.id === columnId
              ? { ...column, cardIds: [...column.cardIds, card.id] }
              : column
          ),
        };
      });
    } catch (error) {
      setErrorMessage("Unable to add the card.");
    }
  };

  const handleUpdateCard = async (
    cardId: string,
    title: string,
    details: string
  ) => {
    if (!board) {
      return;
    }

    const previousCard = board.cards[cardId];
    if (!previousCard) {
      return;
    }

    setBoard((prev) => {
      if (!prev) {
        return prev;
      }
      return {
        ...prev,
        cards: {
          ...prev.cards,
          [cardId]: {
            ...prev.cards[cardId],
            title,
            details,
          },
        },
      };
    });

    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, details }),
      });

      if (!response.ok) {
        throw new Error("Unable to update card");
      }

      const updated = (await response.json()) as {
        id: string;
        title: string;
        details: string;
      };

      setBoard((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          cards: {
            ...prev.cards,
            [updated.id]: {
              id: updated.id,
              title: updated.title,
              details: updated.details,
            },
          },
        };
      });
    } catch (error) {
      setBoard((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          cards: {
            ...prev.cards,
            [cardId]: previousCard,
          },
        };
      });
      setErrorMessage("Unable to update the card.");
    }
  };

  const handleDeleteCard = async (columnId: string, cardId: string) => {
    if (!board) {
      return;
    }

    try {
      const response = await fetch(`/api/cards/${cardId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        setErrorMessage("Unable to delete the card.");
        return;
      }

      setBoard((prev) => {
        if (!prev) {
          return prev;
        }
        return {
          ...prev,
          cards: Object.fromEntries(
            Object.entries(prev.cards).filter(([id]) => id !== cardId)
          ),
          columns: prev.columns.map((column) =>
            column.id === columnId
              ? {
                  ...column,
                  cardIds: column.cardIds.filter((id) => id !== cardId),
                }
              : column
          ),
        };
      });
    } catch (error) {
      setErrorMessage("Unable to delete the card.");
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;
  const modalCard = modalCardId ? cardsById[modalCardId] : null;

  const openCardModal = (cardId: string) => {
    const card = cardsById[cardId];
    if (!card) {
      return;
    }
    setModalCardId(cardId);
    setModalTitle(card.title);
    setModalDetails(card.details);
    setIsModalEditing(false);
  };

  const closeCardModal = () => {
    setModalCardId(null);
    setIsModalEditing(false);
  };

  const handleModalSave = () => {
    if (!modalCardId) {
      return;
    }
    const nextTitle = modalTitle.trim();
    if (!nextTitle) {
      return;
    }
    const nextDetails = modalDetails.trim();
    handleUpdateCard(modalCardId, nextTitle, nextDetails);
    setModalTitle(nextTitle);
    setModalDetails(nextDetails);
    setIsModalEditing(false);
  };

  const handleModalDelete = () => {
    if (!board || !modalCardId) {
      return;
    }
    const location = findCardLocation(board.columns, modalCardId);
    if (!location) {
      return;
    }
    handleDeleteCard(location.columnId, modalCardId);
    closeCardModal();
  };

  const handleChatSubmit = async () => {
    if (!chatInput.trim() || isChatLoading) {
      return;
    }

    const nextMessage = chatInput.trim();
    setChatInput("");
    setChatError("");
    setIsChatLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: nextMessage,
          conversation: chatMessages,
        }),
      });

      if (!response.ok) {
        throw new Error("Chat failed");
      }

      const payload = (await response.json()) as {
        reply: string;
        operations: unknown[];
      };

      setChatMessages((prev) => [
        ...prev,
        { role: "user", content: nextMessage },
        { role: "assistant", content: payload.reply },
      ]);

      await loadBoard(false);
    } catch (error) {
      setChatError("Unable to reach the assistant right now.");
      setChatMessages((prev) => [
        ...prev,
        { role: "user", content: nextMessage },
        {
          role: "assistant",
          content: "I ran into an issue. Please try again in a moment.",
        },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

        <main className="relative mx-auto flex min-h-screen max-w-[1500px] items-center justify-center px-6 pb-16 pt-12">
          <p className="rounded-full border border-[var(--stroke)] bg-white/90 px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            Loading board
          </p>
        </main>
      </div>
    );
  }

  if (!board) {
    return (
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

        <main className="relative mx-auto flex min-h-screen max-w-[1500px] items-center justify-center px-6 pb-16 pt-12">
          <p className="rounded-2xl border border-[var(--stroke)] bg-white/90 px-5 py-3 text-sm text-[var(--gray-text)]">
            {errorMessage || "Unable to load the board."}
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                {board.title}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
          {errorMessage ? (
            <p className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-2 text-xs font-semibold text-[var(--secondary-purple)]">
              {errorMessage}
            </p>
          ) : null}
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId])}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onOpenCard={openCardModal}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex h-full flex-col rounded-[28px] border border-[var(--stroke)] bg-white/85 p-5 shadow-[var(--shadow)] backdrop-blur">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
                  Assistant
                </p>
                <h2 className="mt-2 font-display text-xl font-semibold text-[var(--navy-dark)]">
                  Chat to update the board
                </h2>
              </div>
              <span className="rounded-full border border-[var(--stroke)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)]">
                Live
              </span>
            </div>

            <div className="mt-4 flex min-h-[280px] flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-4">
              {chatMessages.length === 0 ? (
                <div className="space-y-3 text-sm text-[var(--gray-text)]">
                  <p className="font-semibold text-[var(--navy-dark)]">
                    Ask the assistant to adjust your board.
                  </p>
                  <p>
                    Try: “Move the analytics card to Review” or “Add a QA column.”
                  </p>
                </div>
              ) : null}
              {chatMessages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${
                      message.role === "user"
                        ? "bg-[var(--secondary-purple)] text-white"
                        : "bg-white text-[var(--navy-dark)]"
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
            </div>

            {chatError ? (
              <p className="mt-3 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--secondary-purple)]">
                {chatError}
              </p>
            ) : null}

            <form
              className="mt-4 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                handleChatSubmit();
              }}
            >
              <label className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Message
              </label>
              <textarea
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Describe the update you want."
                className="h-24 w-full resize-none rounded-2xl border border-[var(--stroke)] bg-white px-3 py-3 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                aria-label="Chat message"
              />
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
                  {isChatLoading ? "Thinking" : "Ready"}
                </span>
                <button
                  type="submit"
                  className="rounded-full bg-[var(--primary-blue)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
                  disabled={isChatLoading || !chatInput.trim()}
                  aria-label="Send chat message"
                >
                  Send
                </button>
              </div>
            </form>
          </aside>
        </div>
        {modalCard ? (
          <div
            className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(3,33,71,0.45)] px-6 py-10"
            role="dialog"
            aria-modal="true"
            aria-label="Card details"
            onClick={closeCardModal}
          >
            <div
              className="w-full max-w-[560px] rounded-[28px] border border-[var(--stroke)] bg-white p-6 shadow-[0_30px_80px_rgba(3,33,71,0.35)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  {isModalEditing ? (
                    <input
                      value={modalTitle}
                      onChange={(event) => setModalTitle(event.target.value)}
                      className="mt-3 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 font-display text-2xl font-semibold text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
                      aria-label={`Edit title for ${modalCard.title}`}
                    />
                  ) : (
                    <h3 className="mt-3 font-display text-2xl font-semibold text-[var(--navy-dark)]">
                      {modalCard.title}
                    </h3>
                  )}
                </div>
                <button
                  type="button"
                  onClick={closeCardModal}
                  className="rounded-full border border-[var(--stroke)] p-2 text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
                  aria-label="Close"
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M6 6l12 12" />
                    <path d="M18 6l-12 12" />
                  </svg>
                </button>
              </div>
              <div className="mt-4">
                {isModalEditing ? (
                  <textarea
                    value={modalDetails}
                    onChange={(event) => setModalDetails(event.target.value)}
                    className="w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-3 text-sm leading-6 text-[var(--gray-text)] outline-none focus:border-[var(--primary-blue)]"
                    rows={6}
                    aria-label={`Edit details for ${modalCard.title}`}
                  />
                ) : (
                  <p className="whitespace-pre-wrap text-sm leading-6 text-[var(--gray-text)]">
                    {modalCard.details}
                  </p>
                )}
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                {isModalEditing ? (
                  <button
                    type="button"
                    onClick={handleModalSave}
                    className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110"
                    aria-label={`Save ${modalCard.title}`}
                  >
                    Save
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsModalEditing(true)}
                    className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)] transition hover:border-[var(--primary-blue)]"
                    aria-label={`Edit ${modalCard.title}`}
                  >
                    Edit
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleModalDelete}
                  className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
                  aria-label={`Remove ${modalCard.title}`}
                >
                  Remove
                </button>
                {isModalEditing ? (
                  <button
                    type="button"
                    onClick={() => {
                      setModalTitle(modalCard.title);
                      setModalDetails(modalCard.details);
                      setIsModalEditing(false);
                    }}
                    className="rounded-full border border-transparent px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:border-[var(--stroke)]"
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
};
