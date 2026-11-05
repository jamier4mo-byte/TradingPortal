"""Shared tag vocabulary: everyone reads, members propose, the admin curates."""

from fastapi import APIRouter, HTTPException, Query

from ..core.deps import AdminUser, CurrentUser, Db
from ..models import Tag
from ..schemas.auth import OkOut
from ..schemas.tags import TagCreateIn, TagMergeIn, TagOut, TagResolveOut, TagUpdateIn
from ..services import tags as tags_svc
from ..services.tags import TagError
from .errors import http

router = APIRouter(prefix="/tags", tags=["tags"])


def _get_tag(db: Db, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if not tag or tag.deleted_at:
        raise HTTPException(404, "No such tag.")
    return tag


@router.get("", response_model=list[TagOut])
def list_tags(_: CurrentUser, db: Db) -> list[TagOut]:
    return [TagOut.model_validate(t) for t in tags_svc.list_tags(db)]


@router.get("/resolve", response_model=TagResolveOut)
def resolve(_: CurrentUser, db: Db, q: str = Query(min_length=1, max_length=80)) -> TagResolveOut:
    tag = tags_svc.resolve_tag(db, q)
    return TagResolveOut(query=q, tag=TagOut.model_validate(tag) if tag else None)


@router.post("", response_model=TagOut, status_code=201)
def create_or_propose(body: TagCreateIn, user: CurrentUser, db: Db) -> TagOut:
    """Admins create approved tags; members propose them (status=proposed) for the admin to approve."""
    try:
        if user.is_admin:
            tag = tags_svc.create_tag(
                db, user, name=body.name, category=body.category, synonyms=body.synonyms
            )
        else:
            tag = tags_svc.propose_tag(
                db, user, name=body.name, category=body.category, synonyms=body.synonyms
            )
    except TagError as exc:
        raise http(exc) from exc
    return TagOut.model_validate(tag)


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, body: TagUpdateIn, admin: AdminUser, db: Db) -> TagOut:
    tag = _get_tag(db, tag_id)
    try:
        tags_svc.update_tag(db, admin, tag, **body.model_dump(exclude_unset=True))
    except TagError as exc:
        raise http(exc) from exc
    return TagOut.model_validate(tag)


@router.post("/{tag_id}/merge", response_model=TagOut)
def merge_tag(tag_id: int, body: TagMergeIn, admin: AdminUser, db: Db) -> TagOut:
    source, into = _get_tag(db, tag_id), _get_tag(db, body.into_id)
    try:
        survivor = tags_svc.merge_tags(db, admin, source=source, into=into)
    except TagError as exc:
        raise http(exc) from exc
    return TagOut.model_validate(survivor)


@router.delete("/{tag_id}", response_model=OkOut)
def delete_tag(tag_id: int, admin: AdminUser, db: Db) -> OkOut:
    tags_svc.delete_tag(db, admin, _get_tag(db, tag_id))
    return OkOut()
