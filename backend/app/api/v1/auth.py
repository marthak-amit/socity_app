import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import bad_request, too_many, unauthorized
from app.core.phone import normalize_phone
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp,
)
from app.models import OtpCode, RefreshToken, User
from app.schemas.auth import OtpRequest, OtpRequestOut, OtpVerify, RefreshIn, TokenPair
from app.schemas.common import Msg
from app.services.otp import get_otp_provider
from app.services.serializers import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


@router.post("/otp/request", response_model=OtpRequestOut)
async def request_otp(body: OtpRequest, request: Request, session: AsyncSession = Depends(get_session)):
    phone = normalize_phone(body.phone)
    ip = _ip(request)
    limiter.check(f"otp-ip:{ip}", settings.otp_per_ip_per_hour, 3600)

    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)
    recent = (
        await session.execute(
            select(func.count(), func.max(OtpCode.created_at)).where(
                OtpCode.phone == phone, OtpCode.created_at > hour_ago
            )
        )
    ).one()
    count, last = recent
    if last is not None:
        wait = settings.otp_resend_cooldown_seconds - (now - last).total_seconds()
        if wait > 0:
            raise too_many("otp_cooldown", f"Wait {int(wait) + 1}s before requesting another code",
                           retry_after_seconds=int(wait) + 1)
    if count >= settings.otp_per_phone_per_hour:
        raise too_many("otp_rate_limited", "Too many codes requested for this number. Try again in an hour.")

    code = generate_otp()
    session.add(
        OtpCode(
            phone=phone, code_hash=hash_otp(phone, code), ip=ip,
            expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        )
    )
    await session.flush()
    await get_otp_provider().send(phone, code)
    return OtpRequestOut(
        retry_after_seconds=settings.otp_resend_cooldown_seconds,
        dev_otp=code if (settings.otp_dev_echo and not settings.is_prod) else None,
    )


async def _issue_tokens(session: AsyncSession, user: User, is_new: bool) -> TokenPair:
    jti = uuid.uuid4()
    expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
    session.add(RefreshToken(id=jti, user_id=user.id, expires_at=expires))
    access, ttl = create_access_token(user.id)
    return TokenPair(
        access_token=access, refresh_token=create_refresh_token(user.id, jti, expires),
        expires_in=ttl, user=user_out(user), is_new_user=is_new,
    )


@router.post("/otp/verify", response_model=TokenPair)
async def verify_otp(body: OtpVerify, request: Request, session: AsyncSession = Depends(get_session)):
    phone = normalize_phone(body.phone)
    limiter.check(f"otp-verify-ip:{_ip(request)}", 60, 3600)
    now = datetime.now(UTC)
    otp = await session.scalar(
        select(OtpCode)
        .where(OtpCode.phone == phone, OtpCode.consumed_at.is_(None), OtpCode.expires_at > now)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if otp is None:
        raise bad_request("otp_invalid", "Code expired or not requested")
    if otp.attempts >= settings.otp_max_attempts:
        raise too_many("otp_attempts_exceeded", "Too many wrong attempts. Request a new code.")
    otp.attempts += 1
    if otp.code_hash != hash_otp(phone, body.code):
        # Persist the attempt counter even though we raise.
        await session.commit()
        raise bad_request("otp_invalid", "Incorrect code")
    otp.consumed_at = now

    user = await session.scalar(select(User).where(User.phone == phone))
    is_new = user is None
    if is_new:
        user = User(phone=phone, is_super_admin=phone in settings.super_admin_phone_list)
        session.add(user)
        await session.flush()
    user.last_login_at = now
    return await _issue_tokens(session, user, is_new)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, session: AsyncSession = Depends(get_session)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
        jti, user_id = uuid.UUID(payload["jti"]), uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise unauthorized("invalid_token", "Invalid or expired refresh token") from e
    row = await session.scalar(select(RefreshToken).where(RefreshToken.id == jti).with_for_update())
    if row is None or row.user_id != user_id:
        raise unauthorized("invalid_token", "Unknown refresh token")
    if row.revoked_at is not None:
        # A rotated token was replayed → assume theft, kill every session of this user.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await session.commit()
        raise unauthorized("token_reused", "Refresh token already used; please sign in again")
    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized("invalid_token", "User no longer exists")
    row.revoked_at = datetime.now(UTC)
    return await _issue_tokens(session, user, False)


@router.post("/logout", response_model=Msg)
async def logout(body: RefreshIn, session: AsyncSession = Depends(get_session)):
    try:
        jti = uuid.UUID(decode_token(body.refresh_token, "refresh")["jti"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return Msg()
    await session.execute(
        update(RefreshToken).where(RefreshToken.id == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return Msg()
