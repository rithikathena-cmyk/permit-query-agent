from sqlalchemy import func

from app.models.permit import Permit
from app.models.permit_status import PermitStatus
from app.models.permit_type import PermitType
from app.models.city import City

from app.repositories.base_repository import BaseRepository


class StatisticsRepository(BaseRepository):

    def permit_count(self):

        return self.db.query(Permit).count()


    def count_by_status(self):

        return (
            self.db.query(
                PermitStatus.status,
                func.count(Permit.id)
            )
            .join(Permit)
            .group_by(PermitStatus.status)
            .all()
        )


    def count_by_city(self):

        return (
            self.db.query(
                City.city_name,
                func.count(Permit.id)
            )
            .join(Permit)
            .group_by(City.city_name)
            .all()
        )


    def count_by_type(self):

        return (
            self.db.query(
                PermitType.name,
                func.count(Permit.id)
            )
            .join(Permit)
            .group_by(PermitType.name)
            .all()
        )
