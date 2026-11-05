"""Passkeys: option generation, challenge handling and a verified registration + login round trip.

The authenticator is simulated in-process with an EC key, so no browser and no network.
"""

import base64
import hashlib
import json
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

RP_ID = "localhost"
ORIGIN = "http://localhost:5173"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _cose_ec2_key(pub: ec.EllipticCurvePublicKey) -> bytes:
    nums = pub.public_numbers()
    x, y = nums.x.to_bytes(32, "big"), nums.y.to_bytes(32, "big")
    # CBOR map {1: 2, 3: -7, -1: 1, -2: x, -3: y}
    return b"\xa5" + b"\x01\x02" + b"\x03\x26" + b"\x20\x01" + b"\x21\x58\x20" + x + b"\x22\x58\x20" + y


class FakeAuthenticator:
    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = hashlib.sha256(b"fake-cred").digest()[:16]
        self.counter = 0

    def _auth_data(self, flags: int, with_cred: bool) -> bytes:
        rp_hash = hashlib.sha256(RP_ID.encode()).digest()
        self.counter += 1
        data = rp_hash + bytes([flags]) + struct.pack(">I", self.counter)
        if with_cred:
            aaguid = b"\x00" * 16
            data += (
                aaguid
                + struct.pack(">H", len(self.cred_id))
                + self.cred_id
                + _cose_ec2_key(self.key.public_key())
            )
        return data

    def register(self, challenge_b64: str) -> dict:
        client_data = json.dumps(
            {"type": "webauthn.create", "challenge": challenge_b64, "origin": ORIGIN}
        ).encode()
        auth_data = self._auth_data(0x41, with_cred=True)  # UP + AT
        # CBOR {"fmt": "none", "attStmt": {}, "authData": bytes}
        att = (
            b"\xa3"
            + b"\x63fmt"
            + b"\x64none"
            + b"\x67attStmt\xa0"
            + b"\x68authData"
            + b"\x58"
            + bytes([len(auth_data)])
            + auth_data
        )
        return {
            "id": b64url(self.cred_id),
            "rawId": b64url(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "attestationObject": b64url(att),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def authenticate(self, challenge_b64: str) -> dict:
        client_data = json.dumps(
            {"type": "webauthn.get", "challenge": challenge_b64, "origin": ORIGIN}
        ).encode()
        auth_data = self._auth_data(0x01, with_cred=False)
        sig = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64url(self.cred_id),
            "rawId": b64url(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(sig),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        }


def test_register_then_sign_in_with_passkey(member_client, member, client) -> None:
    auth = FakeAuthenticator()
    begin = member_client.post("/api/me/passkeys/begin")
    assert begin.status_code == 200, begin.text
    options, key = begin.json()["options"], begin.json()["challenge_key"]
    assert options["rp"]["id"] == RP_ID and options["user"]["name"] == member.email
    finish = member_client.post(
        "/api/me/passkeys/finish",
        json={"challenge_key": key, "credential": auth.register(options["challenge"]), "name": "MacBook"},
    )
    assert finish.status_code == 201, finish.text
    assert finish.json()["name"] == "MacBook"
    assert [p["name"] for p in member_client.get("/api/me/passkeys").json()] == ["MacBook"]

    # Fresh browser: discoverable sign-in without typing the email
    begin = client.post("/api/auth/passkey/login/begin")
    assert begin.status_code == 200
    options, key = begin.json()["options"], begin.json()["challenge_key"]
    assert "allowCredentials" not in options or not options["allowCredentials"]
    res = client.post(
        "/api/auth/passkey/login/finish",
        json={"challenge_key": key, "credential": auth.authenticate(options["challenge"])},
    )
    assert res.status_code == 200, res.text
    assert res.json()["email"] == member.email
    assert client.get("/api/auth/me").status_code == 200


def test_challenge_cannot_be_replayed_and_wrong_origin_fails(member_client, client, member) -> None:
    auth = FakeAuthenticator()
    begin = member_client.post("/api/me/passkeys/begin").json()
    cred = auth.register(begin["options"]["challenge"])
    assert (
        member_client.post(
            "/api/me/passkeys/finish",
            json={"challenge_key": begin["challenge_key"], "credential": cred, "name": "x"},
        ).status_code
        == 201
    )
    replay = member_client.post(
        "/api/me/passkeys/finish",
        json={"challenge_key": begin["challenge_key"], "credential": cred, "name": "x"},
    )
    assert replay.status_code == 410

    begin = client.post("/api/auth/passkey/login/begin").json()
    bad = auth.authenticate(begin["options"]["challenge"])
    client_data = json.loads(b64url_decode(bad["response"]["clientDataJSON"]))
    client_data["origin"] = "https://evil.example"
    bad["response"]["clientDataJSON"] = b64url(json.dumps(client_data).encode())
    res = client.post(
        "/api/auth/passkey/login/finish", json={"challenge_key": begin["challenge_key"], "credential": bad}
    )
    assert res.status_code == 401


def test_unknown_passkey_404_and_delete(member_client, client) -> None:
    auth = FakeAuthenticator()
    begin = client.post("/api/auth/passkey/login/begin").json()
    res = client.post(
        "/api/auth/passkey/login/finish",
        json={
            "challenge_key": begin["challenge_key"],
            "credential": auth.authenticate(begin["options"]["challenge"]),
        },
    )
    assert res.status_code == 404
    assert member_client.delete("/api/me/passkeys/999").status_code == 404


def test_deactivated_user_cannot_passkey_sign_in(member_client, admin_client, member, client) -> None:
    auth = FakeAuthenticator()
    begin = member_client.post("/api/me/passkeys/begin").json()
    member_client.post(
        "/api/me/passkeys/finish",
        json={
            "challenge_key": begin["challenge_key"],
            "credential": auth.register(begin["options"]["challenge"]),
            "name": "x",
        },
    )
    admin_client.patch(f"/api/admin/users/{member.id}/status", json={"status": "deactivated"})
    begin = client.post("/api/auth/passkey/login/begin").json()
    res = client.post(
        "/api/auth/passkey/login/finish",
        json={
            "challenge_key": begin["challenge_key"],
            "credential": auth.authenticate(begin["options"]["challenge"]),
        },
    )
    assert res.status_code == 403
