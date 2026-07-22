from fastmcp import FastMCP

from app.mcp.tools import (
    execute_query,
    get_schema,
    count_by_status,
    count_by_city,
    count_by_type,
    permit_statistics,
    get_pending_permits,
    search_permits,
)

mcp = FastMCP(
    name="Permit Query Server"
)


@mcp.tool(
    name="get_database_schema",
    description=(
        "Return the accessible database schema: every queryable table with "
        "its columns and foreign keys. Call this BEFORE writing SQL so table "
        "and column names are never guessed. Only tables returned here can be "
        "queried by query_permits."
    ),
)
def get_database_schema():

    """
    Introspect the live database and return the accessible schema.

    Returns
    -------
    JSON response
        ``{"success": True, "table_count": int, "tables": {...}}`` where each
        table maps to its ``columns`` and ``foreign_keys``.
    """

    return get_schema()


@mcp.tool(
    name="query_permits",
    description=(
        "Execute validated read-only SQL "
        "against the permit database."
    ),
)
def query_permits(sql: str):

    """
    Execute a SELECT query.

    Parameters
    ----------
    sql : str

    Returns
    -------
    JSON response
    """

    return execute_query(sql)


# -----------------------------------------------------------------------
# Domain-specific tools
#
# These take no SQL and run parameterized ORM queries, so they need no SQL
# Guard and have no injection surface. Prefer them for the common questions;
# use query_permits for open-ended ones.
# -----------------------------------------------------------------------


@mcp.tool(
    name="count_permits_by_status",
    description="Count permits grouped by status (e.g. Approved, Pending).",
)
def count_permits_by_status():
    return count_by_status()


@mcp.tool(
    name="count_permits_by_city",
    description="Count permits grouped by city.",
)
def count_permits_by_city():
    return count_by_city()


@mcp.tool(
    name="count_permits_by_type",
    description="Count permits grouped by permit type.",
)
def count_permits_by_type():
    return count_by_type()


@mcp.tool(
    name="permit_statistics",
    description=(
        "High-level overview: total permit count plus breakdowns by status "
        "and by type."
    ),
)
def permit_statistics_tool():
    return permit_statistics()


@mcp.tool(
    name="get_pending_permits",
    description=(
        "List permits with status 'Pending', newest first, with lookup names "
        "resolved. Optional limit (default 100)."
    ),
)
def get_pending_permits_tool(limit: int = 100):
    return get_pending_permits(limit=limit)


@mcp.tool(
    name="search_permits",
    description=(
        "Search permits by applicant name or application number "
        "(case-insensitive substring). Optional limit (default 100)."
    ),
)
def search_permits_tool(term: str, limit: int = 100):
    return search_permits(term, limit=limit)


if __name__ == "__main__":
    mcp.run()
