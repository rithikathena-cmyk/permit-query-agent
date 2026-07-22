"""Create (or update) the least-privilege read-only DB user for the app.

The application and MCP server connect as this user. It can only ``SELECT``
within the permit database, so even if the SQL Guard were bypassed the
connection still cannot read other schemas (``mysql``, another app's database)
or write anything.

Run as an admin: credentials come from ``DB_ADMIN_USER`` / ``DB_ADMIN_PASSWORD``
(falling back to ``DB_USER`` / ``DB_PASSWORD``). The read-only user's password
is taken from ``RO_DB_PASSWORD``; its name defaults to ``permit_ro``.

    RO_DB_PASSWORD=... python -m scripts.create_readonly_user
"""
import os
import sys

from sqlalchemy import text

from app.database.connection import admin_engine

RO_USER = os.getenv("RO_DB_USER", "permit_ro")
RO_PASS = os.getenv("RO_DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "permit_system")


def main() -> None:
    if not RO_PASS:
        sys.exit("Set RO_DB_PASSWORD to the read-only user's password.")

    # Identifiers can't be bound parameters; they come from trusted env config,
    # not request input. The password IS bound (:pw) so quoting is handled.
    engine = admin_engine()
    with engine.begin() as conn:
        conn.execute(
            text(f"CREATE USER IF NOT EXISTS '{RO_USER}'@'%' "
                 "IDENTIFIED BY :pw"),
            {"pw": RO_PASS},
        )
        conn.execute(
            text(f"ALTER USER '{RO_USER}'@'%' IDENTIFIED BY :pw"),
            {"pw": RO_PASS},
        )
        # Strip any pre-existing privileges, then grant SELECT only.
        try:
            conn.execute(
                text(f"REVOKE ALL PRIVILEGES, GRANT OPTION "
                     f"FROM '{RO_USER}'@'%'")
            )
        except Exception:  # noqa: BLE001 — nothing to revoke on a fresh user
            pass
        conn.execute(
            text(f"GRANT SELECT ON `{DB_NAME}`.* TO '{RO_USER}'@'%'")
        )
        # The app appends to its query-audit log. Allow INSERT on that ONE
        # table (append-only telemetry) so auditing keeps working — the guard
        # still blocks reading it, and no other table is writable.
        conn.execute(
            text(f"GRANT INSERT ON `{DB_NAME}`.`query_audit` "
                 f"TO '{RO_USER}'@'%'")
        )

    print(
        f"Read-only user '{RO_USER}'@'%' ready — SELECT on {DB_NAME}.*, "
        "INSERT on query_audit only."
    )


if __name__ == "__main__":
    main()
