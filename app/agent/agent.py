"""PermitAgent — turns a question into a validated answer, two ways.

Local (default):
    Streamlit -> PermitAgent -> `claude -p` (Claude Code) -> permit-db MCP
                                             -> QueryService -> SQLGuard -> MySQL
    Claude Code is the LLM, authenticated via the local Claude account
    (no API key). The CLI drives the query_permits MCP tool; this module parses
    its stream-json output for the SQL, rows+timing, and final answer.

Cloud (no CLI, e.g. Streamlit Cloud):
    Streamlit -> PermitAgent -> Anthropic API (ANTHROPIC_API_KEY) generates SQL
                             -> execute_query (MCP tool) -> SQLGuard -> MySQL
    Same guard, same audit — only the SQL *author* changes from the CLI to the
    API. Requires the ``anthropic`` package and a key.

The backend is chosen automatically at construction (see ``PermitAgent``). In
both modes the generated SQL passes through the MCP server's SQL Guard before
it touches the database.
"""
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_ROOT = _PKG.parent.parent               # project root (holds .mcp.json)
_SYSTEM_PROMPT_FILE = _PKG / "system_prompt.md"

_QUERY_TOOL = "mcp__permit-db__query_permits"

# Only query_permits is exposed. The schema is injected into the system prompt
# (below) instead of being fetched via a tool call, which removes an entire
# model round-trip per question. Restricting to query_permits (not the count_*
# domain tools) also guarantees every answer is backed by a visible SELECT.
_ALLOWED_TOOLS = [_QUERY_TOOL]

# sonnet is the fastest option here: in headless Claude Code the per-turn
# harness overhead dominates, and sonnet measured meaningfully faster than
# haiku for this task (~16s vs ~26s). Model choice is NOT the bottleneck —
# per-question process cold-start is (see the persistent-session note in ask()).
DEFAULT_MODEL = "sonnet"
DEFAULT_TIMEOUT_S = 180

# Model id for the Anthropic-API path (cloud / no-CLI mode). Overridable via
# the CLAUDE_MODEL env var / Streamlit secret (e.g. "claude-opus-4-8").
API_MODEL = os.getenv("CLAUDE_MODEL") or "claude-sonnet-5"
# Strip ```sql fences the model may add in API mode.
_FENCE = re.compile(r"```(?:sql)?|```", re.IGNORECASE)


@dataclass
class AgentResult:
    """Everything the UI needs to render one turn."""

    question: str
    sql: str
    ok: bool
    answer: str | None = None
    rows: list = field(default_factory=list)
    execution_time_ms: float | None = None
    error: str | None = None
    mode: str = "cli"


def _schema_text() -> str:
    """Compact rendering of the accessible schema for the system prompt.

    Injecting the schema means the agent never has to spend a turn calling
    ``get_database_schema`` — it can go straight to ``query_permits``. Fetched
    once (fast) and folded into the otherwise-static, cacheable prompt.
    """
    from app.mcp import tools

    resp = tools.get_schema()
    tables = resp.get("tables", {}) if resp.get("success") else {}
    lines = []
    for table, meta in tables.items():
        cols = ", ".join(c["name"] for c in meta["columns"])
        lines.append(f"{table}({cols})")
        for fk in meta["foreign_keys"]:
            lines.append(f"  FK {table}.{fk['column']} -> {fk['references']}")
    return "\n".join(lines)


def _permit_id_hint() -> str:
    """Live application-number range, so the agent's suggestions stay in-bounds.

    Numbers are zero-padded to a fixed width, so lexical MIN/MAX equal the
    numeric first/last id. Injected into the prompt (below) so the model never
    proposes a "corrected" id that is itself out of range.
    """
    from app.mcp import tools

    resp = tools.execute_query(
        "SELECT MIN(application_number) AS lo, MAX(application_number) AS hi, "
        "COUNT(*) AS n FROM permits"
    )
    data = resp.get("data") if resp.get("success") else None
    if not data:
        return ""
    row = data[0]
    return (
        f"Application numbers in the database run from {row['lo']} to "
        f"{row['hi']} ({row['n']} permits total). An id outside this range "
        f"does not exist — do not suggest one."
    )


def _base_rules() -> tuple[str, str]:
    """The static instruction text and rendered few-shot examples."""
    from app.agent.examples import EXAMPLES

    base = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    examples = "\n\n".join(
        f"Q: {e['question']}\nSQL: {e['sql']}" for e in EXAMPLES
    )
    return base, examples


def _cli_system(schema_text: str, id_hint: str = "") -> str:
    """System prompt for the CLI path: the model calls the query_permits tool."""
    base, examples = _base_rules()
    id_line = f"{id_hint}\n\n" if id_hint else ""
    return (
        f"{base}\n\n"
        f"Schema (authoritative — do NOT call any schema tool; use these "
        f"names):\n{schema_text}\n\n"
        f"{id_line}"
        "Answer by calling the `query_permits` tool ONCE with an explicit "
        "SELECT so the SQL is visible; do not use the count_* tools. Always "
        "run this lookup — even for a single permit id, and even if the id "
        "looks malformed: run the SELECT and answer from the actual result "
        "('no matching record' when it returns nothing) rather than refusing "
        "on the format alone. Then give a short, plain-English answer: one or "
        "two sentences. Do NOT restate the SQL and do NOT list or narrate "
        "individual rows — the UI shows the query and the full results table "
        "separately. If the result is a single number, lead with it; "
        "otherwise state what was found and how many rows matched.\n\n"
        "SPECIAL CASE — a lookup of ONE specific permit by application number: "
        "select its status, permit type, submitted_date, "
        "estimated_completion_date, the officer name and department, and LEFT "
        "JOIN permit_documents (received = 0) for pending documents. Then write "
        "a SHORT, friendly summary — two to four sentences of plain prose, NOT "
        "a labelled card and NOT a bulleted list. Weave in the permit type and "
        "current status, then whatever matters most: any pending documents (or "
        "that all documents are received), the assigned officer/department, and "
        "the estimated completion date. End with a one-line next step derived "
        "from the status: Pending -> awaiting initial review; Under Review -> "
        "upload any pending documents to continue; Inspection Scheduled -> "
        "inspection booked, no action needed; Approved -> approved, no further "
        "action; Rejected -> contact the office. The full field-by-field detail "
        "is already visible in the results table, so keep the prose tight.\n\n"
        f"Examples:\n{examples}"
    )


def _api_system(schema_text: str, id_hint: str = "") -> str:
    """System prompt for the API path: the model returns raw SQL (no tools)."""
    base, examples = _base_rules()
    id_line = f"{id_hint}\n\n" if id_hint else ""
    return (
        f"{base}\n\n"
        f"Schema (authoritative — use ONLY these names):\n{schema_text}\n\n"
        f"{id_line}"
        "Output ONLY one MySQL SELECT statement — no prose, no markdown "
        "fences.\n\n"
        f"Examples:\n{examples}"
    )


class PermitAgent:
    """Answers permit questions via Claude.

    Auto-selects a backend at construction:
      * ``cli``  — the ``claude`` CLI is on PATH (local): Claude Code drives the
        permit-db MCP tools. No API key.
      * ``api``  — no CLI but ``ANTHROPIC_API_KEY`` is set (cloud/Streamlit):
        the Anthropic API generates SQL, which still runs through the MCP
        tool + SQL Guard.
      * ``none`` — neither is available: every ``ask`` returns a clear error.
    """

    def __init__(self, model: str = DEFAULT_MODEL,
                 timeout_s: int = DEFAULT_TIMEOUT_S):
        self.model = model
        self.timeout_s = timeout_s
        self._cli = shutil.which("claude")
        # Fetch the schema + id range once and bake them into the (cacheable)
        # system prompt.
        schema = _schema_text()
        id_hint = _permit_id_hint()
        if self._cli:
            self.mode = "cli"
            self._system = _cli_system(schema, id_hint)
        elif os.getenv("ANTHROPIC_API_KEY"):
            self.mode = "api"
            self._system = _api_system(schema, id_hint)
        else:
            self.mode = "none"
            self._system = ""

    # -- public API ------------------------------------------------------- #
    def ask(self, question: str) -> AgentResult:
        question = question.strip()
        if self.mode == "cli":
            return self._ask_cli(question)
        if self.mode == "api":
            return self._ask_api(question)
        return AgentResult(
            question, "", False, mode="none",
            error="No agent available: install the `claude` CLI (local) or set "
            "ANTHROPIC_API_KEY (cloud).",
        )

    # -- CLI path (local) ------------------------------------------------- #
    def _build_command(self, question: str) -> list[str]:
        return [
            self._cli, "-p", question,
            "--output-format", "stream-json",
            "--verbose",                       # required for stream-json in -p
            "--model", self.model,
            "--mcp-config", ".mcp.json",
            "--strict-mcp-config",             # load ONLY permit-db
            "--allowedTools", *_ALLOWED_TOOLS,  # pre-approve (no headless prompt)
            "--append-system-prompt", self._system,
            "--no-session-persistence",
        ]

    def _ask_cli(self, question: str) -> AgentResult:
        try:
            proc = subprocess.run(
                self._build_command(question),
                cwd=str(_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",   # never crash on a stray non-UTF-8 byte
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                question, "", False, mode="cli",
                error=f"Claude Code timed out after {self.timeout_s}s.",
            )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:500]
            return AgentResult(
                question, "", False, mode="cli",
                error=f"claude exited {proc.returncode}: {detail}",
            )
        return self._parse(question, proc.stdout)

    # -- API path (cloud) ------------------------------------------------- #
    def _ask_api(self, question: str) -> AgentResult:
        from app.mcp.tools import execute_query

        try:
            import anthropic
        except ImportError:
            return AgentResult(
                question, "", False, mode="api",
                error="The `anthropic` package is not installed.",
            )
        client = anthropic.Anthropic()

        # 1. Question -> SQL
        try:
            msg = client.messages.create(
                model=API_MODEL, max_tokens=500, system=self._system,
                messages=[{"role": "user",
                           "content": f"Question: {question}\nSQL:"}],
            )
            sql = _FENCE.sub(
                "", "".join(b.text for b in msg.content if b.type == "text")
            ).strip()
        except Exception as exc:  # noqa: BLE001
            return AgentResult(question, "", False, mode="api",
                               error=f"SQL generation failed: {exc}")

        # 2. Validated execution via the MCP tool (guard + audit + timing)
        resp = execute_query(sql)
        if not resp.get("success"):
            return AgentResult(
                question, sql, False, mode="api",
                error=f"Query rejected: {resp.get('error')}",
            )
        rows = resp["data"]
        elapsed = resp["execution_time_ms"]
        sql = resp.get("generated_sql", sql)

        # 3. Rows -> plain-English answer (best-effort)
        try:
            ans = client.messages.create(
                model=API_MODEL, max_tokens=200,
                system="Answer in one or two plain, factual sentences using "
                "the results. Do not restate the SQL. If the result is a "
                "single number, lead with it.",
                messages=[{"role": "user", "content": (
                    f"Question: {question}\nSQL: {sql}\n"
                    f"Results (JSON, up to 20 rows): "
                    f"{json.dumps(rows[:20], default=str)}\n"
                    f"Total rows: {len(rows)}"
                )}],
            )
            answer = "".join(
                b.text for b in ans.content if b.type == "text"
            ).strip()
        except Exception:  # noqa: BLE001 — phrasing is best-effort
            answer = f"Query returned {len(rows)} row(s)."

        return AgentResult(question, sql, True, answer=answer, rows=rows,
                           execution_time_ms=elapsed, mode="api")

    # -- parsing ---------------------------------------------------------- #
    def _parse(self, question: str, stdout: str) -> AgentResult:
        sql = ""
        rows: list = []
        elapsed = None
        answer = None
        query_ids: set[str] = set()

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = evt.get("type")

            if etype == "assistant":
                for block in evt.get("message", {}).get("content", []):
                    if (block.get("type") == "tool_use"
                            and block.get("name") == _QUERY_TOOL):
                        sql = block.get("input", {}).get("sql", sql)
                        if block.get("id"):
                            query_ids.add(block["id"])

            elif etype == "user":
                for block in evt.get("message", {}).get("content", []):
                    if (block.get("type") == "tool_result"
                            and block.get("tool_use_id") in query_ids):
                        parsed = _parse_tool_content(block.get("content"))
                        if parsed and parsed.get("success"):
                            rows = parsed.get("data", rows)
                            elapsed = parsed.get("execution_time_ms", elapsed)
                            sql = parsed.get("generated_sql", sql)
                        elif parsed and parsed.get("error"):
                            return AgentResult(
                                question, sql, False,
                                error=f"Query rejected: {parsed['error']}",
                            )

            elif etype == "result":
                if evt.get("is_error") or evt.get("subtype") != "success":
                    return AgentResult(
                        question, sql, False,
                        error=evt.get("result") or "Claude Code returned an "
                        "error.",
                    )
                answer = evt.get("result", answer)

        if answer is None and not rows:
            return AgentResult(question, sql, False,
                               error="Claude Code produced no result.")

        return AgentResult(question, sql, True, answer=answer, rows=rows,
                           execution_time_ms=elapsed)


def _parse_tool_content(content) -> dict | None:
    """A tool_result's content -> the MCP response dict, or None.

    permit-db returns its JSON as a string; other tools may use a list of text
    blocks. Handle both.
    """
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    else:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
