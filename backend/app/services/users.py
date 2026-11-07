"""Users, invites, resets and sign-in: the server-side rules (F6, F11, 4.1)."""

from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core.security import hash_password, hash_token, new_token, password_problem, utcnow, verify_password
from ..core.settings import get_settings
from ..models import OWNER_COLOURS, Invite, PasswordReset, User
from ..models import Session as DbSession
from . import audit


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def normalise_email(email: str) -> str:
    return email.strip().lower()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalise_email(email)))


def next_colour_index(db: Session) -> int:
    return (db.scalar(select(func.count(User.id))) or 0) % OWNER_COLOURS


def create_user(db: Session, *, email: str, display_name: str, password: str, role: str = "member") -> User:
    email = normalise_email(email)
    if not email or "@" not in email:
        raise AuthError("Enter a valid email address.")
    if get_by_email(db, email):
        raise AuthError("That email already has an account.", 409)
    if problem := password_problem(password):
        raise AuthError(problem)
    user = User(
        email=email,
        display_name=display_name.strip() or email.split("@")[0],
        role=role,
        password_hash=hash_password(password),
        colour_index=next_colour_index(db),
    )
    db.add(user)
    db.flush()
    return user


# ---- sign-in -------------------------------------------------------------------------------


def authenticate(db: Session, email: str, password: str) -> User:
    """Password sign-in with lockout. Raises AuthError(401) or AuthError(423) when locked."""
    s = get_settings()
    user = get_by_email(db, email)
    now = utcnow()
    # A locked account answers 423 so the UI can show the locked-out screen. That reveals the account
    # exists; accepted on purpose (see PHASE-1-REPORT Assumptions) and softened by the per-IP limit.
    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AuthError(f"Too many attempts. Try again in {minutes} min.", 423)

    ok = verify_password(password, user.password_hash if user else None)
    if not user or not ok:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= s.lockout_threshold:
                user.locked_until = now + timedelta(minutes=s.lockout_minutes)
                user.failed_logins = 0
                audit.record(db, "auth.locked", target_type="user", target_id=user.id)
            db.commit()
        raise AuthError("Wrong email or password.", 401)
    if not user.is_active:
        raise AuthError("This account is deactivated.", 403)
    user.failed_logins = 0
    user.locked_until = None
    return user


def create_session(db: Session, user: User, user_agent: str | None) -> str:
    """Create a server-side session and return the plaintext token (goes in the cookie only)."""
    token = new_token()
    now = utcnow()
    db.add(
        DbSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(days=get_settings().session_days),
            user_agent=(user_agent or "")[:300] or None,
            created_at=now,
            last_used_at=now,
        )
    )
    user.last_seen_at = now
    audit.record(db, "auth.login", actor=user, target_type="user", target_id=user.id)
    db.commit()
    return token


def find_session(db: Session, token: str) -> DbSession | None:
    sess = db.scalar(select(DbSession).where(DbSession.token_hash == hash_token(token)))
    if not sess or sess.expires_at <= utcnow():
        return None
    return sess


def touch_session(db: Session, sess: DbSession) -> bool:
    """Sliding window: extend the expiry at most once per slide window. Returns True if extended."""
    s = get_settings()
    now = utcnow()
    extended = False
    if now - sess.last_used_at >= timedelta(hours=s.session_slide_hours):
        sess.expires_at = now + timedelta(days=s.session_days)
        extended = True
    if extended or (sess.user.last_seen_at is None) or now - sess.user.last_seen_at >= timedelta(minutes=5):
        sess.last_used_at = now
        sess.user.last_seen_at = now
        db.commit()
    return extended


def revoke_session(db: Session, token: str) -> None:
    sess = db.scalar(select(DbSession).where(DbSession.token_hash == hash_token(token)))
    if sess:
        audit.record(db, "auth.logout", actor=sess.user, target_type="user", target_id=sess.user_id)
        db.delete(sess)
        db.commit()


def revoke_all_sessions(db: Session, user: User) -> None:
    for sess in list(user.sessions):
        db.delete(sess)


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AuthError("Your current password is wrong.", 401)
    set_password(db, user, new, actor=user)


def set_password(db: Session, user: User, new: str, *, actor: User | None) -> None:
    if problem := password_problem(new):
        raise AuthError(problem)
    if verify_password(new, user.password_hash):
        raise AuthError("Choose a password you haven't used here before.")
    user.password_hash = hash_password(new)
    revoke_all_sessions(db, user)  # every other browser signs out
    audit.record(db, "user.password_changed", actor=actor, target_type="user", target_id=user.id)
    db.commit()


# ---- invites (admin only) ---------------------------------------------------------------------


def create_invite(
    db: Session, admin: User, *, role: str = "member", email: str | None = None
) -> tuple[Invite, str]:
    if role not in ("admin", "member"):
        raise AuthError("Role must be admin or member.")
    token = new_token()
    now = utcnow()
    invite = Invite(
        token_hash=hash_token(token),
        role=role,
        email=normalise_email(email) if email else None,
        expires_at=now + timedelta(days=get_settings().invite_days),
        created_by_id=admin.id,
        created_at=now,
    )
    db.add(invite)
    db.flush()
    audit.record(
        db, "invite.created", actor=admin, target_type="invite", target_id=invite.id, meta={"role": role}
    )
    db.commit()
    return invite, token


def peek_invite(db: Session, token: str) -> Invite:
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if not invite:
        raise AuthError("This invite link isn't valid.", 404)
    if invite.used_at:
        raise AuthError("This invite link has already been used.", 410)
    if invite.expires_at <= utcnow():
        raise AuthError("This invite link has expired. Ask for a new one.", 410)
    return invite


def accept_invite(db: Session, token: str, *, email: str, display_name: str, password: str) -> User:
    invite = peek_invite(db, token)
    if invite.email and normalise_email(email) != invite.email:
        raise AuthError("This invite was made for a different email address.", 403)
    # Claim the invite atomically so two browsers can't both use one link.
    now = utcnow()
    claimed = db.execute(
        update(Invite)
        .where(Invite.id == invite.id, Invite.used_at.is_(None), Invite.expires_at > now)
        .values(used_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise AuthError("This invite link has already been used.", 410)
    try:
        user = create_user(db, email=email, display_name=display_name, password=password, role=invite.role)
    except AuthError:
        db.rollback()
        raise
    db.refresh(invite)
    invite.used_by_id = user.id
    audit.record(db, "invite.accepted", actor=user, target_type="invite", target_id=invite.id)
    db.commit()
    return user


# ---- password resets (admin-issued links) ----------------------------------------------------------


def create_reset(db: Session, admin: User, user: User) -> tuple[PasswordReset, str]:
    token = new_token()
    now = utcnow()
    reset = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(hours=get_settings().reset_hours),
        created_by_id=admin.id,
        created_at=now,
    )
    db.add(reset)
    db.flush()
    audit.record(db, "reset.created", actor=admin, target_type="user", target_id=user.id)
    db.commit()
    return reset, token


def use_reset(db: Session, token: str, new_password: str) -> User:
    reset = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(token)))
    if not reset or reset.used_at or reset.expires_at <= utcnow():
        raise AuthError("This reset link isn't valid any more. Ask the admin for a new one.", 410)
    user = db.get(User, reset.user_id)
    if not user or not user.is_active:
        raise AuthError("This account is deactivated.", 403)
    # Claim the link atomically so two browsers can't both use it.
    now = utcnow()
    claimed = db.execute(
        update(PasswordReset)
        .where(PasswordReset.id == reset.id, PasswordReset.used_at.is_(None), PasswordReset.expires_at > now)
        .values(used_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise AuthError("This reset link isn't valid any more. Ask the admin for a new one.", 410)
    try:
        set_password(db, user, new_password, actor=user)
    except AuthError:
        db.rollback()
        raise
    audit.record(db, "reset.used", actor=user, target_type="user", target_id=user.id)
    db.commit()
    return user


# ---- admin: roles and status ------------------------------------------------------------------------


def set_role(db: Session, admin: User, user: User, role: str) -> None:
    if role not in ("admin", "member"):
        raise AuthError("Role must be admin or member.")
    if user.id == admin.id and role != "admin":
        raise AuthError("You can't remove your own admin role.", 409)
    user.role = role
    audit.record(
        db, "user.role_changed", actor=admin, target_type="user", target_id=user.id, meta={"role": role}
    )
    db.commit()


def set_status(db: Session, admin: User, user: User, status: str) -> None:
    """F6: never delete. Deactivating signs the user out everywhere; their work stays visible."""
    if status not in ("active", "deactivated"):
        raise AuthError("Status must be active or deactivated.")
    if user.id == admin.id and status == "deactivated":
        raise AuthError("You can't deactivate yourself.", 409)
    user.status = status
    if status == "deactivated":
        revoke_all_sessions(db, user)
    audit.record(db, f"user.{status}", actor=admin, target_type="user", target_id=user.id)
    db.commit()


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))
