import re

from app.security.constants import (
    ALLOWED_TABLES,
    FORBIDDEN_KEYWORDS,
    MAX_LIMIT,
)

from app.security.exceptions import SQLValidationError

# Keywords that end a FROM clause — used to bound comma-separated table lists so
# a comma in the SELECT list is never mistaken for an extra table.
_CLAUSE_BOUNDARY = re.compile(
    r"\b(WHERE|GROUP|HAVING|ORDER|LIMIT|UNION|JOIN|INNER|LEFT|RIGHT|OUTER|"
    r"CROSS|FULL|NATURAL|ON|USING)\b",
    re.IGNORECASE,
)


def _split_top_level_commas(segment: str) -> list[str]:
    """Split on commas that are NOT inside parentheses (subqueries/functions)."""
    parts, depth, cur = [], 0, ""
    for ch in segment:
        if ch == "(":
            depth += 1
            cur += ch
        elif ch == ")":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _from_regions(sql: str) -> list[str]:
    """Return the text of each FROM clause (up to the next clause keyword).

    ``re.finditer`` over every ``FROM`` also reaches into subqueries, so nested
    ``FROM`` targets are covered too.
    """
    regions = []
    for m in re.finditer(r"\bFROM\b", sql, re.IGNORECASE):
        rest = sql[m.end():]
        boundary = _CLAUSE_BOUNDARY.search(rest)
        region = rest[: boundary.start()] if boundary else rest
        # Cut at the first paren that closes a level we did not open, so a
        # `FROM (subquery)` region stops at the subquery's closing paren.
        depth, cut = 0, len(region)
        for i, ch in enumerate(region):
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    cut = i
                    break
                depth -= 1
        regions.append(region[:cut])
    return regions


def _extract_table_refs(sql: str) -> list[str]:
    """Every table referenced by the query — including comma joins.

    Backticks are neutralised first so a quoted identifier can't hide a
    cross-schema reference (`` `mysql`.`user` `` -> ``mysql . user``).
    """
    norm = sql.replace("`", " ")
    refs: list[str] = []

    # Each JOIN introduces exactly one table (covers subquery JOINs too).
    for m in re.finditer(r"\bJOIN\s+([A-Za-z0-9_.]+)", norm, re.IGNORECASE):
        refs.append(m.group(1))

    # FROM clauses -> split on top-level commas -> first identifier of each item
    # (drops any alias). Sub-select items (starting with "(") are skipped; their
    # own inner FROM is matched separately.
    for region in _from_regions(norm):
        for part in _split_top_level_commas(region):
            stripped = part.strip()
            if not stripped or stripped.startswith("("):
                continue
            ident = re.match(r"([A-Za-z0-9_.]+)", stripped)
            if ident:
                refs.append(ident.group(1))
    return refs


class SQLGuard:
    """
    Read-only SQL validator. This is defense-in-depth: the app also connects as
    a least-privilege user that can only SELECT within the permit database, so a
    parsing gap here still cannot read other schemas or write.
    """

    @staticmethod
    def validate(sql: str) -> str:

        if not sql:
            raise SQLValidationError("SQL cannot be empty.")

        sql = sql.strip()

        upper_sql = sql.upper()

        # ------------------------
        # Only SELECT
        # ------------------------

        if not upper_sql.startswith("SELECT"):
            raise SQLValidationError(
                "Only SELECT statements are allowed."
            )

        # ------------------------
        # Multiple Statements
        # ------------------------

        if ";" in sql[:-1]:
            raise SQLValidationError(
                "Multiple SQL statements are not allowed."
            )

        # ------------------------
        # SQL Comments
        # ------------------------

        if "--" in sql:
            raise SQLValidationError(
                "Comments are not allowed."
            )

        if "/*" in sql:
            raise SQLValidationError(
                "Comments are not allowed."
            )

        # ------------------------
        # Dangerous Keywords
        # ------------------------

        for keyword in FORBIDDEN_KEYWORDS:

            if re.search(
                rf"\b{keyword}\b",
                upper_sql
            ):
                raise SQLValidationError(
                    f"{keyword} is forbidden."
                )

        # ------------------------
        # Validate Tables
        # ------------------------

        for table in _extract_table_refs(sql):

            # A dotted name is a cross-schema reference (e.g.
            # information_schema.tables); every allowed table is unqualified.
            if "." in table:
                raise SQLValidationError(
                    f"Cross-schema access to '{table}' is not allowed."
                )

            if table.lower() not in ALLOWED_TABLES:

                raise SQLValidationError(
                    f"Access to '{table}' is not allowed."
                )

        # ------------------------
        # Add LIMIT
        # ------------------------

        if "LIMIT" not in upper_sql:

            sql += f" LIMIT {MAX_LIMIT}"

        return sql
