# Permit Query Agent — instructions

**Use the `permit-query-agent` subagent** (`.claude/agents/permit-query-agent.md`)
for any request to look up, count, or summarize permit records — it already
knows the schema-first workflow, join rules, and edge cases below.

This project exposes a read-only SQL interface to a permit database over MCP
(`permit-db` server). Two tools are available:

- `get_database_schema()` — returns every queryable table with its columns and
  foreign keys.
- `query_permits(sql)` — runs a single validated read-only `SELECT`.

## Workflow — always follow this order

```
User question → get_database_schema() → generate SQL → query_permits(sql) → results
```

1. **Call `get_database_schema()` first** whenever you are unsure of a table or
   column name. Never invent them.
2. **Use only the tables and columns returned by the schema tool.** The SQL
   Guard enforces an allowlist; a guessed name (e.g. `statuses` instead of
   `permit_statuses`) is rejected with `Access to '<name>' is not allowed.`
3. **Always join lookup tables instead of returning raw ids.** Return
   human-readable values, not foreign keys.
   - `permits.status_id` → join `permit_statuses` (`status`)
   - `permits.permit_type_id` → join `permit_types` (`name`)
   - `permits.city_id` → join `cities` (`city_name`)
   - `permits.officer_id` → join `officers` (`name`)

## Query constraints (enforced by the SQL Guard)

- `SELECT` only. `INSERT/UPDATE/DELETE/DROP/…`, `SHOW`, `DESCRIBE`, multiple
  statements, comments, and file I/O are all blocked.
- A `LIMIT` is auto-appended (max 100) when absent.
- Do not attempt DDL/DML or schema-introspection SQL (`SHOW TABLES`,
  `DESCRIBE`) — use `get_database_schema()` for structure instead.

## Development

- Run tests with `pytest`.
- Table allowlist lives in `app/security/constants.py` (`ALLOWED_TABLES`); the
  schema tool intersects it with the live database so it never advertises a
  table the guard would block.
