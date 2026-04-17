# Database approach

## Storage

- SQLite in a local file for the MVP
- Database created automatically if missing on backend startup

## Identity

- User IDs, board IDs, column IDs, and card IDs are stored as TEXT (UUID-style strings)
- One board per user for the MVP, enforced via a unique index on boards.user_id

## Ordering strategy

- Columns and cards use an integer position per parent
- Reordering updates positions within the affected parent scope

## Schema source

- Canonical schema proposal lives in docs/db-schema.json
