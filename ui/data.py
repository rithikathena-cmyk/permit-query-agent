"""Deterministic, read-only data access for the exploration UI.

These helpers power the non-AI parts of the app — Discover Data, KPI cards,
charts, table previews. They go through the parameterized MCP tool layer
(``app.mcp.tools``), NOT Claude Code, so browsing a table or drawing a chart is
instant and free. Only the "Ask AI" box spends a Claude Code run.

Everything here is read-only and cached briefly to keep the UI snappy.
"""
import streamlit as st

from app.mcp import tools


# -- schema ----------------------------------------------------------------- #
@st.cache_data(ttl=300, show_spinner=False)
def get_schema() -> dict:
    """{table: {columns, foreign_keys}} for every accessible table."""
    resp = tools.get_schema()
    return resp.get("tables", {}) if resp.get("success") else {}


def table_names() -> list[str]:
    return list(get_schema().keys())


# -- aggregates ------------------------------------------------------------- #
@st.cache_data(ttl=60, show_spinner=False)
def count_by_status() -> list[dict]:
    resp = tools.count_by_status()
    return resp.get("data", []) if resp.get("success") else []


@st.cache_data(ttl=60, show_spinner=False)
def count_by_city() -> list[dict]:
    resp = tools.count_by_city()
    return resp.get("data", []) if resp.get("success") else []


@st.cache_data(ttl=60, show_spinner=False)
def count_by_type() -> list[dict]:
    resp = tools.count_by_type()
    return resp.get("data", []) if resp.get("success") else []


@st.cache_data(ttl=60, show_spinner=False)
def kpis() -> dict:
    """Totals for the KPI cards: overall + a per-status map."""
    by_status = {row["status"]: row["count"] for row in count_by_status()}
    return {"total": sum(by_status.values()), "by_status": by_status}


@st.cache_data(ttl=300, show_spinner=False)
def monthly_trend() -> list[dict]:
    """Permits submitted per calendar month (for the trend chart)."""
    resp = tools.execute_query(
        "SELECT DATE_FORMAT(submitted_date, '%Y-%m') AS month, "
        "COUNT(*) AS permits FROM permits "
        "GROUP BY month ORDER BY month"
    )
    return resp.get("data", []) if resp.get("success") else []


# -- sample preview --------------------------------------------------------- #
@st.cache_data(ttl=300, show_spinner=False)
def preview_table(table: str, limit: int = 5) -> dict:
    """First few rows of a table. The table name is validated against the live
    schema before it is interpolated, so no arbitrary identifier reaches SQL —
    and the query still passes through the SQL Guard."""
    if table not in get_schema():
        return {"success": False, "error": f"Unknown table '{table}'."}
    return tools.execute_query(f"SELECT * FROM {table} LIMIT {int(limit)}")


# -- suggested questions (schema-derived, no LLM) --------------------------- #
def suggested_questions() -> list[str]:
    """Clickable starter questions generated from the actual schema.

    Deterministic (no Claude Code call) so the Discover page loads instantly;
    clicking one routes it to the Ask AI agent.
    """
    schema = get_schema()
    tables = set(schema.keys())
    permit_cols = {
        c["name"] for c in schema.get("permits", {}).get("columns", [])
    }

    qs: list[str] = []
    if "permit_statuses" in tables:
        qs.append("Count permits by status")
    if "cities" in tables:
        qs.append("Which cities have the most permits?")
    if "permit_types" in tables:
        qs.append("Count permits by permit type")
    if "estimated_cost" in permit_cols and "permit_types" in tables:
        qs.append("What is the average estimated cost by permit type?")
    if "submitted_date" in permit_cols:
        qs.append("How many permits were submitted each month?")
    qs.append("Show the 10 most recent pending permits")
    if "officers" in tables:
        qs.append("Which officer approved the most permits?")
    return qs


# -- connectivity ----------------------------------------------------------- #
@st.cache_data(ttl=30, show_spinner=False)
def db_connected() -> bool:
    try:
        return bool(tools.get_schema().get("success"))
    except Exception:  # noqa: BLE001
        return False
