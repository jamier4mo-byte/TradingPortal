"""`make vapid`: writes a usable VAPID pair into .env once, never prints the private key."""

import stat
import time

from py_vapid import Vapid, Vapid01

from app import vapid_cli
from app.services import push


def _env(path):
    out = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.startswith("#"):
            out[key] = value
    return out


def test_writes_a_pair_that_round_trips(tmp_path, capsys):
    env = tmp_path / ".env"
    assert vapid_cli.main(env) == 0
    values = _env(env)
    public, private = values["VAPID_PUBLIC_KEY"], values["VAPID_PRIVATE_KEY"]
    assert values["VAPID_SUBJECT"] == "mailto:you@example.com"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert "=" not in public and "=" not in private  # urlsafe base64, no padding
    assert len(public) == 87 and len(private) == 43  # 65-byte point, 32-byte private value

    out = capsys.readouterr().out
    assert private not in out
    assert public in out
    assert "change" in out.lower()

    # pywebpush loads the private key through Vapid.from_string; its public half is the one we wrote.
    signer = Vapid01.from_string(private_key=private)
    claims = {
        "sub": "mailto:you@example.com",
        "aud": "https://push.example.test",
        "exp": int(time.time()) + 600,
    }
    assert Vapid01.verify(public, signer.sign(claims)["Authorization"])
    assert Vapid.from_string(private_key=private)  # the RFC 8292 class loads it too

    # The sender built from these settings serves the same public key to browsers.
    sender = push.WebPushSender(private, "mailto:you@example.com", public)
    assert sender.public_key == public


def test_second_run_changes_nothing(tmp_path, capsys):
    env = tmp_path / ".env"
    vapid_cli.main(env)
    before = env.read_text()
    capsys.readouterr()
    assert vapid_cli.main(env) == 0
    assert env.read_text() == before
    assert "nothing changed" in capsys.readouterr().out


def test_keeps_other_lines_and_replaces_a_blank_pair(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_PORTAL_SECRET_KEY=abc\nVAPID_PUBLIC_KEY=\nVAPID_SUBJECT=mailto:jamie@example.test\n"
    )
    env.chmod(0o644)
    result = vapid_cli.write_keys(env)
    assert result["changed"] and result["added"] == ["VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"]
    values = _env(env)
    assert values["TRADING_PORTAL_SECRET_KEY"] == "abc"
    assert values["VAPID_SUBJECT"] == "mailto:jamie@example.test"
    assert values["VAPID_PUBLIC_KEY"] and values["VAPID_PRIVATE_KEY"]
    assert env.read_text().count("VAPID_PUBLIC_KEY=") == 1
    assert stat.S_IMODE(env.stat().st_mode) == 0o644  # an existing file keeps its mode


def test_sender_is_off_without_keys():
    assert push.get_sender() is None  # conftest blanks VAPID_* for every test
