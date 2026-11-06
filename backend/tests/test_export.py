"""Export for AI, Copy for AI and CSV: zip layout, manifest hashes, JSONL, image limits, no secrets."""

import csv
import hashlib
import io
import json
import zipfile

from PIL import Image

from app.services.analytics.export import MAX_EDGE
from tests.test_journal_api import do_import, new_strategy, png_bytes

KEY = "td-live-key-should-never-leak-9876"


def q(**body) -> str:
    return json.dumps(body)


def export_zip(client, **body) -> zipfile.ZipFile:
    res = client.get("/api/analytics/export/ai", params={"q": q(**body)})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert res.headers["content-disposition"].startswith('attachment; filename="trading-portal-')
    return zipfile.ZipFile(io.BytesIO(res.content))


def strategy_with_shots(client, *, big=False):
    s = new_strategy(client, description="Sweep, then FVG entry in the killzone.")
    result = do_import(client, s["id"], "backtest")
    t = result["trades"][0]
    client.patch(
        f"/api/trades/{t['id']}",
        json={
            "reasoning": {"htf_bias": "Bearish daily", "pd_array": "FVG"},
            "rules_followed": {"r1": True, "r2": False},
            "tags": ["FVG"],
            "notes": "Textbook",
        },
    )
    for slot in ("htf", "entry", "outcome"):
        w, h = (3200, 1800) if big else (1200, 700)
        res = client.post(
            f"/api/trades/{t['id']}/screenshots",
            files={"file": (f"{slot}.png", png_bytes(w, h), "image/png")},
            data={"slot": slot},
        )
        assert res.status_code == 201, res.text
    return s, t


def test_zip_structure_and_manifest_hashes(admin_client):
    s, _ = strategy_with_shots(admin_client)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"])
    assert zf.testzip() is None  # unzips cleanly
    names = set(zf.namelist())
    assert {"README_prompt.md", "strategy.md", "trades.jsonl", "manifest.json"} <= names
    images = sorted(n for n in names if n.startswith("images/"))
    assert len(images) == 3 and all(n.endswith(".webp") for n in images)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["app"] == "Trading Portal" and manifest["source"] == "backtest"
    assert manifest["counts"] == {"trades": 10, "strategies": 1, "images": 3, "missing_images": 0}
    assert manifest["images"]["max_long_edge"] == MAX_EDGE
    listed = {f["path"]: f for f in manifest["files"]}
    assert set(listed) == names - {"manifest.json"}
    for path, entry in listed.items():
        data = zf.read(path)
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], path
        assert len(data) == entry["bytes"]


def test_trades_jsonl_is_valid_and_complete(admin_client):
    s, t = strategy_with_shots(admin_client)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"])
    lines = zf.read("trades.jsonl").decode().splitlines()
    assert len(lines) == 10
    records = [json.loads(line) for line in lines]
    assert [r["n"] for r in records] == list(range(1, 11))
    first = next(r for r in records if r["id"] == t["id"])
    for key in (
        "r",
        "pnl",
        "outcome",
        "entry_price",
        "stop_price",
        "session",
        "weekday",
        "max_favourable_r",
        "rules",
    ):
        assert key in first
    assert first["reasoning"] == {"HTF bias": "Bearish daily", "PD array / entry model": "FVG"}
    assert first["tags"] == ["FVG"] and first["notes"] == "Textbook"
    assert {"rule": "Entry taken inside the killzone", "kept": False} in first["rules"]
    assert first["all_rules_kept"] is False
    assert [i["slot"] for i in first["images"]] == ["htf", "entry", "outcome"]
    for img in first["images"]:
        assert img["path"] in zf.namelist()
    assert first["logged_by"] == "Jamie" and first["strategy"] == "NAS100 silver bullet"


def test_images_are_resized_to_the_long_edge_limit(admin_client):
    s, _ = strategy_with_shots(admin_client, big=True)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"])
    for name in (n for n in zf.namelist() if n.startswith("images/")):
        with Image.open(io.BytesIO(zf.read(name))) as img:
            assert max(img.size) <= MAX_EDGE
            assert img.format == "WEBP"


def test_without_images(admin_client):
    s, _ = strategy_with_shots(admin_client)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"], include_images=False)
    assert not [n for n in zf.namelist() if n.startswith("images/")]
    assert json.loads(zf.read("manifest.json"))["images"]["included"] is False


def test_readme_and_strategy_md_read_well(admin_client):
    s, _ = strategy_with_shots(admin_client)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"])
    readme = zf.read("README_prompt.md").decode()
    assert readme.startswith("# Read me first")
    assert "NAS100 silver bullet" in readme and "10 trades" in readme and "3 screenshots" in readme
    assert "Win rate leaves breakevens out" in readme and "What I'd like from you" in readme
    assert "{" not in readme.replace("`{", "")  # every placeholder filled
    md = zf.read("strategy.md").decode()
    assert (
        "## NAS100 silver bullet" in md and "### Rulebook" in md and "### Backtest results (10 trades)" in md
    )
    assert "| Win rate |" in md and "Breakevens are left out" in md
    assert "### Reconcile against FX Replay's CSV" in md and "✓" in md


def test_export_respects_the_filters(admin_client):
    s, _ = strategy_with_shots(admin_client)
    zf = export_zip(admin_client, source="backtest", strategy_id=s["id"], filters={"directions": ["sell"]})
    records = [json.loads(line) for line in zf.read("trades.jsonl").decode().splitlines()]
    assert records and all(r["direction"] == "short" for r in records)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["filters"]["directions"] == ["sell"] and "direction short" in manifest["filters_text"]


def test_member_exports_everyone_but_never_secrets(admin_client, member_client, admin, member):
    member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    admin_client.put("/api/me/keys/twelve_data", json={"key": KEY + "-admin"})
    strategy_with_shots(admin_client)  # the admin's strategy
    zf = export_zip(member_client, source="backtest", scope="everyone")
    assert json.loads(zf.read("manifest.json"))["counts"]["trades"] == 10
    everything = b"".join(zf.read(n) for n in zf.namelist())
    for secret in (
        KEY.encode(),
        b"td-live-key",
        admin.email.encode(),
        member.email.encode(),
        b"argon2",
        b"$argon",
    ):
        assert secret not in everything
    for field in (b"password", b"api_key", b"ciphertext", b"token", b"email"):
        assert field not in everything.lower()
    # The member's own scope has none of the admin's trades.
    mine = export_zip(member_client, source="backtest", scope="mine")
    assert json.loads(mine.read("manifest.json"))["counts"]["trades"] == 0
    assert "No trades match these filters." in mine.read("strategy.md").decode()


def test_csv_export(admin_client):
    s, _ = strategy_with_shots(admin_client)
    res = admin_client.get("/api/analytics/export/csv", params={"q": q(strategy_id=s["id"])})
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    text = res.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 10
    assert {"r", "pnl", "outcome", "opened_uk", "tags"} <= set(rows[0])


def test_copy_for_ai(admin_client):
    s, _ = strategy_with_shots(admin_client)
    res = admin_client.post("/api/analytics/copy", json={"strategy_id": s["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["trades"] == 10
    assert body["text"].startswith("# Strategy dossier")
    assert "## Trades (compact)" in body["text"] and body["text"].count(" | NAS100 | ") == 10


def test_export_errors(admin_client, client):
    assert client.get("/api/analytics/export/ai").status_code == 401
    assert admin_client.get("/api/analytics/export/ai", params={"q": "not json"}).status_code == 422
    assert admin_client.get("/api/analytics/export/ai", params={"q": q(strategy_id=99999)}).status_code == 404
    assert admin_client.get("/api/analytics/export/csv", params={"q": q(source="nope")}).status_code == 422
