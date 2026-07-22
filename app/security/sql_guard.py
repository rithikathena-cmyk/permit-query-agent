import re

from app.security.constants import (
    ALLOWED_TABLES,
    FORBIDDEN_KEYWORDS,
    MAX_LIMIT,
)

from app.security.exceptions import SQLValidationError


class SQLGuard:
    """
    Production SQL validator.
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

        tables = re.findall(
            r"(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)",
            sql,
            re.IGNORECASE,
        )

        for table in tables:

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
