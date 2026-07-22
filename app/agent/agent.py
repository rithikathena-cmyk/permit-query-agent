"""PermitAgent — bridges the app to the Claude Code agent.

Architecture (the lab's target):

    User -> Streamlit -> PermitAgent -> `claude -p` (Claude Code)
                                            -> permit-db MCP server
                                                -> QueryService -> SQLGuard
                                                    -> Repository -> MySQL

Claude Code IS the LLM/agent. It authenticates through the local Claude account
(``apiKeySource: none`` — no ``ANTHROPIC_API_KEY``, no ``anthropic`` package).
This module only spawns the ``claude`` CLI in headless print mode, constrains it
to the two read-only permit-db MCP tools, and parses its ``stream-json`` output
to recover:

  * the SELECT Claude ran        (from the ``query_permits`` tool_use input)
  * the result rows + timing     (from the tool_result the MCP server returned)
  * the plain-English answer      (from Claude's final ``result`` message)

The heavy lifting (schema lookup, SQL generation, phrasing) all happens inside
Claude Code. The SQL still passes through the MCP server's SQL Guard before it
touches the database, exactly as it does for a human-driven MCP session.
"""
import json
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
    mode: str = "claude-code"


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


def _system_prompt(schema_text: str) -> str:
    """The headless agent's instructions: base rules + schema + examples."""
    from app.agent.examples import EXAMPLES

    base = _SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")
    examples = "\n\n".join(
        f"Q: {e['question']}\nSQL: {e['sql']}" for e in EXAMPLES
    )
    return (
        f"{base}\n\n"
        f"Schema (authoritative — do NOT call any schema tool; use these "
        f"names):\n{schema_text}\n\n"
        "Answer by calling the `query_permits` tool ONCE with an explicit "
        "SELECT so the SQL is visible; do not use the count_* tools. Then give "
        "a short, plain-English answer.\n\n"
        f"Examples:\n{examples}"
    )


class PermitAgent:
    """Runs the Claude Code CLI headlessly and parses its stream."""

    mode = "claude-code"

    def __init__(self, model: str = DEFAULT_MODEL,
                 timeout_s: int = DEFAULT_TIMEOUT_S):
        self.model = model
        self.timeout_s = timeout_s
        # Fetch the schema once and bake it into the (cacheable) system prompt
        # so no per-question schema round-trip is needed.
        self._system = _system_prompt(_schema_text())

    # -- command ---------------------------------------------------------- #
    def _build_command(self, question: str) -> list[str] | None:
        exe = shutil.which("claude")
        if exe is None:
            return None
        return [
            exe, "-p", question,
            "--output-format", "stream-json",
            "--verbose",                       # required for stream-json in -p
            "--model", self.model,
            "--mcp-config", ".mcp.json",
            "--strict-mcp-config",             # load ONLY permit-db
            "--allowedTools", *_ALLOWED_TOOLS,  # pre-approve (no headless prompt)
            "--append-system-prompt", self._system,
            "--no-session-persistence",
        ]

    # -- public API ------------------------------------------------------- #
    def ask(self, question: str) -> AgentResult:
        question = question.strip()
        cmd = self._build_command(question)
        if cmd is None:
            return AgentResult(question, "", False,
                               error="`claude` CLI not found on PATH.")
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return AgentResult(
                question, "", False,
                error=f"Claude Code timed out after {self.timeout_s}s.",
            )

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:500]
            return AgentResult(
                question, "", False,
                error=f"claude exited {proc.returncode}: {detail}",
            )

        return self._parse(question, proc.stdout)

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
