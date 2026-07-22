# permit-query-agent

## Project Structure

```
permit-query-agent/
│
├── app/                  # Application source
│   ├── agent/            # Agent orchestration / reasoning loop
│   ├── config/           # Settings & environment loading
│   ├── database/         # DB connection & session management
│   ├── logging/          # Logging setup
│   ├── mcp/              # MCP server / client integration
│   ├── models/           # Data models / schemas
│   ├── repositories/     # Data access layer (queries)
│   ├── security/         # Auth, secrets, input validation
│   ├── services/         # Business logic
│   └── utils/            # Shared helpers
│
├── ui/                   # User interface (Streamlit app)
├── tests/                # Test suite
├── scripts/              # One-off / setup scripts
│
├── .env                  # Local secrets (git-ignored)
├── .mcp.json             # MCP server configuration
├── requirements.txt
├── README.md
└── .gitignore
```

## Database

MySQL 8.0, database name `permits`. Connection settings are read from `.env`
(see `.env.example`). Use `app/database/db.py::get_connection()`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials
python -m app.database.db   # smoke-test the DB connection
```
