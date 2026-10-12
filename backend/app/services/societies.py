import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import random_code
from app.models import Membership, Society
from app.models.enums import MembershipStatus, Role
from app.schemas.societies import SocietyBrief, SocietyOut
from app.services.storage import get_storage

ADMIN_ROLES = (Role.OWNER.value, Role.ADMIN.value)


async def unique_invite_code(session: AsyncSession) -> str:
    for _ in range(10):
        code = random_code(8)
        if not await session.scalar(select(Society.id).where(Society.invite_code == code)):
            return code
    raise RuntimeError("could not allocate invite code")


async def admin_count(session: AsyncSession, society_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count()).where(
            Membership.society_id == society_id,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.role.in_(ADMIN_ROLES),
        )
    )


async def society_warnings(session: AsyncSession, society: Society) -> list[str]:
    warnings = []
    if await admin_count(session, society.id) < 2:
        warnings.append("min_two_admins")  # bus-factor: keep at least two people able to approve payments
    if not society.upi_id:
        warnings.append("upi_not_configured")
    return warnings


def brief(s: Society) -> SocietyBrief:
    return SocietyBrief(id=s.id, name=s.name, city=s.city, logo_url=get_storage().url_for(s.logo_key), status=s.status)


async def society_out(session: AsyncSession, s: Society, role: Role) -> SocietyOut:
    is_admin = role in (Role.OWNER, Role.ADMIN)
    return SocietyOut(
        id=s.id, name=s.name, city=s.city, address=s.address, upi_id=s.upi_id, upi_name=s.upi_name,
        logo_url=get_storage().url_for(s.logo_key), status=s.status, timezone=s.timezone,
        created_at=s.created_at, my_role=role,
        invite_code=s.invite_code if is_admin else None,
        warnings=await society_warnings(session, s) if is_admin else [],
    )


def invite_links(code: str) -> tuple[str, str]:
    st = get_settings()
    return f"{st.app_deep_link_scheme}://join?code={code}", f"{st.app_web_domain}/join/{code}"
