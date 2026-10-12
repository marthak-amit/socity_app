"""Shared ORM → API model helpers (URL resolution for storage keys)."""

from app.models import User
from app.schemas.auth import UserOut
from app.services.storage import get_storage


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, phone=u.phone, name=u.name, avatar_url=get_storage().url_for(u.avatar_key),
        locale=u.locale, is_super_admin=u.is_super_admin,
    )
