"""S3Storage (Tigris) behind the Storage interface, against moto. Nothing here touches the network."""

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.api import journal as journal_api
from app.core.settings import Settings
from app.services import backup
from app.services import screenshots as shots_svc
from app.services import storage as storage_mod
from app.services.storage import LocalStorage, S3Storage, StorageError, get_storage, local_storage
from tests.test_journal_api import do_import, new_strategy, png_bytes

BUCKET = "tp-test-bucket"


@pytest.fixture
def s3store(monkeypatch) -> S3Storage:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    for name in ("AWS_ENDPOINT_URL_S3", "AWS_ENDPOINT_URL", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield S3Storage(BUCKET, prefix="screenshots/", region="us-east-1")


def _keys(store: S3Storage) -> list[str]:
    res = store.client.list_objects_v2(Bucket=store.bucket)
    return sorted(o["Key"] for o in res.get("Contents", []))


# ---- the store on its own -----------------------------------------------------------------------------


def test_round_trip_and_content_type(s3store):
    s3store.put("1/2/entry-abc.png", b"\x89PNG fake", "image/png")
    assert s3store.get("1/2/entry-abc.png") == b"\x89PNG fake"
    head = s3store.client.head_object(Bucket=BUCKET, Key="screenshots/1/2/entry-abc.png")
    assert head["ContentType"] == "image/png"


def test_prefix_is_applied_and_path_is_none(s3store):
    s3store.put("a/b.webp", b"x", "image/webp")
    assert _keys(s3store) == ["screenshots/a/b.webp"]
    assert s3store.path("a/b.webp") is None
    bare = S3Storage(BUCKET, prefix="", region="us-east-1", client=s3store.client)
    bare.put("c.webp", b"y", "image/webp")
    assert "c.webp" in _keys(s3store)


def test_exists_and_delete(s3store):
    assert not s3store.exists("1/x.png")
    s3store.put("1/x.png", b"data", "image/png")
    assert s3store.exists("1/x.png")
    s3store.delete("1/x.png")
    assert not s3store.exists("1/x.png")
    s3store.delete("1/x.png")  # deleting twice is fine


def test_missing_key_raises_file_not_found_like_local(s3store, tmp_path):
    with pytest.raises(FileNotFoundError):
        s3store.get("nope/missing.png")
    with pytest.raises(FileNotFoundError):
        LocalStorage(tmp_path).get("nope/missing.png")


@pytest.mark.parametrize("key", ["../etc/passwd", "/abs.png", "a//b.png", "a/../b.png", "", "sp ace.png"])
def test_unsafe_keys_refused(s3store, key):
    with pytest.raises(StorageError):
        s3store.put(key, b"x", "image/png")
    with pytest.raises(StorageError):
        s3store.exists(key)


def test_no_bucket_is_a_clear_error():
    with pytest.raises(StorageError):
        S3Storage("")
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, STORAGE_BACKEND="s3", BUCKET_NAME="")
    assert "BUCKET_NAME" in str(exc.value)


def test_get_storage_picks_the_backend(monkeypatch):
    assert isinstance(get_storage(), LocalStorage)  # tests run local
    s3_settings = Settings(
        _env_file=None,
        STORAGE_BACKEND="s3",
        BUCKET_NAME="tp-live",
        AWS_ENDPOINT_URL_S3="https://t3.storage.dev",
        AWS_REGION="",
    )
    assert s3_settings.s3_region == "auto"
    monkeypatch.setattr(storage_mod, "get_settings", lambda: s3_settings)
    store = get_storage.__wrapped__()
    assert isinstance(store, S3Storage)
    assert (store.bucket, store.endpoint_url) == ("tp-live", "https://t3.storage.dev")
    assert store.prefix == "screenshots/"


# ---- through the API ---------------------------------------------------------------------------------


@pytest.fixture
def api_on_s3(monkeypatch, s3store) -> S3Storage:
    monkeypatch.setattr(shots_svc, "get_storage", lambda: s3store)
    monkeypatch.setattr(journal_api, "get_storage", lambda: s3store)
    return s3store


def test_upload_and_fetch_screenshot_through_s3(admin_client, api_on_s3):
    s = new_strategy(admin_client)
    t = do_import(admin_client, s["id"], "backtest")["trades"][0]
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("entry.png", png_bytes(800, 500), "image/png")},
        data={"slot": "entry"},
    )
    assert res.status_code == 201, res.text
    shot = res.json()["screenshots"][0]  # the upload returns the whole trade
    keys = _keys(api_on_s3)
    assert len(keys) == 2 and all(k.startswith(f"screenshots/{s['id']}/{t['id']}/entry-") for k in keys)
    assert not (local_storage().root / f"{s['id']}").exists()  # nothing written locally

    full = admin_client.get(shot["full_url"])
    assert full.status_code == 200
    assert full.headers["content-type"] == "image/png"
    assert full.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert full.content.startswith(b"\x89PNG")
    thumb = admin_client.get(shot["thumb_url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    assert thumb.content[8:12] == b"WEBP"

    api_on_s3.client.delete_object(Bucket=BUCKET, Key=keys[0])
    api_on_s3.client.delete_object(Bucket=BUCKET, Key=keys[1])
    assert admin_client.get(shot["full_url"]).status_code == 404


# ---- make migrate-screenshots --------------------------------------------------------------------------


def test_migrate_screenshots_is_idempotent(admin_client, db, s3store, capsys):
    s = new_strategy(admin_client)
    trades = do_import(admin_client, s["id"], "backtest")["trades"][:2]
    for t in trades:
        for slot in ("htf", "entry"):
            res = admin_client.post(
                f"/api/trades/{t['id']}/screenshots",
                files={"file": (f"{slot}.png", png_bytes(600, 400), "image/png")},
                data={"slot": slot},
            )
            assert res.status_code == 201, res.text
    local = local_storage()

    dry = backup.copy_screenshots(db, local, s3store, dry_run=True)
    assert dry == {"copied": 8, "skipped": 0, "missing": 0} and _keys(s3store) == []

    first = backup.copy_screenshots(db, local, s3store)
    assert first == {"copied": 8, "skipped": 0, "missing": 0}
    assert len(_keys(s3store)) == 8
    second = backup.copy_screenshots(db, local, s3store)
    assert second == {"copied": 0, "skipped": 8, "missing": 0}
    assert "copied 0, skipped 8" in capsys.readouterr().out

    # Resumable: a new upload plus a file that vanished locally.
    res = admin_client.post(
        f"/api/trades/{trades[0]['id']}/screenshots",
        files={"file": ("outcome.png", png_bytes(600, 400), "image/png")},
        data={"slot": "outcome"},
    )
    assert res.status_code == 201
    one_key = _keys(s3store)[0].removeprefix("screenshots/")
    s3store.client.delete_object(Bucket=BUCKET, Key=f"screenshots/{one_key}")
    local.delete(one_key)
    third = backup.copy_screenshots(db, local, s3store)
    assert third == {"copied": 2, "skipped": 7, "missing": 1}
    # The local files are still there (only the one we removed by hand is gone).
    assert sum(1 for _ in local.root.rglob("*.*")) == 9


def test_migrate_cli_refuses_without_s3_backend(db):
    with pytest.raises(RuntimeError, match="STORAGE_BACKEND"):
        backup.migrate_screenshots(db)
