from typing import Any


def success_response(
    sql: str,
    data: list[dict],
    execution_time_ms: float,
):
    return {
        "success": True,
        "generated_sql": sql,
        "rows_returned": len(data),
        "execution_time_ms": execution_time_ms,
        "data": data,
    }


def schema_response(schema: dict):
    return {
        "success": True,
        "table_count": len(schema),
        "tables": schema,
    }


def list_response(data: list[dict]):
    return {
        "success": True,
        "rows_returned": len(data),
        "data": data,
    }


def stats_response(statistics: dict):
    return {
        "success": True,
        "statistics": statistics,
    }


def error_response(message: str):
    return {
        "success": False,
        "error": message,
    }
