"""Shared tag vocabulary (U5): one list, synonyms, admin merge, member proposals."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import utcnow
from ..models import TAG_CATEGORIES, Tag, User
from . import audit


class TagError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def normalise(text: str) -> str:
    """Case- and punctuation-insensitive key: 'F.V.G' → 'fvg', 'Fair value gap' → 'fairvaluegap'."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "tag"


def _live(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).where(Tag.deleted_at.is_(None), Tag.merged_into_id.is_(None))))


def list_tags(db: Session, *, include_proposed: bool = True) -> list[Tag]:
    tags = _live(db)
    if not include_proposed:
        tags = [t for t in tags if t.status == "approved"]
    return sorted(tags, key=lambda t: (t.category, t.name.lower()))


def resolve_tag(db: Session, text: str) -> Tag | None:
    """Match a name or synonym regardless of case or punctuation, following merges."""
    key = normalise(text)
    if not key:
        return None
    for tag in db.scalars(select(Tag).where(Tag.deleted_at.is_(None))):
        if normalise(tag.name) == key or any(normalise(s) == key for s in tag.synonyms or []):
            return _follow_merge(db, tag)
    return None


def _follow_merge(db: Session, tag: Tag) -> Tag:
    seen = set()
    while tag.merged_into_id and tag.id not in seen:
        seen.add(tag.id)
        tag = db.get(Tag, tag.merged_into_id) or tag
    return tag


def _check(
    db: Session, name: str, category: str, synonyms: list[str], *, exclude_id: int | None = None
) -> None:
    if not name.strip():
        raise TagError("Give the tag a name.")
    if category not in TAG_CATEGORIES:
        raise TagError("Unknown category.")
    keys = {normalise(name), *(normalise(s) for s in synonyms)}
    keys.discard("")
    for other in _live(db):
        if other.id == exclude_id:
            continue
        other_keys = {normalise(other.name), *(normalise(s) for s in other.synonyms or [])}
        clash = keys & other_keys
        if clash:
            raise TagError(f"'{name}' clashes with the existing tag '{other.name}'.", 409)


def _unique_slug(db: Session, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while True:
        taken = db.scalar(select(Tag).where(Tag.slug == slug))
        if not taken or taken.id == exclude_id:
            return slug
        slug = f"{base}-{n}"
        n += 1


def create_tag(
    db: Session,
    actor: User,
    *,
    name: str,
    category: str,
    synonyms: list[str] | None = None,
    status: str = "approved",
) -> Tag:
    synonyms = [s.strip() for s in (synonyms or []) if s.strip()]
    _check(db, name, category, synonyms)
    tag = Tag(
        name=name.strip(),
        slug=_unique_slug(db, slugify(name)),
        category=category,
        synonyms=synonyms,
        status=status,
        created_by_id=actor.id,
    )
    db.add(tag)
    db.flush()
    audit.record(
        db,
        f"tag.{'proposed' if status == 'proposed' else 'created'}",
        actor=actor,
        target_type="tag",
        target_id=tag.id,
    )
    db.commit()
    return tag


def propose_tag(
    db: Session, member: User, *, name: str, category: str, synonyms: list[str] | None = None
) -> Tag:
    return create_tag(db, member, name=name, category=category, synonyms=synonyms, status="proposed")


def update_tag(
    db: Session,
    admin: User,
    tag: Tag,
    *,
    name: str | None = None,
    category: str | None = None,
    synonyms: list[str] | None = None,
    status: str | None = None,
) -> Tag:
    new_name = (name if name is not None else tag.name).strip()
    new_category = category if category is not None else tag.category
    new_synonyms = [s.strip() for s in (synonyms if synonyms is not None else tag.synonyms) if s.strip()]
    if status is not None and status not in ("approved", "proposed"):
        raise TagError("Status must be approved or proposed.")
    _check(db, new_name, new_category, new_synonyms, exclude_id=tag.id)
    if new_name != tag.name:
        tag.slug = _unique_slug(db, slugify(new_name), exclude_id=tag.id)
    tag.name, tag.category, tag.synonyms = new_name, new_category, new_synonyms
    if status is not None:
        tag.status = status
    audit.record(db, "tag.updated", actor=admin, target_type="tag", target_id=tag.id)
    db.commit()
    return tag


def merge_tags(db: Session, admin: User, *, source: Tag, into: Tag) -> Tag:
    """Fold `source` into `into`: its name and synonyms become synonyms of the survivor."""
    if source.id == into.id:
        raise TagError("Pick two different tags.")
    if into.merged_into_id or into.deleted_at:
        raise TagError("Can't merge into a tag that is itself merged or deleted.")
    merged_keys = {normalise(into.name), *(normalise(s) for s in into.synonyms)}
    extra = [s for s in [source.name, *source.synonyms] if normalise(s) not in merged_keys]
    into.synonyms = [*into.synonyms, *extra]
    source.merged_into_id = into.id
    source.deleted_at = utcnow()
    audit.record(
        db, "tag.merged", actor=admin, target_type="tag", target_id=source.id, meta={"into": into.id}
    )
    db.commit()
    return into


def delete_tag(db: Session, admin: User, tag: Tag) -> None:
    tag.deleted_at = utcnow()
    audit.record(db, "tag.deleted", actor=admin, target_type="tag", target_id=tag.id)
    db.commit()
