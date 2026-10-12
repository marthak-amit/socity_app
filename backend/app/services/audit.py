import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def audit(
    session: AsyncSession,
    *,
    society_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | str | None = None,
    **meta,
) -> None:
    """Queue an audit row in the caller's transaction (so it commits/rolls back with the change)."""
    session.add(
        AuditLog(
            society_id=society_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id else None,
            meta={k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in meta.items()},
        )
    )
