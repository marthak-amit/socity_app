"""JWT helpers, OTP hashing and the signed QR token for passes."""

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

settings = get_settings()
JWT_ALG = "HS256"


# ---------------------------------------------------------------- JWT
def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {"sub": str(user_id), "typ": "access", "iat": _now(), "exp": _now() + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALG), int(ttl.total_seconds())


def create_refresh_token(user_id: uuid.UUID, jti: uuid.UUID, expires_at: datetime) -> str:
    payload = {"sub": str(user_id), "typ": "refresh", "jti": str(jti), "iat": _now(), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALG)


def decode_token(token: str, expected_type: str) -> dict:
    """Raises jwt.PyJWTError on any problem (expired, bad signature, wrong type)."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALG])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# ---------------------------------------------------------------- OTP
def hash_otp(phone: str, code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def generate_otp() -> str:
    if settings.otp_fixed_code and not settings.is_prod:
        return settings.otp_fixed_code
    return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))


# ---------------------------------------------------------------- QR tokens
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    return _b64(hmac.new(settings.qr_secret.encode(), body.encode(), hashlib.sha256).digest())


def make_qr_token(pass_id: uuid.UUID, event_id: uuid.UUID) -> str:
    """`v1.<payload>.<hmac-sha256>`; payload = {p: pass_id, e: event_id, n: nonce}."""
    payload = {"p": str(pass_id), "e": str(event_id), "n": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"v1.{body}.{_sign(body)}"


class InvalidQrToken(Exception):
    pass


def verify_qr_token(token: str) -> dict:
    """Return {pass_id, event_id, nonce} or raise InvalidQrToken. Constant-time signature check."""
    try:
        version, body, sig = token.strip().split(".")
    except ValueError as e:
        raise InvalidQrToken("malformed") from e
    if version != "v1" or not hmac.compare_digest(sig, _sign(body)):
        raise InvalidQrToken("bad signature")
    try:
        payload = json.loads(_unb64(body))
        return {
            "pass_id": uuid.UUID(payload["p"]),
            "event_id": uuid.UUID(payload["e"]),
            "nonce": payload["n"],
        }
    except (ValueError, KeyError, TypeError) as e:
        raise InvalidQrToken("malformed payload") from e


# ---------------------------------------------------------------- misc codes
_UNAMBIGUOUS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def random_code(n: int) -> str:
    return "".join(secrets.choice(_UNAMBIGUOUS) for _ in range(n))
