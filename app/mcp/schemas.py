"""Input/output schemas for MCP tools.

FastMCP infers the tool's JSON schema from the function signature, so these
Pydantic models are optional documentation/validation helpers.
"""
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Input payload for the query_permits tool."""

    sql: str = Field(
        ...,
        description="A read-only SELECT statement to run against the "
        "permit database.",
    )


class QueryResponse(BaseModel):
    """Shape of a successful query response."""

    success: bool
    generated_sql: str
    rows_returned: int
    execution_time_ms: float
    data: list[dict]
