"""Permit Intelligence Platform — Streamlit UI.

Run from the project root:

    streamlit run ui/app.py

Two clearly separated layers:

* **Ask AI** — natural-language questions go to the Claude Code agent
  (``PermitAgent`` -> ``claude -p`` -> permit-db MCP -> MySQL). ~10-20s each.
* **Discover Data / Analytics** — deterministic, cached reads via
  ``ui/data.py`` (the parameterized MCP tool layer). Instant and free; these
  never invoke Claude Code.

The UI never touches the database or repository directly.
"""
import csv
import io
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Bridge Streamlit secrets -> environment BEFORE importing the backend, so the
# database layer (which reads DB_* / DATABASE_URL from os.environ) and the API
# agent (ANTHROPIC_API_KEY) pick up config when deployed to Streamlit Cloud.
# Local runs have no secrets file, which is fine — the .env is used instead.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:  # noqa: BLE001 — no secrets.toml locally is expected
    pass

import data  # noqa: E402  (ui/data.py — deterministic reads)
from app.agent.agent import PermitAgent  # noqa: E402

st.set_page_config(
    page_title="Permit Intelligence Platform", page_icon="🏛️", layout="wide"
)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_agent() -> PermitAgent:
    return PermitAgent()


def rows_to_csv(rows: list) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def run_question(question: str) -> None:
    """Run a question through the Claude Code agent and record it.

    Successful answers are cached per-session by question text, so re-asking
    the same thing (e.g. clicking a suggestion twice) is instant instead of
    spending another ~16s Claude Code run.
    """
    cache = st.session_state.setdefault("answer_cache", {})
    key = question.strip().lower()
    if key in cache:
        result = cache[key]
    else:
        with st.spinner("Asking Claude Code… (this can take ~10–20s)"):
            result = get_agent().ask(question)
        if result.ok:
            cache[key] = result
    st.session_state.current = result
    st.session_state.history.insert(0, result)


def kpi_cards() -> None:
    k = data.kpis()
    by = k["by_status"]
    cols = st.columns(4)
    cards = [
        ("Total Permits", k["total"]),
        ("Pending", by.get("Pending", 0)),
        ("Approved", by.get("Approved", 0)),
        ("Rejected", by.get("Rejected", 0)),
    ]
    for col, (label, value) in zip(cols, cards):
        with col:
            with st.container(border=True):
                st.metric(label, f"{value:,}")


def goto_ask(question: str) -> None:
    """Fill the Ask AI box with a question, flag it to run, and switch tabs.

    Used as a button ``on_click`` callback: callbacks run at the start of the
    next rerun, *before* the ``nav`` radio and the ``q_input`` text box are
    instantiated, so writing to their session_state keys here is allowed
    (writing them after the widgets exist raises StreamlitAPIException).
    """
    st.session_state.q_input = question   # shows the text in the box
    st.session_state.autorun = True       # trigger a run on arrival
    st.session_state.nav = "💬 Ask AI"


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
st.session_state.setdefault("history", [])
st.session_state.setdefault("current", None)


# --------------------------------------------------------------------------- #
# Sidebar — brand, nav, status
# --------------------------------------------------------------------------- #
NAV = ["💬 Ask AI", "🧭 Discover Data", "📊 Analytics", "🕘 History"]

with st.sidebar:
    st.title("🏛️ Permit Intelligence")
    st.radio("Navigate", NAV, key="nav", label_visibility="collapsed")

    st.divider()
    st.caption("**System status**")
    db_ok = data.db_connected()
    agent_mode = get_agent().mode
    agent_label = {
        "cli": "Agent: Claude Code (CLI)",
        "api": "Agent: Anthropic API",
        "none": "Agent: not configured",
    }[agent_mode]
    mcp_ok = (_ROOT / ".mcp.json").exists()
    st.write(f"{'✅' if db_ok else '❌'} Database (MySQL)")
    st.write(f"{'✅' if mcp_ok else '❌'} MCP server")
    st.write(f"{'✅' if agent_mode != 'none' else '❌'} {agent_label}")

    st.divider()
    dark = st.toggle("🌙 Dark mode", value=False)
    if st.button("🗑️ Clear history", width="stretch"):
        st.session_state.history = []
        st.session_state.current = None
        st.rerun()

if dark:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0e1117; color: #e6e6e6; }
        [data-testid="stSidebar"] { background-color: #161a23; }
        </style>
        """,
        unsafe_allow_html=True,
    )

nav = st.session_state.nav


# --------------------------------------------------------------------------- #
# Page: Ask AI
# --------------------------------------------------------------------------- #
def page_ask_ai() -> None:
    st.title("💬 Ask AI")
    kpi_cards()
    st.write("")

    with st.form("ask", clear_on_submit=False):
        question = st.text_input(
            "Ask a permit question",
            key="q_input",
            placeholder="How many electrical permits are pending?",
        )
        submitted = st.form_submit_button("Ask AI", type="primary")

    # Auto-run a question routed from a suggestion, else run on submit.
    if st.session_state.pop("autorun", False):
        if question.strip():
            run_question(question)
    elif submitted and question.strip():
        run_question(question)

    result = st.session_state.current
    if result is None:
        return

    st.divider()
    if not result.ok:
        st.error(result.error or "Query failed.")
        if result.sql:
            st.subheader("Generated SQL")
            st.code(result.sql, language="sql")
        return

    st.subheader("AI Answer")
    st.success(result.answer)

    st.subheader("Generated SQL")
    st.code(result.sql or "(no SQL)", language="sql")

    st.subheader("Results")
    if result.rows:
        st.dataframe(result.rows, width="stretch")
        c1, c2 = st.columns([1, 3])
        with c1:
            st.metric("Execution Time", f"{result.execution_time_ms} ms")
        with c2:
            st.download_button(
                "⬇️ Export CSV",
                data=rows_to_csv(result.rows),
                file_name="permit_results.csv",
                mime="text/csv",
            )
    else:
        st.info("No rows returned.")


# --------------------------------------------------------------------------- #
# Page: Discover Data  ("Discover Your Data")
# --------------------------------------------------------------------------- #
def page_discover() -> None:
    st.title("🧭 Discover Your Data")
    st.caption(
        "Browse the tables, inspect their columns, preview sample records, and "
        "click a suggested question to explore with AI."
    )

    schema = data.get_schema()
    if not schema:
        st.error("Could not load the schema. Is the database reachable?")
        return

    left, right = st.columns([2, 1])

    # -- Database Explorer (schema + preview) ------------------------------ #
    with left:
        st.subheader("Database Explorer")
        tables = list(schema.keys())
        table = st.selectbox("Table", tables)
        meta = schema[table]

        with st.container(border=True):
            st.markdown(f"**Columns — `{table}`**")
            col_rows = [
                {"column": c["name"], "type": c["type"]}
                for c in meta["columns"]
            ]
            st.dataframe(col_rows, width="stretch", hide_index=True)
            if meta["foreign_keys"]:
                fks = ", ".join(
                    f"{fk['column']} → {fk['references']}"
                    for fk in meta["foreign_keys"]
                )
                st.caption(f"🔗 Foreign keys: {fks}")

        st.markdown("**Sample records**")
        preview = data.preview_table(table, limit=5)
        if preview.get("success") and preview.get("data"):
            st.dataframe(preview["data"], width="stretch")
        elif preview.get("success"):
            st.info("Table is empty.")
        else:
            st.warning(preview.get("error", "Could not preview this table."))

    # -- AI Suggestions ---------------------------------------------------- #
    with right:
        st.subheader("💡 Suggested questions")
        st.caption("Generated from the schema. Click to ask.")
        for i, q in enumerate(data.suggested_questions()):
            st.button(
                q, key=f"sugg-{i}", width="stretch",
                on_click=goto_ask, args=(q,),
            )


# --------------------------------------------------------------------------- #
# Page: Analytics
# --------------------------------------------------------------------------- #
def _bar(rows: list, label_key: str, value_key: str, top: int | None = None):
    if not rows:
        st.info("No data.")
        return
    df = pd.DataFrame(rows).rename(
        columns={label_key: "label", value_key: "count"}
    )
    df = df.sort_values("count", ascending=False)
    if top:
        df = df.head(top)
    st.bar_chart(df.set_index("label")["count"])


def page_analytics() -> None:
    st.title("📊 Analytics")
    kpi_cards()
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Permits by Status")
        _bar(data.count_by_status(), "status", "count")
    with c2:
        st.subheader("Permits by Type")
        _bar(data.count_by_type(), "permit_type", "count")

    st.subheader("Top 10 Cities")
    _bar(data.count_by_city(), "city", "count", top=10)

    st.subheader("Monthly Submissions")
    trend = data.monthly_trend()
    if trend:
        df = pd.DataFrame(trend).set_index("month")["permits"]
        st.line_chart(df)
    else:
        st.info("No trend data.")


# --------------------------------------------------------------------------- #
# Page: History
# --------------------------------------------------------------------------- #
def page_history() -> None:
    st.title("🕘 Query History")
    if not st.session_state.history:
        st.info("No questions asked yet. Head to Ask AI to start.")
        return
    for h in st.session_state.history:
        status = "✅" if h.ok else "❌"
        meta = f"{h.execution_time_ms} ms" if h.ok else "error"
        with st.expander(f"{status}  {h.question or '(query)'}  —  {meta}"):
            st.code(h.sql or "(no SQL generated)", language="sql")
            if h.ok:
                st.write(h.answer)
                st.caption(f"{len(h.rows)} row(s)")
            else:
                st.error(h.error or "")


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
if nav == "💬 Ask AI":
    page_ask_ai()
elif nav == "🧭 Discover Data":
    page_discover()
elif nav == "📊 Analytics":
    page_analytics()
elif nav == "🕘 History":
    page_history()
