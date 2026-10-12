import uuid
from datetime import datetime
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams:
    def __init__(self, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> None:
        self.limit = limit
        self.offset = offset


class Msg(BaseModel):
    ok: bool = True
    message: str | None = None


class UserBrief(ORM):
    id: uuid.UUID
    name: str | None
    phone: str


__all__ = ["ORM", "Page", "PageParams", "Msg", "UserBrief", "datetime"]
