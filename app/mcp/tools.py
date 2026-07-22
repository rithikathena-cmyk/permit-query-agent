import time

from app.database.session import get_db
from app.repositories.permit_repository import PermitRepository
from app.services.query_service import QueryService
from app.services.schema_service import SchemaService
from app.services.statistics_service import StatisticsService
from app.mcp.responses import (
    success_response,
    schema_response,
    list_response,
    stats_response,
    error_response,
)


def execute_query(sql: str):

    start = time.perf_counter()

    try:

        with get_db() as db:

            service = QueryService(db)

            result = service.execute(sql)

        elapsed = (
            time.perf_counter() - start
        ) * 1000

        return success_response(
            sql=sql,
            data=result,
            execution_time_ms=round(elapsed, 2),
        )

    except Exception as e:

        return error_response(str(e))


def get_schema():

    try:

        with get_db() as db:

            service = SchemaService(db)

            schema = service.get_schema()

        return schema_response(schema)

    except Exception as e:

        return error_response(str(e))


# -- Domain-specific tools (no SQL input; parameterized ORM) -------------

def count_by_status():

    try:
        with get_db() as db:
            data = StatisticsService(db).count_by_status()
        return list_response(data)
    except Exception as e:
        return error_response(str(e))


def count_by_city():

    try:
        with get_db() as db:
            data = StatisticsService(db).count_by_city()
        return list_response(data)
    except Exception as e:
        return error_response(str(e))


def count_by_type():

    try:
        with get_db() as db:
            data = StatisticsService(db).count_by_type()
        return list_response(data)
    except Exception as e:
        return error_response(str(e))


def permit_statistics():

    try:
        with get_db() as db:
            stats = StatisticsService(db).overview()
        return stats_response(stats)
    except Exception as e:
        return error_response(str(e))


def get_pending_permits(limit: int = 100):

    try:
        with get_db() as db:
            data = PermitRepository(db).get_pending(limit=limit)
        return list_response(data)
    except Exception as e:
        return error_response(str(e))


def search_permits(term: str, limit: int = 100):

    try:
        with get_db() as db:
            data = PermitRepository(db).search(term, limit=limit)
        return list_response(data)
    except Exception as e:
        return error_response(str(e))
