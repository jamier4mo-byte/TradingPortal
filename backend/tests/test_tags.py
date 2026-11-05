"""Shared tag vocabulary: seed, resolve, propose, curate, merge."""

import pytest

from app.services import tags as tags_svc

REQUIRED_SEED = [
    "FVG", "IFVG", "order block", "breaker", "mitigation block", "BOS", "MSS", "CHoCH", "liquidity sweep",
    "BSL", "SSL", "equal highs", "equal lows", "OTE", "premium", "discount", "PD array", "SMT divergence",
    "NWOG", "NDOG", "Asia killzone", "London killzone", "NY AM killzone", "NY PM killzone", "Silver Bullet",
    "Judas swing", "HTF bias",
]  # fmt: skip


@pytest.mark.parametrize("text", REQUIRED_SEED)
def test_seed_covers_the_starter_list(db, text) -> None:
    assert tags_svc.resolve_tag(db, text) is not None, text


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("FVG", "fvg"),
        ("fair value gap", "fvg"),
        ("f.v.g", "fvg"),
        ("Fair-Value  Gap", "fvg"),
        ("IMBALANCE", "fvg"),
        ("change of character", "mss"),
        ("choch", "mss"),
        ("buy side liquidity", "bsl"),
        ("Buyside Liquidity", "bsl"),
        ("new york am", "ny-am-killzone"),
        ("OB", "order-block"),
    ],
)
def test_resolve_is_case_and_punctuation_insensitive(db, text, slug) -> None:
    assert tags_svc.resolve_tag(db, text).slug == slug


def test_resolve_unknown_is_none(db) -> None:
    assert tags_svc.resolve_tag(db, "wibble wobble") is None
    assert tags_svc.resolve_tag(db, "...") is None


def test_resolve_endpoint(member_client) -> None:
    res = member_client.get("/api/tags/resolve", params={"q": "f.v.g"})
    assert res.status_code == 200 and res.json()["tag"]["slug"] == "fvg"
    assert member_client.get("/api/tags/resolve", params={"q": "zzz"}).json()["tag"] is None


def test_member_proposes_admin_approves(member_client, admin_client) -> None:
    res = member_client.post(
        "/api/tags", json={"name": "Rejection block", "category": "pd_array", "synonyms": ["RB"]}
    )
    assert res.status_code == 201 and res.json()["status"] == "proposed"
    tag_id = res.json()["id"]
    assert member_client.patch(f"/api/tags/{tag_id}", json={"status": "approved"}).status_code == 403
    ok = admin_client.patch(f"/api/tags/{tag_id}", json={"status": "approved"})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"


def test_admin_creates_approved_and_duplicates_clash(admin_client) -> None:
    res = admin_client.post("/api/tags", json={"name": "Fresh tag", "category": "confluence"})
    assert res.status_code == 201 and res.json()["status"] == "approved" and res.json()["slug"] == "fresh-tag"
    dup = admin_client.post("/api/tags", json={"name": "fair value gap", "category": "pd_array"})
    assert dup.status_code == 409
    syn = admin_client.post(
        "/api/tags", json={"name": "Totally new", "category": "other", "synonyms": ["f.v.g"]}
    )
    assert syn.status_code == 409


def test_merge_folds_source_into_survivor(admin_client, db) -> None:
    tags = {t["slug"]: t for t in admin_client.get("/api/tags").json()}
    source, into = tags["equal-highs"], tags["equal-lows"]
    res = admin_client.post(f"/api/tags/{source['id']}/merge", json={"into_id": into["id"]})
    assert res.status_code == 200
    body = res.json()
    assert "Equal highs" in body["synonyms"] and "EQH" in body["synonyms"]
    # the merged tag disappears from the list but still resolves to the survivor
    slugs = [t["slug"] for t in admin_client.get("/api/tags").json()]
    assert "equal-highs" not in slugs
    assert tags_svc.resolve_tag(db, "EQH").slug == "equal-lows"
    assert (
        admin_client.get(f"/api/tags/{source['id']}").status_code == 404
    )  # no detail route: 404 via not-found path
    bad = admin_client.post(f"/api/tags/{into['id']}/merge", json={"into_id": into["id"]})
    assert bad.status_code == 400


def test_rename_updates_slug_and_rejects_bad_category(admin_client) -> None:
    tag = next(t for t in admin_client.get("/api/tags").json() if t["slug"] == "silver-bullet")
    res = admin_client.patch(f"/api/tags/{tag['id']}", json={"name": "ICT Silver Bullet"})
    assert res.status_code == 200 and res.json()["slug"] == "ict-silver-bullet"
    assert admin_client.patch(f"/api/tags/{tag['id']}", json={"category": "nonsense"}).status_code == 422


def test_delete_is_soft(admin_client, db) -> None:
    tag = next(t for t in admin_client.get("/api/tags").json() if t["slug"] == "macro")
    assert admin_client.delete(f"/api/tags/{tag['id']}").status_code == 200
    assert "macro" not in [t["slug"] for t in admin_client.get("/api/tags").json()]
    from app.models import Tag

    assert db.get(Tag, tag["id"]).deleted_at is not None
