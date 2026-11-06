"""Screenshot uploads (F10): magic-byte type check, size limits, path-safe keys, thumbnail."""

import io
import secrets
import warnings
from datetime import datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..core.deps import require_owner_or_admin
from ..core.security import utcnow
from ..models import LABELLED_SLOTS, MAX_EXTRA_SCREENSHOTS, SLOTS, Screenshot, Trade, User
from . import audit
from .storage import get_storage

MAX_BYTES = 12 * 1024 * 1024
MAX_THUMB_BYTES = 1024 * 1024
THUMB_EDGE = 400
FULL_EDGE = 1920
MAX_EDGE = 12_000  # a 5K screen is 5120 wide; anything bigger isn't a chart screenshot
MAX_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)

MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"RIFF", "image/webp", "webp"),  # + "WEBP" at offset 8
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
)


class ScreenshotError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def sniff(data: bytes) -> tuple[str, str]:
    for magic, ctype, ext in MAGIC:
        if data.startswith(magic):
            if ctype == "image/webp" and data[8:12] != b"WEBP":
                continue
            return ctype, ext
    raise ScreenshotError("That isn't a PNG, JPEG, WebP or GIF image.", 415)


def _open(data: bytes) -> Image.Image:
    """Check the declared size before decoding a single pixel (decompression-bomb guard)."""
    try:
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if width > MAX_EDGE or height > MAX_EDGE or width * height > MAX_PIXELS:
            raise ScreenshotError(f"Images are limited to {MAX_EDGE}px on an edge.", 413)
        img.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ScreenshotError(f"Images are limited to {MAX_EDGE}px on an edge.", 413) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ScreenshotError("That image can't be read.", 415) from exc
    return ImageOps.exif_transpose(img) or img


def make_thumbnail(img: Image.Image) -> bytes:
    thumb = img.convert("RGB")
    thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
    out = io.BytesIO()
    thumb.save(out, format="WEBP", quality=80, method=4)
    return out.getvalue()


def _next_position(trade: Trade, slot: str) -> int:
    live = [s for s in trade.screenshots if s.deleted_at is None and s.slot == slot]
    return max((s.position for s in live), default=-1) + 1


def add_screenshot(
    db: Session,
    actor: User,
    trade: Trade,
    data: bytes,
    *,
    slot: str,
    thumb: bytes | None = None,
    captured_at: datetime | None = None,
    original_filename: str | None = None,
    replace: bool = True,
) -> Screenshot:
    require_owner_or_admin(trade, actor)
    if slot not in SLOTS:
        raise ScreenshotError("slot must be htf, entry, outcome or extra.")
    if len(data) > MAX_BYTES:
        raise ScreenshotError("Images are limited to 12 MB. The browser should have made a WebP first.", 413)
    if thumb is not None and len(thumb) > MAX_THUMB_BYTES:
        raise ScreenshotError("That thumbnail is too big.", 413)
    ctype, ext = sniff(data)
    img = _open(data)
    width, height = img.size
    if thumb is not None:
        try:
            sniff(thumb)
        except ScreenshotError:
            thumb = None
    if thumb is None:
        thumb = make_thumbnail(img)

    live = [s for s in trade.screenshots if s.deleted_at is None]
    if slot in LABELLED_SLOTS:
        for existing in (s for s in live if s.slot == slot):
            if not replace:
                raise ScreenshotError(f"The {slot} slot is already filled.", 409)
            existing.deleted_at = utcnow()
    elif sum(1 for s in live if s.slot == "extra") >= MAX_EXTRA_SCREENSHOTS:
        raise ScreenshotError(f"Up to {MAX_EXTRA_SCREENSHOTS} extra screenshots per trade.", 409)

    token = secrets.token_hex(8)
    base = f"{trade.strategy_id}/{trade.id}/{slot}-{token}"
    storage = get_storage()
    storage.put(f"{base}.{ext}", data, ctype)
    storage.put(f"{base}.thumb.webp", thumb, "image/webp")
    shot = Screenshot(
        owner_id=trade.owner_id,
        trade_id=trade.id,
        slot=slot,
        position=_next_position(trade, slot),
        full_key=f"{base}.{ext}",
        thumb_key=f"{base}.thumb.webp",
        width=width,
        height=height,
        bytes=len(data),
        content_type=ctype,
        captured_at=captured_at,
        original_filename=(original_filename or None) and original_filename[:255],
    )
    db.add(shot)
    trade.updated_at = utcnow()
    db.flush()
    audit.record(db, "screenshot.added", actor=actor, target_type="screenshot", target_id=shot.id)
    db.commit()
    db.refresh(trade)
    return shot


def move_screenshot(db: Session, actor: User, shot: Screenshot, *, trade: Trade, slot: str) -> Screenshot:
    """Drag to fix in the matcher grid: change slot and/or trade. Swaps with whatever held the slot."""
    require_owner_or_admin(shot, actor)
    require_owner_or_admin(trade, actor)
    if slot not in SLOTS:
        raise ScreenshotError("slot must be htf, entry, outcome or extra.")
    if slot in LABELLED_SLOTS:
        for other in (
            s for s in trade.screenshots if s.deleted_at is None and s.slot == slot and s.id != shot.id
        ):
            other.trade_id, other.slot = shot.trade_id, shot.slot
    shot.trade_id, shot.slot = trade.id, slot
    shot.position = _next_position(trade, slot)
    db.commit()
    return shot


def delete_screenshot(db: Session, actor: User, shot: Screenshot) -> None:
    require_owner_or_admin(shot, actor)
    shot.deleted_at = utcnow()
    audit.record(db, "screenshot.deleted", actor=actor, target_type="screenshot", target_id=shot.id)
    db.commit()


def get_screenshot(db: Session, shot_id: int) -> Screenshot:
    shot = db.get(Screenshot, shot_id)
    if not shot or shot.deleted_at:
        raise ScreenshotError("No such screenshot.", 404)
    return shot
