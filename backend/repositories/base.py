"""
Generic base repository providing common CRUD operations.

Subclasses specify the model type T.
"""

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository with common DB operations."""

    def __init__(self, model: type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def get_by_id(self, entity_id: int) -> ModelType | None:
        return self.db.get(self.model, entity_id)

    def list_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def add(self, entity: ModelType) -> ModelType:
        self.db.add(entity)
        self.db.flush()  # Get ID without committing
        return entity

    def delete(self, entity: ModelType) -> None:
        self.db.delete(entity)
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
