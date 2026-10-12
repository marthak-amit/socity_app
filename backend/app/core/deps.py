"""Authentication + society scoping dependencies. EVERY society-scoped route goes through
`require_role(...)`; the role always comes from the DB membership row, never from the client."""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import forbidden, not_found, unauthorized
from app.core.security import decode_token
from app.models import Membership, Society, User
from app.models.enums import ROLE_RANK, MembershipStatus, Role, SocietyStatus

bearer = HTTPBearer(auto_error=False)


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise unauthorized("not_authenticated", "Missing bearer token")
    try:
        payload = decode_token(creds.credentials, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise unauthorized("invalid_token", "Invalid or expired token") from e
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized("invalid_token", "User no longer exists")
    return user


async def current_super_admin(user: User = Depends(current_user)) -> User:
    if not user.is_super_admin:
        raise forbidden("super_admin_required", "Platform admin only")
    return user


@dataclass
class SocietyContext:
    user: User
    society: Society
    membership: Membership

    @property
    def role(self) -> Role:
        return Role(self.membership.role)

    @property
    def is_admin(self) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[Role.ADMIN]

    @property
    def sid(self) -> uuid.UUID:
        return self.society.id


def require_role(min_role: Role = Role.MEMBER, *, allow_suspended: bool = False):
    """Dependency factory: resolves `/societies/{society_id}/...` and enforces membership + role.

    * not a member (or society deleted) → 404, so society existence is not leaked across tenants
    * pending/removed membership → 403
    * role below `min_role` → 403
    * suspended society → 403 (except where `allow_suspended`)
    """

    async def dep(
        society_id: uuid.UUID = Path(...),
        user: User = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> SocietyContext:
        row = (
            await session.execute(
                select(Membership, Society)
                .join(Society, Society.id == Membership.society_id)
                .where(Membership.user_id == user.id, Membership.society_id == society_id)
            )
        ).first()
        if row is None or row.Society.status == SocietyStatus.DELETED:
            raise not_found("society_not_found", "Society not found")
        membership, society = row.Membership, row.Society
        if membership.status != MembershipStatus.ACTIVE:
            raise forbidden(f"membership_{membership.status}", f"Your membership is {membership.status}")
        if society.status == SocietyStatus.SUSPENDED and not allow_suspended:
            raise forbidden("society_suspended", "This society has been suspended by the platform")
        if ROLE_RANK[Role(membership.role)] < ROLE_RANK[min_role]:
            raise forbidden("insufficient_role", f"Requires {min_role.value} role")
        return SocietyContext(user=user, society=society, membership=membership)

    return dep
