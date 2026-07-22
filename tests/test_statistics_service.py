"""Unit tests for the StatisticsService (repository is mocked — no database)."""
from unittest.mock import MagicMock, patch

from app.services.statistics_service import StatisticsService


def _service(repo):
    db = MagicMock()
    with patch(
        "app.services.statistics_service.StatisticsRepository",
        return_value=repo,
    ):
        return StatisticsService(db)


def test_count_by_status_shapes_rows():
    repo = MagicMock()
    repo.count_by_status.return_value = [("Approved", 437), ("Pending", 284)]
    out = _service(repo).count_by_status()
    assert out == [
        {"status": "Approved", "count": 437},
        {"status": "Pending", "count": 284},
    ]


def test_count_by_city_shapes_rows():
    repo = MagicMock()
    repo.count_by_city.return_value = [("Springfield", 12)]
    out = _service(repo).count_by_city()
    assert out == [{"city": "Springfield", "count": 12}]


def test_count_by_type_shapes_rows():
    repo = MagicMock()
    repo.count_by_type.return_value = [("Electrical", 50)]
    out = _service(repo).count_by_type()
    assert out == [{"permit_type": "Electrical", "count": 50}]


def test_overview_combines_total_and_breakdowns():
    repo = MagicMock()
    repo.permit_count.return_value = 1000
    repo.count_by_status.return_value = [("Approved", 437)]
    repo.count_by_type.return_value = [("Electrical", 50)]
    out = _service(repo).overview()
    assert out["total_permits"] == 1000
    assert out["by_status"] == [{"status": "Approved", "count": 437}]
    assert out["by_type"] == [{"permit_type": "Electrical", "count": 50}]
