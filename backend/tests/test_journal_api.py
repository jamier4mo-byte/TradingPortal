"""Replay Journal API: strategies, imports, sessions, undo, trash, permissions, screenshots, summary."""

import io
from datetime import UTC, datetime

import pytest
from PIL import Image

from app.services.storage import get_storage
from tests.conftest import FIXTURES, make_client, sign_in

SAMPLE = (FIXTURES / "fxreplay-sample.csv").read_bytes()


def new_strategy(client, name="NAS100 silver bullet", **extra):
    body = {"name": name, "instruments": ["NAS100"], "timeframes": ["5m"], "entry_models": ["FVG"], **extra}
    res = client.post("/api/strategies", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def do_import(client, strategy_id, destination, data=SAMPLE, timezone=None, name="export.csv"):
    form = {"destination": destination}
    if timezone:
        form["timezone"] = timezone
    res = client.post(
        f"/api/strategies/{strategy_id}/imports", files={"file": (name, data, "text/csv")}, data=form
    )
    assert res.status_code == 201, res.text
    return res.json()


def png_bytes(w=1200, h=700, colour=(40, 60, 90)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(out, format="PNG")
    return out.getvalue()


# ---- strategies ----------------------------------------------------------------------------


def test_create_strategy_fills_defaults_and_computes_stage(admin_client):
    s = new_strategy(admin_client)
    assert s["csv_timezone"] == "Europe/London"
    assert len(s["rules"]) == 4 and s["reasoning_template"][0]["key"] == "htf_bias"
    assert s["stage"] == "ideal" and s["ideal_count"] == 0 and s["coverage"]["unlocked"] is False
    assert s["coverage"]["target_months"] == 6 and s["can_edit"] is True
    assert s["owner"]["display_name"] == "Jamie"


def test_rulebook_must_have_four_to_eight_rules(admin_client):
    res = admin_client.post(
        "/api/strategies", json={"name": "x", "rules": [{"text": "one"}, {"text": "two"}]}
    )
    assert res.status_code == 400
    res = admin_client.post(
        "/api/strategies", json={"name": "x", "rules": [{"text": f"r{i}"} for i in range(9)]}
    )
    assert res.status_code == 400
    res = admin_client.post(
        "/api/strategies", json={"name": "x", "rules": [{"text": f"r{i}"} for i in range(8)]}
    )
    assert res.status_code == 201


def test_strategy_timezone_only_london_or_utc(admin_client):
    res = admin_client.post("/api/strategies", json={"name": "x", "csv_timezone": "America/New_York"})
    assert res.status_code == 422


def test_scope_filter_mine_everyone_others(admin_client, member_client):
    new_strategy(admin_client, "Jamie's")
    new_strategy(member_client, "Sam's")
    assert len(admin_client.get("/api/strategies").json()) == 2
    assert [s["name"] for s in admin_client.get("/api/strategies?scope=mine").json()] == ["Jamie's"]
    assert [s["name"] for s in admin_client.get("/api/strategies?scope=others").json()] == ["Sam's"]


# ---- imports (F3) --------------------------------------------------------------------------


def test_preview_reports_everything_and_writes_nothing(admin_client):
    s = new_strategy(admin_client)
    res = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", SAMPLE, "text/csv")}
    )
    assert res.status_code == 200, res.text
    p = res.json()
    assert p["rows_parsed"] == 10 and p["rows_total"] == 12 and len(p["problems"]) == 2
    assert p["timezone"] == "Europe/London"
    assert (p["winners"], p["losers"], p["breakevens"]) == (6, 2, 2)
    assert p["duplicates"] == {"ideal": 0, "backtest": 0}
    assert p["would_import"] == {"ideal": 6, "backtest": 10}
    assert p["range_start"] == "2026-01-12" and p["range_end"] == "2026-10-25"
    assert p["rows"][0]["instrument"] == "NAS100" and p["rows"][0]["opened_uk"] == "12 Jan 2026 09:30"
    assert admin_client.get(f"/api/strategies/{s['id']}/trades").json() == []


def test_ideal_import_keeps_winners_only(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    assert out["report"]["imported"] == 6 and out["report"]["skipped_not_winners"] == 4
    assert out["session"]["kind"] == "ideal" and out["session"]["trade_count"] == 6
    assert out["session"]["range_start"] == "2026-01-12"
    trades = out["trades"]
    assert all(t["kind"] == "ideal" and t["outcome"] == "win" for t in trades)
    # Times are UTC on the wire; the May trade was 13:45 BST
    may = next(t for t in trades if t["fx_id"] == "100000005")
    assert may["opened_at"].startswith("2026-05-20T12:45:00")
    assert may["session_label"] == "New York" and may["side"] == "sell"
    # NAS100 is in points: SL 40 points, TP 120 points = 3R
    assert may["sl_distance"] == 40 and may["tp_distance"] == 120 and may["tp_r"] == pytest.approx(3.0)
    assert may["r_multiple"] == pytest.approx(1.6)
    # Tags came through the vocabulary
    march = next(t for t in trades if t["fx_id"] == "100000003")
    assert sorted(t["name"] for t in march["tags"]) == ["FVG", "Order block"]
    assert march["raw_row"] if "raw_row" in march else True
    card = admin_client.get(f"/api/strategies/{s['id']}").json()
    assert (
        card["ideal_count"] == 6
        and card["coverage"]["covered_count"] == 6
        and card["coverage"]["best_run"] == 3
    )


def test_backtest_import_keeps_everything_then_duplicates_are_skipped(admin_client):
    s = new_strategy(admin_client)
    first = do_import(admin_client, s["id"], "ideal")
    assert first["report"]["imported"] == 6
    # The backtest ledger is a separate destination: every row, winners included
    second = do_import(admin_client, s["id"], "backtest")
    assert second["report"]["imported"] == 10 and second["report"]["duplicates"] == []
    assert sorted(t["outcome"] for t in second["trades"]).count("win") == 6
    third = do_import(admin_client, s["id"], "backtest")
    assert third["report"]["imported"] == 0 and len(third["report"]["duplicates"]) == 10
    again = do_import(admin_client, s["id"], "ideal")
    assert again["report"]["imported"] == 0 and len(again["report"]["duplicates"]) == 6
    preview = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", SAMPLE, "text/csv")}
    ).json()
    assert preview["duplicates"] == {"ideal": 6, "backtest": 10}
    assert preview["would_import"] == {"ideal": 0, "backtest": 0}
    card = admin_client.get(f"/api/strategies/{s['id']}").json()
    assert card["backtest_count"] == 10 and card["stage"] == "backtesting"
    assert card["backtest_stats"]["trades"] == 10 and card["backtest_stats"]["win_rate"] == pytest.approx(
        6 / 8
    )


def test_fresh_strategy_backtest_import_takes_all_ten(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "backtest")
    assert out["report"]["imported"] == 10
    stats = out["session"]["stats"]
    assert stats["trades"] == 10 and stats["win_rate"] == pytest.approx(6 / 8)


def test_import_with_utc_override(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "backtest", timezone="UTC")
    may = next(t for t in out["trades"] if t["fx_id"] == "100000005")
    assert may["opened_at"].startswith("2026-05-20T13:45:00")
    assert out["session"]["csv_timezone"] == "UTC"


def test_breakeven_threshold_from_the_users_settings(admin_client):
    admin_client.patch("/api/me", json={"breakeven_threshold": 100})
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    assert out["report"]["imported"] == 4  # the +90 and +60 trades are now breakeven


def test_bad_files_are_422_not_500(admin_client):
    s = new_strategy(admin_client)
    res = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")}
    )
    assert res.status_code == 422 and "Missing columns" in res.json()["detail"]
    res = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", b"", "text/csv")}
    )
    assert res.status_code == 400


# ---- undo and trash ------------------------------------------------------------------------


def test_undo_session_soft_deletes_its_trades_and_restore_brings_them_back(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    sid = out["session"]["id"]
    res = admin_client.delete(f"/api/journal/sessions/{sid}")
    assert res.status_code == 200 and res.json()["trades"] == 6
    assert admin_client.get(f"/api/strategies/{s['id']}/trades").json() == []
    assert admin_client.get(f"/api/journal/sessions/{sid}").status_code == 404
    # re-import now is not a duplicate problem (deleted trades don't count) but restoring first is the point
    trash = admin_client.get("/api/journal/trash").json()
    assert [x["id"] for x in trash["sessions"]] == [sid] and trash["trades"] == [] and trash["days"] == 30
    res = admin_client.post(f"/api/journal/sessions/{sid}/restore")
    assert res.status_code == 200 and res.json()["trades"] == 6
    assert len(admin_client.get(f"/api/strategies/{s['id']}/trades").json()) == 6


def test_deleted_trades_do_not_count_towards_coverage(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    jan = next(t for t in out["trades"] if t["fx_id"] == "100000001")
    admin_client.delete(f"/api/trades/{jan['id']}")
    card = admin_client.get(f"/api/strategies/{s['id']}").json()
    assert card["ideal_count"] == 5 and card["coverage"]["first_month"] == "2026-03"
    trash = admin_client.get("/api/journal/trash").json()
    assert [t["id"] for t in trash["trades"]] == [jan["id"]]
    admin_client.post(f"/api/trades/{jan['id']}/restore")
    assert admin_client.get(f"/api/strategies/{s['id']}").json()["ideal_count"] == 6


def test_deleted_strategy_goes_to_trash_and_restores(admin_client):
    s = new_strategy(admin_client)
    admin_client.delete(f"/api/strategies/{s['id']}")
    assert admin_client.get(f"/api/strategies/{s['id']}").status_code == 404
    assert admin_client.get("/api/strategies").json() == []
    assert [x["id"] for x in admin_client.get("/api/journal/trash").json()["strategies"]] == [s["id"]]
    assert admin_client.post(f"/api/strategies/{s['id']}/restore").status_code == 200
    assert admin_client.get(f"/api/strategies/{s['id']}").status_code == 200


# ---- permissions ---------------------------------------------------------------------------


def test_member_gets_403_on_the_admins_strategy_and_trades(admin_client, member_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    trade = out["trades"][0]
    # read is fine (everything visible by default)
    seen = member_client.get(f"/api/strategies/{s['id']}").json()
    assert seen["can_edit"] is False and seen["owner"]["display_name"] == "Jamie"
    assert member_client.get(f"/api/trades/{trade['id']}").json()["can_edit"] is False
    # every write is refused
    assert member_client.patch(f"/api/strategies/{s['id']}", json={"name": "Mine now"}).status_code == 403
    assert member_client.delete(f"/api/strategies/{s['id']}").status_code == 403
    assert member_client.patch(f"/api/trades/{trade['id']}", json={"notes": "hi"}).status_code == 403
    assert member_client.delete(f"/api/trades/{trade['id']}").status_code == 403
    assert member_client.delete(f"/api/journal/sessions/{out['session']['id']}").status_code == 403
    body = {"kind": "ideal", "instrument": "NAS100", "side": "buy", "opened_at": "2026-02-02T10:00:00Z"}
    assert member_client.post(f"/api/strategies/{s['id']}/trades", json=body).status_code == 403
    res = member_client.post(
        f"/api/strategies/{s['id']}/imports",
        files={"file": ("x.csv", SAMPLE, "text/csv")},
        data={"destination": "backtest"},
    )
    assert res.status_code == 403
    res = member_client.post(
        f"/api/trades/{trade['id']}/screenshots",
        files={"file": ("a.png", png_bytes(), "image/png")},
        data={"slot": "entry"},
    )
    assert res.status_code == 403


def test_admin_can_change_a_members_records(admin_client, member_client):
    s = new_strategy(member_client, "Sam's")
    res = admin_client.patch(f"/api/strategies/{s['id']}", json={"description": "tidied by Jamie"})
    assert res.status_code == 200 and res.json()["owner_id"] == s["owner_id"]
    out = do_import(admin_client, s["id"], "backtest")
    # trades logged by the admin into Sam's strategy stay Sam's
    assert out["trades"][0]["owner"]["display_name"] == "Sam"


def test_instruments_admin_only_for_writes(admin_client, member_client):
    assert len(member_client.get("/api/instruments").json()) == 11
    body = {
        "symbol": "us30",
        "name": "Dow",
        "asset_class": "index",
        "pip_size": 1,
        "unit": "points",
        "price_decimals": 1,
    }
    assert member_client.post("/api/instruments", json=body).status_code == 403
    res = admin_client.post("/api/instruments", json=body)
    assert res.status_code == 201 and res.json()["symbol"] == "US30"
    assert (
        admin_client.patch(f"/api/instruments/{res.json()['id']}", json={"pip_size": 0.5}).json()["pip_size"]
        == 0.5
    )


# ---- manual trades and annotation ----------------------------------------------------------


def test_quick_log_computes_distances_and_resolves_tags(admin_client):
    s = new_strategy(admin_client)
    body = {
        "kind": "ideal",
        "instrument": "EUR/USD",
        "side": "buy",
        "opened_at": "2026-03-03T08:30:00Z",
        "closed_at": "2026-03-03T10:00:00Z",
        "entry_price": 1.0850,
        "initial_sl": 1.0830,
        "max_tp": 1.0910,
        "exit_price": 1.0905,
        "pnl": 275,
        "entry_model": "FVG",
        "tags": ["fair value gap", "f.v.g", "nonsense-tag"],
        "reasoning": {"htf_bias": "bullish"},
    }
    res = admin_client.post(f"/api/strategies/{s['id']}/trades", json=body)
    assert res.status_code == 201, res.text
    t = res.json()
    assert t["instrument"] == "EURUSD" and t["sl_distance"] == 20 and t["tp_distance"] == 60
    assert t["tp_r"] == pytest.approx(3.0) and t["r_multiple"] == pytest.approx(2.75)
    assert t["outcome"] == "win" and t["session_label"] == "London" and t["duration_seconds"] == 5400
    assert [x["name"] for x in t["tags"]] == ["FVG"]
    # annotate
    res = admin_client.patch(
        f"/api/trades/{t['id']}",
        json={"rules_followed": {"r1": True, "r2": False}, "mae_r": -0.4, "mfe_r": 3.1, "notes": "late"},
    )
    assert (
        res.status_code == 200 and res.json()["mae_r"] == -0.4 and res.json()["rules_followed"]["r2"] is False
    )


def test_missed_setups_stay_out_of_pnl(admin_client):
    s = new_strategy(admin_client)
    body = {
        "kind": "missed",
        "instrument": "NAS100",
        "side": "sell",
        "opened_at": "2026-03-03T14:30:00Z",
        "pnl": 500,
        "notes": "Saw it, didn't take it",
    }
    t = admin_client.post(f"/api/strategies/{s['id']}/trades", json=body).json()
    assert t["kind"] == "missed" and t["pnl"] is None and t["outcome"] is None
    card = admin_client.get(f"/api/strategies/{s['id']}").json()
    assert card["missed_count"] == 1 and card["ideal_count"] == 0 and card["backtest_stats"] is None


# ---- sessions, inbox, recap, brief ---------------------------------------------------------


def test_session_progress_and_improve_note(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    sid = out["session"]["id"]
    assert out["session"]["progress"] == {
        "trades": 6,
        "screenshots": 0,
        "screenshots_target": 18,
        "reasons": 0,
        "reasons_target": 6,
        "completed": 0,
    }
    t = out["trades"][0]
    admin_client.patch(f"/api/trades/{t['id']}", json={"reasoning": {"htf_bias": "bearish"}})
    admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("a.png", png_bytes(), "image/png")},
        data={"slot": "entry"},
    )
    sess = admin_client.patch(
        f"/api/journal/sessions/{sid}", json={"improve_note": "Wait for the FVG to fill"}
    ).json()
    assert sess["progress"]["screenshots"] == 1 and sess["progress"]["reasons"] == 1
    assert sess["progress"]["completed"] == 0
    # Completed is a manual mark, not a computed state
    done = admin_client.patch(f"/api/trades/{t['id']}", json={"annotated": True}).json()
    assert done["annotated_at"] is not None
    assert admin_client.get(f"/api/journal/sessions/{sid}").json()["progress"]["completed"] == 1
    undone = admin_client.patch(f"/api/trades/{t['id']}", json={"annotated": False}).json()
    assert undone["annotated_at"] is None
    assert sess["improve_note"] == "Wait for the FVG to fill"
    brief = admin_client.get(f"/api/strategies/{s['id']}/brief").json()
    assert brief["recent_improve_notes"][0]["note"] == "Wait for the FVG to fill"
    assert brief["next_uncovered"] == "2026-09" and brief["profile"] is None and brief["news"] is None
    assert [x["id"] for x in admin_client.get(f"/api/strategies/{s['id']}/sessions").json()] == [sid]


def test_profile_appears_once_unlocked_or_opened_early(admin_client, db):
    s = new_strategy(admin_client)
    for month in range(1, 7):
        body = {
            "kind": "ideal",
            "instrument": "NAS100",
            "side": "buy",
            "opened_at": f"2026-{month:02d}-10T09:30:00Z",
            "closed_at": f"2026-{month:02d}-10T10:30:00Z",
            "entry_price": 20000,
            "initial_sl": 19960,
            "max_tp": 20120,
            "exit_price": 20100,
            "pnl": 100,
            "entry_model": "FVG",
            "reasoning": {"confluences": "NWOG, SMT"},
        }
        assert admin_client.post(f"/api/strategies/{s['id']}/trades", json=body).status_code == 201
    card = admin_client.get(f"/api/strategies/{s['id']}").json()
    assert card["coverage"]["unlocked"] is True and card["stage"] == "ready"
    profile = admin_client.get(f"/api/strategies/{s['id']}/profile").json()
    assert profile["trades"] == 6 and profile["avg_sl_distance"] == 40 and profile["avg_tp_r"] == 3
    assert profile["typical_duration_seconds"] == 3600
    assert profile["entry_models"] == [{"label": "FVG", "count": 6}]
    assert {c["label"] for c in profile["confluences"]} == {"NWOG", "SMT"}
    # cached: same object back without recompute, and invalidated by a new trade
    assert admin_client.get(f"/api/strategies/{s['id']}/profile").json() == profile
    body["opened_at"] = "2026-07-01T09:30:00Z"
    admin_client.post(f"/api/strategies/{s['id']}/trades", json=body)
    assert admin_client.get(f"/api/strategies/{s['id']}/profile").json()["trades"] == 7


def test_open_early_shows_profile_before_unlock(admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "ideal")
    assert admin_client.get(f"/api/strategies/{s['id']}/profile").json() is None
    admin_client.patch(f"/api/strategies/{s['id']}", json={"backtest_opened_early": True})
    assert admin_client.get(f"/api/strategies/{s['id']}/profile").json()["trades"] == 6


def test_summary_for_the_hub(admin_client, member_client):
    assert admin_client.get("/api/journal/summary").json() == {
        "strategies": 0,
        "trades": 0,
        "unlocked": 0,
        "last_session": None,
        "my_last_session": None,
    }
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "ideal")
    summary = member_client.get("/api/journal/summary").json()
    assert summary["strategies"] == 1 and summary["trades"] == 6
    assert summary["last_session"]["trade_count"] == 6 and summary["my_last_session"] is None


# ---- screenshots ---------------------------------------------------------------------------


def test_upload_makes_a_thumbnail_serves_only_when_signed_in_and_fills_slots(admin_client):
    s = new_strategy(admin_client)
    t = do_import(admin_client, s["id"], "ideal")["trades"][0]
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("T01_entry.png", png_bytes(2984, 1719), "image/png")},
        data={"slot": "entry", "captured_at": "2026-11-05T23:25:13Z"},
    )
    assert res.status_code == 201, res.text
    shot = res.json()["screenshots"][0]
    assert shot["slot"] == "entry" and shot["width"] == 2984 and shot["content_type"] == "image/png"
    assert shot["original_filename"] == "T01_entry.png" and shot["captured_at"].startswith(
        "2026-11-05T23:25:13"
    )
    full = admin_client.get(shot["full_url"])
    assert full.status_code == 200 and full.headers["content-type"] == "image/png"
    thumb = admin_client.get(shot["thumb_url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    img = Image.open(io.BytesIO(thumb.content))
    assert max(img.size) == 400
    assert make_client().get(shot["full_url"]).status_code == 401  # never public
    # a second entry replaces the first; extras cap at 3
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("b.png", png_bytes(), "image/png")},
        data={"slot": "entry"},
    )
    assert len([x for x in res.json()["screenshots"] if x["slot"] == "entry"]) == 1
    for i in range(3):
        res = admin_client.post(
            f"/api/trades/{t['id']}/screenshots",
            files={"file": (f"e{i}.png", png_bytes(), "image/png")},
            data={"slot": "extra"},
        )
        assert res.status_code == 201
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("e4.png", png_bytes(), "image/png")},
        data={"slot": "extra"},
    )
    assert res.status_code == 409


def test_type_is_checked_by_magic_bytes_and_keys_stay_in_the_store(admin_client):
    s = new_strategy(admin_client)
    t = do_import(admin_client, s["id"], "ideal")["trades"][0]
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("evil.png", b"<html>hi</html>", "image/png")},
        data={"slot": "entry"},
    )
    assert res.status_code == 415
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("../../x.png", png_bytes(), "image/png")},
        data={"slot": "outcome"},
    )
    assert res.status_code == 201
    storage = get_storage()
    for p in storage.root.rglob("*"):
        assert ".." not in p.parts and storage.root in p.parents


def test_browser_made_webp_and_thumbnail_are_stored_as_sent(admin_client):
    s = new_strategy(admin_client)
    t = do_import(admin_client, s["id"], "ideal")["trades"][0]
    full, thumb = io.BytesIO(), io.BytesIO()
    Image.new("RGB", (1920, 1080), (10, 20, 30)).save(full, format="WEBP")
    Image.new("RGB", (400, 225), (10, 20, 30)).save(thumb, format="WEBP")
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={
            "file": ("a.webp", full.getvalue(), "image/webp"),
            "thumb": ("a.thumb.webp", thumb.getvalue(), "image/webp"),
        },
        data={"slot": "outcome"},
    )
    assert res.status_code == 201, res.text
    shot = res.json()["screenshots"][0]
    assert shot["content_type"] == "image/webp" and shot["width"] == 1920
    assert admin_client.get(shot["thumb_url"]).content == thumb.getvalue()


def test_move_and_delete_screenshot(admin_client):
    s = new_strategy(admin_client)
    trades = do_import(admin_client, s["id"], "ideal")["trades"]
    a, b = trades[0], trades[1]
    shot = admin_client.post(
        f"/api/trades/{a['id']}/screenshots",
        files={"file": ("x.png", png_bytes(), "image/png")},
        data={"slot": "entry"},
    ).json()["screenshots"][0]
    other = admin_client.post(
        f"/api/trades/{b['id']}/screenshots",
        files={"file": ("y.png", png_bytes(), "image/png")},
        data={"slot": "outcome"},
    ).json()["screenshots"][0]
    moved = admin_client.patch(
        f"/api/screenshots/{shot['id']}", json={"trade_id": b["id"], "slot": "outcome"}
    ).json()
    assert moved["trade_id"] == b["id"] and moved["slot"] == "outcome"
    # the one that held the slot swapped into the vacated place
    a_shots = admin_client.get(f"/api/trades/{a['id']}").json()["screenshots"]
    assert [x["id"] for x in a_shots] == [other["id"]] and a_shots[0]["slot"] == "entry"
    assert admin_client.delete(f"/api/screenshots/{shot['id']}").status_code == 200
    assert admin_client.get(f"/api/screenshots/{shot['id']}/full").status_code == 404
    assert admin_client.get(f"/api/trades/{b['id']}").json()["screenshots"] == []


def test_match_endpoint_pairs_files_with_the_sessions_trades(admin_client):
    s = new_strategy(admin_client)
    out = do_import(admin_client, s["id"], "ideal")
    sid, trades = out["session"]["id"], out["trades"]
    files = [{"name": f"T0{i}_{slot}.png"} for i in range(1, 7) for slot in ("htf", "entry", "outcome")]
    files += [{"name": "spare.png", "captured_at": datetime(2026, 11, 5, 23, 25, tzinfo=UTC).isoformat()}]
    res = admin_client.post(f"/api/journal/sessions/{sid}/match", json={"files": files})
    assert res.status_code == 200, res.text
    matches = res.json()
    assert sum(1 for m in matches if m["trade_id"] is not None) == 18
    assert matches[0] == {
        "file": "T01_htf.png",
        "trade_id": trades[0]["id"],
        "slot": "htf",
        "confidence": "high",
        "reason": "filename says trade 1 htf",
    }
    assert matches[-1]["trade_id"] is None and matches[-1]["confidence"] == "none"
    # hash-named files fall back to sequence
    files = [
        {"name": f"{h}.png", "captured_at": datetime(2026, 11, 5, 23, 25, i, tzinfo=UTC).isoformat()}
        for i, h in enumerate("abcdefghijklmnop")
    ]
    matches = admin_client.post(f"/api/journal/sessions/{sid}/match", json={"files": files}).json()
    assert all(m["trade_id"] is not None and m["confidence"] == "low" for m in matches)  # 16 files, 18 slots
    assert [m["slot"] for m in matches[:3]] == ["htf", "entry", "outcome"]
    assert matches[2]["trade_id"] == trades[0]["id"]


def test_member_cannot_see_nothing_but_can_see_everything_read_only(member, admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "backtest")
    c = make_client()
    sign_in(c, member.email)
    assert len(c.get(f"/api/strategies/{s['id']}/trades").json()) == 10


def test_huge_declared_dimensions_are_refused_before_decoding(admin_client):
    import struct
    import zlib

    s = new_strategy(admin_client)
    t = do_import(admin_client, s["id"], "ideal")["trades"][0]
    # A real 1×1 PNG whose header is patched to claim 30000×30000 pixels (CRC recomputed)
    real = png_bytes(1, 1)
    ihdr = struct.pack(">IIBBBBB", 30000, 30000, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    patched = (
        real[:8]
        + struct.pack(">I", 13)
        + chunk
        + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        + real[33:]
    )
    res = admin_client.post(
        f"/api/trades/{t['id']}/screenshots",
        files={"file": ("bomb.png", patched, "image/png")},
        data={"slot": "entry"},
    )
    assert res.status_code == 413, res.text


def test_session_id_must_belong_to_the_strategy_and_the_actor(admin_client, member_client):
    mine = new_strategy(admin_client, "Jamie's")
    sams = new_strategy(member_client, "Sam's")
    sam_session = do_import(member_client, sams["id"], "backtest")["session"]
    body = {
        "kind": "ideal",
        "instrument": "NAS100",
        "side": "buy",
        "opened_at": "2026-02-02T10:00:00Z",
        "session_id": sam_session["id"],
    }
    assert admin_client.post(f"/api/strategies/{mine['id']}/trades", json=body).status_code == 404
    jamie_session = do_import(admin_client, mine["id"], "ideal")["session"]
    body["session_id"] = jamie_session["id"]
    assert member_client.post(f"/api/strategies/{mine['id']}/trades", json=body).status_code == 403
