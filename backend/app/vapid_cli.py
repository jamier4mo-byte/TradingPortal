"""`make vapid` (python -m app.vapid_cli): write a VAPID key pair for Web Push into the repo-root .env.

Leaves a .env that already has both keys untouched. Otherwise generates a P-256 pair and writes:

  VAPID_PUBLIC_KEY   urlsafe base64 (no padding) of the 65-byte uncompressed point; the browser's
                     `applicationServerKey`.
  VAPID_PRIVATE_KEY  urlsafe base64 (no padding) of the raw 32-byte private value: the "raw" form that
                     py_vapid's `Vapid.from_string` (used by pywebpush) loads, and the format the common
                     `web-push generate-vapid-keys` tool prints, so it fits on one line as a Fly secret.
  VAPID_SUBJECT      a mailto: placeholder (only if missing) — change it to a real address.

The private key is never printed.
"""

import base64
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .core.settings import REPO_ROOT

PLACEHOLDER_SUBJECT = "mailto:you@example.com"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_pair() -> tuple[str, str]:
    """(public, private) in the formats above."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(public), _b64url(private)


def _read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _value(lines: list[str], name: str) -> str:
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def write_keys(env_path: Path) -> dict:
    """Add the missing VAPID lines to `env_path`. Returns what happened (never the private key)."""
    lines = _read(env_path)
    existed = env_path.exists()
    if _value(lines, "VAPID_PUBLIC_KEY") and _value(lines, "VAPID_PRIVATE_KEY"):
        return {"changed": False, "public_key": _value(lines, "VAPID_PUBLIC_KEY"), "added": []}
    public, private = generate_pair()
    # A half-written pair is useless: drop both key lines (blank or orphaned) and write a fresh pair.
    kept = [
        ln for ln in lines if ln.partition("=")[0].strip() not in {"VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"}
    ]
    added = [f"VAPID_PUBLIC_KEY={public}", f"VAPID_PRIVATE_KEY={private}"]
    if not _value(lines, "VAPID_SUBJECT"):
        kept = [ln for ln in kept if ln.partition("=")[0].strip() != "VAPID_SUBJECT"]
        added.append(f"VAPID_SUBJECT={PLACEHOLDER_SUBJECT}")
    if kept and kept[-1].strip():
        kept.append("")
    env_path.write_text("\n".join([*kept, "# Web Push (make vapid)", *added]) + "\n", encoding="utf-8")
    if not existed:
        os.chmod(env_path, 0o600)
    return {"changed": True, "public_key": public, "added": [a.partition("=")[0] for a in added]}


def main(env_path: Path | None = None) -> int:
    path = env_path or REPO_ROOT / ".env"
    result = write_keys(path)
    if not result["changed"]:
        print(f"{path} already has VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY; nothing changed.")
        return 0
    print(f"Wrote {', '.join(result['added'])} to {path}.")
    print(f"Public key: {result['public_key']}")
    if "VAPID_SUBJECT" in result["added"]:
        print(
            f"Change VAPID_SUBJECT={PLACEHOLDER_SUBJECT} to your own mailto: address (push services use it)."
        )
    print("For Fly: `fly secrets set VAPID_PUBLIC_KEY=… VAPID_PRIVATE_KEY=… VAPID_SUBJECT=…` from that file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
