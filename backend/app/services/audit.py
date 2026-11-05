from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, User


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    target_type: str | None = None,
    target_id: int | str | None = None,
    meta: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one audit row. Never put a plaintext secret in `meta`."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        meta=meta,
    )
    db.add(entry)
    return entry
