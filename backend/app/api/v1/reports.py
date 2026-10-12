import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.models.enums import Role
from app.schemas.reports import EventReport
from app.services import reports as svc
from app.services.audit import audit
from app.services.events import load_event

router = APIRouter(prefix="/societies/{society_id}/events/{event_id}", tags=["reports"])


@router.get("/report", response_model=EventReport)
async def report(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    return await svc.build_report(session, await load_event(session, ctx.sid, event_id))


@router.get("/report/export")
async def export(
    event_id: uuid.UUID, format: Literal["csv", "xlsx"] = Query("xlsx"),
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ev.title).strip("-").lower() or "event"
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="report.export", entity="event", entity_id=ev.id, format=format)
    if format == "csv":
        data, media = await svc.export_csv(session, ev), "text/csv; charset=utf-8"
    else:
        data = await svc.export_xlsx(session, ev, await svc.build_report(session, ev))
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content=data, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{slug}-report.{format}"'})
