from sqlalchemy import or_, text

from app.models.city import City
from app.models.officer import Officer
from app.models.permit import Permit
from app.models.permit_status import PermitStatus
from app.models.permit_type import PermitType
from app.repositories.base_repository import BaseRepository


class PermitRepository(BaseRepository):
    """
    Repository responsible for read-only permit queries.
    """

    def execute_read_query(self, sql: str):
        """
        Execute validated SELECT SQL.
        """
        result = self.db.execute(text(sql))

        return [
            dict(row._mapping)
            for row in result
        ]

    # -- Domain queries (parameterized ORM — no raw SQL) -----------------

    def _readable_permit_query(self):
        """Base query returning permits with lookup names already joined."""
        return (
            self.db.query(
                Permit.application_number,
                Permit.applicant_name,
                Permit.submitted_date,
                Permit.approved_date,
                Permit.estimated_cost,
                PermitType.name.label("permit_type"),
                PermitStatus.status.label("status"),
                City.city_name.label("city"),
                Officer.name.label("officer"),
            )
            .join(PermitType, Permit.permit_type_id == PermitType.id)
            .join(PermitStatus, Permit.status_id == PermitStatus.id)
            .join(City, Permit.city_id == City.id)
            .join(Officer, Permit.officer_id == Officer.id)
        )

    def get_pending(self, limit: int = 100):
        """Permits whose status is 'Pending', newest first."""
        rows = (
            self._readable_permit_query()
            .filter(PermitStatus.status == "Pending")
            .order_by(Permit.submitted_date.desc())
            .limit(limit)
            .all()
        )
        return [dict(row._mapping) for row in rows]

    def search(self, term: str, limit: int = 100):
        """Search permits by applicant name or application number."""
        like = f"%{term}%"
        rows = (
            self._readable_permit_query()
            .filter(
                or_(
                    Permit.applicant_name.ilike(like),
                    Permit.application_number.ilike(like),
                )
            )
            .order_by(Permit.submitted_date.desc())
            .limit(limit)
            .all()
        )
        return [dict(row._mapping) for row in rows]
