# Project plan

This plan expands each phase with concrete checklists, tests, and success criteria. After Part 1 is done, pause for user approval before starting Part 2.

## Design decisions log

- 2026-04-16: Card interactions use a modal view on click; inline edit/remove controls are removed from board cards.
- 2026-04-16: Modal actions include Edit, Save, Remove; no "click to edit" or preview copy in the modal.
- 2026-04-16: Modal close control is icon-only instead of a text button.

## Part 1: Plan

Checklist
- [x] Review requirements and constraints from AGENTS.md and docs/PLAN.md
- [x] Expand each part below with actionable steps, tests, and success criteria
- [x] Create frontend/AGENTS.md describing the current frontend structure (high level)
- [x] Ask user to review and approve the plan before any implementation work

Tests
- No code execution; validation is human review
- Record minimum unit test coverage target: 80%
- Record requirement for robust integration testing

Success criteria
- Plan is detailed, testable, and aligns with business and technical constraints
- frontend/AGENTS.md exists and matches current frontend code
- User explicitly approves the plan before Part 2

## Part 2: Scaffolding

Checklist
- [x] Add Dockerfile and docker-compose.yml at repo root to run full app locally
- [x] Create FastAPI backend in backend/ with minimal app structure
- [x] Serve example static HTML at / to verify backend serving
- [x] Add a sample API route (for example, /api/health) returning JSON
- [x] Add start and stop scripts in scripts/ for macOS, Windows, Linux
- [x] Ensure uv is used for Python dependency management inside container
- [ ] Document run steps briefly in docs/ or README as needed

Tests
- Run start script to bring up container (validated)
- Visit / to confirm example HTML renders (validated)
- Call /api/health and confirm JSON response (validated)
- Run stop script to cleanly shut down (validated)
- No coverage requirement yet (no unit tests expected)

Success criteria
- Single container runs locally and serves both HTML and API (met)
- start/stop scripts work on supported platforms (macOS validated)
- Backend uses uv and FastAPI per requirements (met)

## Part 3: Add in Frontend

Checklist
- [x] Update Docker setup to build the Next.js frontend
- [x] Serve the static build from FastAPI at /
- [x] Ensure Kanban demo renders at root
- [x] Wire any required static asset handling
- [x] Keep Next.js build output consistent with container runtime

Tests
- Frontend unit tests with Vitest (passed)
- Frontend integration/e2e tests with Playwright (passed)
- Smoke test: / displays Kanban board in container (validated)
- Enforce minimum 80% unit test coverage (passed)
- Coverage run 2026-04-15: 80.2% statements, 81.81% branches, 81.25% functions, 80.2% lines
- Ensure robust integration testing for core board flows (passed)

Success criteria
- / shows the existing Kanban demo in Docker (met)
- Unit and e2e tests pass (met)

## Part 4: Fake user sign-in experience

Checklist
- [x] Add login screen gated at /
- [x] Use hardcoded credentials (user/password)
- [x] Add logout control
- [x] Preserve minimal state handling (no over-engineering)

Tests
- Unit tests for login logic (passed)
- E2E test for login, view board, logout (passed)
- Enforce minimum 80% unit test coverage (passed)
- Ensure robust integration testing for auth flow (passed)

Success criteria
- Unauthenticated users see login (met)
- Authenticated users see Kanban board (met)
- Logout returns to login view (met)

## Part 5: Database modeling

Checklist
- [x] Propose schema for users, boards, columns, cards, and ordering
- [x] Save schema proposal as JSON in docs/
- [x] Document approach in docs/ (SQLite, IDs, ordering strategy)
- [x] Request user sign-off

Tests
- Schema review is manual
- Coverage target not applicable in this phase

Success criteria
- Schema fits requirements and supports future multi-user
- User approves before Part 6

## Part 6: Backend

Checklist
- [x] Create SQLite database if missing at startup
- [x] Implement CRUD APIs for board/columns/cards scoped to user
- [x] Keep API surface minimal and explicit
- [x] Add backend unit tests with Pytest

Tests
- Pytest unit tests for API routes and data operations (passed 2026-04-15, rerun after lifespan update)
- DB creation and migration behavior validated in tests
- Enforce minimum 80% unit test coverage (passed 2026-04-15: 94% total)
- Ensure robust integration testing for API endpoints

Success criteria
- API persists and retrieves Kanban data correctly (met)
- Tests pass and cover happy paths and basic error cases (met)

## Part 7: Frontend + Backend

Checklist
- [x] Replace frontend in-memory state with API calls
- [x] Keep UI behavior identical to current demo
- [x] Handle loading and error states minimally
- [x] Ensure drag/drop updates persist

Tests
- Frontend unit tests updated for API behavior
- E2E tests verify persistence across reloads
- Enforce minimum 80% unit test coverage
- Ensure robust integration testing for API + UI flows

Success criteria
- Kanban board persists via backend API (met)
- UI remains responsive and consistent (met)

## Part 8: AI connectivity

Checklist
- [x] Add backend OpenRouter client using API key from .env
- [x] Implement a simple test endpoint or test harness

Tests
- Run a "2+2" call and verify expected response (validated 2026-04-16)
- Add a backend integration test for OpenRouter connectivity (can be skipped when key missing, validated 2026-04-16)

Success criteria
- OpenRouter connectivity verified from backend (met)

## Part 9: AI structured outputs for Kanban updates

Checklist
- [x] Define structured response schema (chat reply + optional board updates)
- [x] Send current board JSON + conversation + user message to model
- [x] Parse structured outputs and validate shape
- [x] Update backend board data when updates are provided

Tests
- Unit tests for schema parsing and board update application (validated 2026-04-16)
- API-level tests for chat endpoint behavior (validated 2026-04-16)
- Enforce minimum 80% unit test coverage
- Ensure robust integration testing for structured output handling

Success criteria
- AI replies are returned consistently (met)
- Valid structured updates correctly mutate the board (met)

## Part 10: AI chat sidebar UI

Checklist
- [x] Add a sidebar chat UI matching existing visual language
- [x] Wire chat to backend AI endpoint
- [x] Apply AI-provided board updates to UI
- [x] Refresh board state after AI updates

Tests
- Unit tests for chat UI state handling (validated 2026-04-16)
- [x] E2E test for chat flow with board update
- Enforce minimum 80% unit test coverage
- Ensure robust integration testing for chat + board sync

Success criteria
- Sidebar chat works end-to-end
- Kanban updates reflect AI instructions automatically (met)