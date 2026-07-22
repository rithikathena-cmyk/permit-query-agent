from app.models.city import City
from app.repositories.base_repository import BaseRepository


class CityRepository(BaseRepository):

    def get_all(self):

        return (
            self.db.query(City)
            .order_by(City.city_name)
            .all()
        )
