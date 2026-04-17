# Frontend overview

## Stack

- Next.js app router with TypeScript
- Tailwind-style utility classes in components
- Drag and drop via @dnd-kit
- Unit tests with Vitest, e2e with Playwright

## Key entry points

- src/app/page.tsx renders the Kanban board
- src/app/layout.tsx sets global layout and styles

## Core UI components

- src/components/KanbanBoard.tsx manages board state and drag/drop
- src/components/KanbanColumn.tsx renders columns with editable titles
- src/components/KanbanCard.tsx renders cards with actions
- src/components/KanbanCardPreview.tsx renders drag overlay preview
- src/components/NewCardForm.tsx adds new cards

## Data model

- src/lib/kanban.ts defines board types, initial data, and card movement logic

## Tests

- src/components/*.test.tsx for component behavior
- src/lib/kanban.test.ts for data logic
- tests/kanban.spec.ts for end-to-end coverage
