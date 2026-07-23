# permit-query-agent

A read-only, natural-language interface to a permit database. Ask a question in
plain English; the local Claude Code CLI writes a `SELECT`, runs it through a
validated MCP tool (`permit-db`), and explains the result. A Streamlit UI wraps
it with deterministic Discover/Analytics pages that never call the LLM.

## Project Structure

```
permit-query-agent/
│
├── app/                  # Application source
│   ├── agent/            # PermitAgent — drives the `claude` CLI + MCP tools
│   ├── config/           # Query-safety / logging settings
│   ├── database/         # Engine, session, schema init (connection.py)
│   ├── logging/          # Logging setup
│   ├── mcp/              # MCP server + tool layer (SQL entry point)
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Data access layer (queries)
│   ├── security/         # SQL Guard, audit, table allowlist
│   ├── services/         # Query / schema / statistics services
│   └── utils/            # Shared helpers
│
├── ui/                   # Streamlit app (app.py) + deterministic reads (data.py)
├── scripts/              # Setup: init_db, create_readonly_user, seed_data
├── certs/                # DB TLS certs (e.g. Aiven ca.pem) — git-ignored
├── tests/                # Test suite
│
├── .env                  # Local secrets (git-ignored)
├── .env.example          # Copy to .env and fill in
├── .mcp.json             # MCP server configuration
└── requirements.txt
```

## Database

MySQL 8, database `permit_system` (or Aiven's `defaultdb`). All connection
settings are read from `.env` — see `.env.example`. Two supported targets:

- **Local MySQL** — `DB_HOST=localhost`, `DB_PORT=3306`, `DB_SSL` unset.
- **Aiven for MySQL** — the service host/port, `DB_SSL=true`. Aiven requires
  TLS; to verify the server cert, download `ca.pem` into `certs/` and set
  `DB_SSL_CA=./certs/aiven-ca.pem`.

The app connects as a least-privilege **read-only** user (`DB_USER`); setup
scripts use the admin credentials (`DB_ADMIN_USER` / `DB_ADMIN_PASSWORD`).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env            # then fill in host / credentials

python -m app.database.init_db  # create the tables (admin creds)

# create the read-only app user (name defaults to permit_ro)
RO_DB_PASSWORD=your_ro_password python -m scripts.create_readonly_user

python -m scripts.seed_data     # load ~1,000 sample permits
```

## Run

```bash
streamlit run ui/app.py         # UI — needs the `claude` CLI on PATH for Ask AI
pytest                          # test suite
```
