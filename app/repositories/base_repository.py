from sqlalchemy.orm import Session


class BaseRepository:
    """Base repository shared by all repositories."""

    def __init__(self, db: Session):
        self.db = db
