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
import html as _html
import io
import os
import re
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
    page_title="Permit Intelligence Platform",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------- #
# Optional one-time seeding for a fresh hosted deployment (SEED_ON_START=true).
#
# Runs at most once per process (st.cache_resource) and only populates an EMPTY
# database — an already-seeded DB is left untouched, so it is safe to leave on.
# Best-effort: any failure (e.g. a read-only connection) is surfaced as a
# warning and the app keeps running.
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def _seed_on_start_once() -> str:
    if os.getenv("SEED_ON_START", "").strip().lower() not in (
        "1", "true", "yes", "on"
    ):
        return "disabled"
    try:
        from scripts.seed_data import seed_if_empty

        with st.spinner("Preparing sample data (first run only)…"):
            return "seeded" if seed_if_empty() else "already-populated"
    except Exception as exc:  # noqa: BLE001 — never block the app on seeding
        st.warning(f"SEED_ON_START skipped: {exc}")
        return "error"


_seed_on_start_once()


# --------------------------------------------------------------------------- #
# Theme — a single CSS-variable stylesheet, re-applied every run.
#
# The old toggle only injected a background override when dark was on, leaving
# text/inputs/cards light — so it looked broken. Here BOTH modes get the full
# stylesheet: only the variable values swap, and every surface reads from them.
# --------------------------------------------------------------------------- #
LIGHT = {
    "bg": "#eef1f7", "surface": "#ffffff", "surface2": "#f4f6fb",
    "text": "#1a2233", "muted": "#64748b", "border": "#e3e8f0",
    "primary": "#4f46e5", "primary2": "#7c3aed", "ring": "rgba(79,70,229,.35)",
    "shadow": "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)",
    "shadow_lg": "0 10px 30px rgba(16,24,40,.12)",
    "grad": "linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#2563eb 100%)",
}
DARK = {
    "bg": "#0a0f1c", "surface": "#141b2d", "surface2": "#1b2437",
    "text": "#e6ebf5", "muted": "#93a1b8", "border": "#26304a",
    "primary": "#818cf8", "primary2": "#a78bfa", "ring": "rgba(129,140,248,.40)",
    "shadow": "0 1px 2px rgba(0,0,0,.4), 0 2px 8px rgba(0,0,0,.35)",
    "shadow_lg": "0 12px 34px rgba(0,0,0,.55)",
    "grad": "linear-gradient(135deg,#4f46e5 0%,#7c3aed 55%,#2563eb 100%)",
}

STATUS_COLORS = {
    "Approved": "#16a34a", "Pending": "#d97706", "Under Review": "#2563eb",
    "Inspection Scheduled": "#7c3aed", "Rejected": "#dc2626",
}


def apply_theme(dark: bool) -> None:
    t = DARK if dark else LIGHT
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {{
            --bg:{t['bg']}; --surface:{t['surface']}; --surface2:{t['surface2']};
            --text:{t['text']}; --muted:{t['muted']}; --border:{t['border']};
            --primary:{t['primary']}; --primary2:{t['primary2']}; --ring:{t['ring']};
            --shadow:{t['shadow']}; --shadow-lg:{t['shadow_lg']}; --grad:{t['grad']};
        }}

        html, body, .stApp, [class*="css"] {{
            font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        }}
        .stApp {{ background:var(--bg); color:var(--text); }}
        [data-testid="stAppViewContainer"] {{ background:var(--bg); }}
        [data-testid="stHeader"] {{ background:transparent; }}
        .block-container {{ padding-top:2.2rem; max-width:1220px; }}

        h1,h2,h3,h4,h5,h6, p, span, label, li, div {{ color:var(--text); }}
        [data-testid="stCaptionContainer"], .stCaption, small {{ color:var(--muted) !important; }}

        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {{
            background:var(--surface); border-right:1px solid var(--border);
        }}
        [data-testid="stSidebar"] .block-container {{ padding-top:1.4rem; }}

        /* ---- Sidebar nav radio -> menu items ---- */
        [data-testid="stSidebar"] [role="radiogroup"] {{ gap:.35rem; }}
        [data-testid="stSidebar"] [role="radiogroup"] label {{
            display:flex; align-items:center; padding:.55rem .8rem; border-radius:10px;
            border:1px solid transparent; cursor:pointer; transition:all .15s ease;
            font-weight:500;
        }}
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
            background:var(--surface2); border-color:var(--border);
        }}
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
            background:var(--grad); border-color:transparent; box-shadow:var(--shadow);
        }}
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) * {{
            color:#fff !important;
        }}
        [data-testid="stSidebar"] [role="radiogroup"] [data-testid="stMarkdownContainer"] p {{
            margin:0; font-size:.95rem;
        }}

        /* ---- Buttons ---- */
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
            border-radius:10px; border:1px solid var(--border); background:var(--surface);
            color:var(--text); font-weight:600; padding:.5rem .95rem;
            transition:all .16s ease; box-shadow:var(--shadow);
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            transform:translateY(-1px); border-color:var(--primary);
            box-shadow:var(--shadow-lg);
        }}
        .stFormSubmitButton > button, .stButton > button[kind="primary"] {{
            background:var(--grad); color:#fff; border:none;
        }}
        .stFormSubmitButton > button:hover {{
            transform:translateY(-1px); box-shadow:var(--shadow-lg); filter:brightness(1.05);
        }}

        /* ---- Inputs ---- */
        [data-baseweb="input"], [data-baseweb="select"] > div, .stTextInput input,
        [data-baseweb="base-input"] {{
            background:var(--surface) !important; border-radius:10px !important;
            border-color:var(--border) !important; color:var(--text) !important;
        }}
        .stTextInput input {{ padding:.6rem .8rem; }}
        .stTextInput input:focus {{ box-shadow:0 0 0 3px var(--ring); }}
        [data-testid="stForm"] {{
            background:var(--surface); border:1px solid var(--border);
            border-radius:16px; padding:1.1rem; box-shadow:var(--shadow);
        }}

        /* ---- Bordered containers / cards ---- */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background:var(--surface); border-radius:16px !important;
            border:1px solid var(--border) !important; box-shadow:var(--shadow);
        }}

        /* ---- Metrics ---- */
        [data-testid="stMetric"] {{
            background:var(--surface); border:1px solid var(--border);
            border-radius:14px; padding:1rem 1.1rem; box-shadow:var(--shadow);
        }}
        [data-testid="stMetricValue"] {{ color:var(--text); font-weight:700; }}
        [data-testid="stMetricLabel"] {{ color:var(--muted); }}

        /* ---- DataFrame ---- */
        [data-testid="stDataFrame"] {{
            border:1px solid var(--border); border-radius:14px; overflow:hidden;
            box-shadow:var(--shadow);
        }}

        /* ---- Code blocks ---- */
        [data-testid="stCode"], pre {{
            border-radius:12px !important; border:1px solid var(--border);
        }}

        /* ---- Expander ---- */
        [data-testid="stExpander"] {{
            border:1px solid var(--border) !important; border-radius:12px !important;
            background:var(--surface); box-shadow:var(--shadow);
        }}

        /* ---- Alerts ---- */
        [data-testid="stAlert"] {{ border-radius:12px; }}

        /* ---- Custom hero + cards ---- */
        .hero {{
            background:var(--grad); border-radius:20px; padding:1.6rem 1.9rem;
            color:#fff; box-shadow:var(--shadow-lg); margin-bottom:1.4rem;
            position:relative; overflow:hidden;
        }}
        .hero::after {{
            content:""; position:absolute; right:-40px; top:-40px; width:180px;
            height:180px; background:rgba(255,255,255,.12); border-radius:50%;
        }}
        .hero h1 {{ color:#fff !important; margin:0; font-size:1.7rem; font-weight:800;
            letter-spacing:-.02em; }}
        .hero p {{ color:rgba(255,255,255,.9) !important; margin:.35rem 0 0;
            font-size:.98rem; }}

        .kpi-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1rem;
            margin-bottom:.4rem; }}
        .kpi {{
            background:var(--surface); border:1px solid var(--border); border-radius:16px;
            padding:1.1rem 1.2rem; box-shadow:var(--shadow); transition:all .18s ease;
            position:relative; overflow:hidden;
        }}
        .kpi:hover {{ transform:translateY(-3px); box-shadow:var(--shadow-lg); }}
        .kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
            background:var(--accent); }}
        .kpi .lab {{ color:var(--muted); font-size:.8rem; font-weight:600;
            text-transform:uppercase; letter-spacing:.04em; }}
        .kpi .val {{ color:var(--text); font-size:1.9rem; font-weight:800;
            line-height:1.1; margin-top:.25rem; }}
        .kpi .ico {{ font-size:1.1rem; }}

        .answer-card {{
            background:var(--surface); border:1px solid var(--border);
            border-left:4px solid var(--primary); border-radius:14px;
            padding:1.15rem 1.3rem; box-shadow:var(--shadow); line-height:1.65;
        }}
        .answer-card p, .answer-card li {{ color:var(--text); }}

        .badge {{ display:inline-block; padding:.2rem .7rem; border-radius:999px;
            font-size:.8rem; font-weight:700; color:#fff; }}

        .sec-title {{ font-size:1.05rem; font-weight:700; margin:1.3rem 0 .5rem;
            display:flex; align-items:center; gap:.5rem; }}

        @media (max-width:900px) {{ .kpi-row {{ grid-template-columns:repeat(2,1fr); }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def get_agent() -> PermitAgent:
    return PermitAgent()


def answer_html(text: str) -> str:
    """Render the agent's markdown answer as safe HTML for the card.

    Streamlit does not parse markdown inside a raw HTML block, so ``**bold**``
    and newlines would show literally. We escape first (no injection), then
    convert the small markdown subset the agent emits — bold, bullet lines, and
    line breaks — into HTML by hand.
    """
    if not text:
        return ""
    s = _html.escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)      # **bold**
    s = re.sub(r"(?m)^\s*[-*]\s+", "&nbsp;&nbsp;• ", s)          # - bullet
    return s.replace("\n", "<br>")


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


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def kpi_cards() -> None:
    k = data.kpis()
    by = k["by_status"]
    cards = [
        ("📋", "Total Permits", k["total"], "var(--primary)"),
        ("⏳", "Pending", by.get("Pending", 0), STATUS_COLORS["Pending"]),
        ("✅", "Approved", by.get("Approved", 0), STATUS_COLORS["Approved"]),
        ("🔍", "Under Review", by.get("Under Review", 0),
         STATUS_COLORS["Under Review"]),
    ]
    html = '<div class="kpi-row">'
    for ico, label, value, accent in cards:
        html += (
            f'<div class="kpi" style="--accent:{accent}">'
            f'<div class="lab"><span class="ico">{ico}</span> {label}</div>'
            f'<div class="val">{value:,}</div></div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def goto_ask(question: str) -> None:
    """Fill the Ask AI box with a question, flag it to run, and switch tabs."""
    st.session_state.q_input = question
    st.session_state.autorun = True
    st.session_state.nav = "💬 Ask AI"


def render_chips(caption: str, items: list, per_row: int = 3) -> None:
    """Render a labelled group of example chips, `per_row` per row.

    Each item is ``(label, question)`` — the short label shows on the chip, the
    full question is what gets sent to the agent on click.
    """
    st.markdown(
        f'<div style="color:var(--muted);font-size:.82rem;font-weight:600;'
        f'margin:.7rem 0 .3rem;">{caption}</div>', unsafe_allow_html=True)
    for start in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, (label, question) in zip(cols, items[start:start + per_row]):
            with col:
                st.button(label, key=f"chip-{label}", width="stretch",
                          on_click=goto_ask, args=(question,))


# Quick concrete demos.
QUICK_CHIPS = [
    ("📋 Status of PERM-2026-000052",
     "What's the status of permit PERM-2026-000052?"),
    ("⏳ How many are pending?", "How many permits are pending?"),
    ("🏙️ Cities with most permits", "Which cities have the most permits?"),
]


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #
st.session_state.setdefault("history", [])
st.session_state.setdefault("current", None)
st.session_state.setdefault("dark", False)


# --------------------------------------------------------------------------- #
# Sidebar — brand, nav, status
# --------------------------------------------------------------------------- #
NAV = ["💬 Ask AI", "🧭 Discover Data", "📊 Analytics", "🕘 History"]

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.25rem;font-weight:800;letter-spacing:-.02em;'
        'margin-bottom:.2rem;">🏛️ Permit Intelligence</div>'
        '<div style="color:var(--muted);font-size:.82rem;margin-bottom:1rem;">'
        'AI-powered permit lookup</div>',
        unsafe_allow_html=True,
    )
    st.radio("Navigate", NAV, key="nav", label_visibility="collapsed")

    st.divider()
    st.markdown(
        '<div style="color:var(--muted);font-size:.78rem;font-weight:700;'
        'text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem;">'
        'System status</div>',
        unsafe_allow_html=True,
    )
    db_ok = data.db_connected()
    agent_mode = get_agent().mode
    agent_label = {
        "cli": "Claude Code (CLI)",
        "api": "Anthropic API",
        "none": "not configured",
    }[agent_mode]
    mcp_ok = (_ROOT / ".mcp.json").exists()

    def _status_line(ok: bool, text: str) -> str:
        dot = "#16a34a" if ok else "#dc2626"
        return (
            f'<div style="display:flex;align-items:center;gap:.5rem;'
            f'padding:.15rem 0;font-size:.88rem;">'
            f'<span style="width:8px;height:8px;border-radius:50%;'
            f'background:{dot};box-shadow:0 0 0 3px {dot}22;"></span>{text}</div>'
        )

    st.markdown(
        _status_line(db_ok, "Database (MySQL)")
        + _status_line(mcp_ok, "MCP server")
        + _status_line(agent_mode != "none", f"Agent: {agent_label}"),
        unsafe_allow_html=True,
    )

    st.divider()
    st.toggle("🌙 Dark mode", key="dark")
    if st.button("🗑️ Clear history", width="stretch"):
        st.session_state.history = []
        st.session_state.current = None
        st.rerun()

# Apply the theme AFTER the toggle is read, so switching re-styles everything.
apply_theme(st.session_state.dark)

nav = st.session_state.nav


# --------------------------------------------------------------------------- #
# Page: Ask AI
# --------------------------------------------------------------------------- #
def page_ask_ai() -> None:
    hero("💬 Ask AI", "Ask any question about permits in plain English — "
         "the agent writes the SQL, runs it, and explains the result.")
    kpi_cards()
    st.write("")

    with st.form("ask", clear_on_submit=False):
        question = st.text_input(
            "Ask a permit question",
            key="q_input",
            placeholder="e.g. What's the status of permit PERM-2026-000052?",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("✨ Ask AI", type="primary")

    # Quick-start chips
    render_chips("Try a quick query", QUICK_CHIPS, per_row=3)

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
            st.markdown('<div class="sec-title">🧾 Generated SQL</div>',
                        unsafe_allow_html=True)
            st.code(result.sql, language="sql")
        return

    st.markdown('<div class="sec-title">🤖 AI Answer</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="answer-card">{answer_html(result.answer)}</div>',
                unsafe_allow_html=True)

    st.markdown('<div class="sec-title">🧾 Generated SQL</div>',
                unsafe_allow_html=True)
    st.code(result.sql or "(no SQL)", language="sql")

    st.markdown('<div class="sec-title">📊 Results</div>',
                unsafe_allow_html=True)
    if result.rows:
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(result.rows):,}")
        c2.metric("Execution Time", f"{result.execution_time_ms} ms")
        with c3:
            st.write("")
            st.download_button(
                "⬇️ Export CSV",
                data=rows_to_csv(result.rows),
                file_name="permit_results.csv",
                mime="text/csv",
                width="stretch",
            )
        st.dataframe(result.rows, width="stretch")
    else:
        st.info("No rows returned.")


# --------------------------------------------------------------------------- #
# Page: Discover Data  ("Discover Your Data")
# --------------------------------------------------------------------------- #
def page_discover() -> None:
    hero("🧭 Discover Your Data",
         "Browse the tables, inspect their columns, preview records, and click "
         "a suggested question to explore with AI.")

    schema = data.get_schema()
    if not schema:
        st.error("Could not load the schema. Is the database reachable?")
        return

    left, right = st.columns([2, 1])

    with left:
        st.markdown('<div class="sec-title">🗂️ Database Explorer</div>',
                    unsafe_allow_html=True)
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

    with right:
        st.markdown('<div class="sec-title">💡 Suggested questions</div>',
                    unsafe_allow_html=True)
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
    st.bar_chart(df.set_index("label")["count"], color="#4f46e5")


def page_analytics() -> None:
    hero("📊 Analytics", "Live aggregates across the permit database.")
    kpi_cards()
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**Permits by Status**")
            _bar(data.count_by_status(), "status", "count")
    with c2:
        with st.container(border=True):
            st.markdown("**Permits by Type**")
            _bar(data.count_by_type(), "permit_type", "count")

    with st.container(border=True):
        st.markdown("**Top 10 Cities**")
        _bar(data.count_by_city(), "city", "count", top=10)

    with st.container(border=True):
        st.markdown("**Monthly Submissions**")
        trend = data.monthly_trend()
        if trend:
            df = pd.DataFrame(trend).set_index("month")["permits"]
            st.line_chart(df, color="#7c3aed")
        else:
            st.info("No trend data.")


# --------------------------------------------------------------------------- #
# Page: History
# --------------------------------------------------------------------------- #
def page_history() -> None:
    hero("🕘 Query History", "Every question you've asked this session.")
    if not st.session_state.history:
        st.info("No questions asked yet. Head to Ask AI to start.")
        return
    for h in st.session_state.history:
        status = "✅" if h.ok else "❌"
        meta = f"{h.execution_time_ms} ms" if h.ok else "error"
        with st.expander(f"{status}  {h.question or '(query)'}  —  {meta}"):
            st.code(h.sql or "(no SQL generated)", language="sql")
            if h.ok:
                st.markdown(
                    f'<div class="answer-card">{answer_html(h.answer)}</div>',
                    unsafe_allow_html=True)
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
