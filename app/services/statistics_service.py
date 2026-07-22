"""Statistics service — domain-specific aggregates over permits.

These power the domain MCP tools (``count_permits_by_status`` etc.). Unlike
``query_permits``, they take no SQL: each is a parameterized ORM query, so there
is no injection surface and no need for the SQL Guard. Use them for the common,
well-known questions; fall back to ``query_permits`` for open-ended ones.
"""
from app.repositories.statistics_repository import StatisticsRepository


class StatisticsService:

    def __init__(self, db):
        self.repo = StatisticsRepository(db)

    def count_by_status(self) -> list[dict]:
        return [
            {"status": status, "count": count}
            for status, count in self.repo.count_by_status()
        ]

    def count_by_city(self) -> list[dict]:
        return [
            {"city": city, "count": count}
            for city, count in self.repo.count_by_city()
        ]

    def count_by_type(self) -> list[dict]:
        return [
            {"permit_type": name, "count": count}
            for name, count in self.repo.count_by_type()
        ]

    def overview(self) -> dict:
        return {
            "total_permits": self.repo.permit_count(),
            "by_status": self.count_by_status(),
            "by_type": self.count_by_type(),
        }
