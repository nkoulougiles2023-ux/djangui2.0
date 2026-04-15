"""OTP issuing + verification and PIN lockout, backed by Redis."""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from .models import AuditLog, OTPAttempt, User

log = logging.getLogger("djangui.accounts")


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _otp_attempts_key(phone: str) -> str:
    return f"otp_attempts:{phone}"


def _otp_send_key(phone: str) -> str:
    return f"otp_sends:{phone}"


def _pin_fail_key(user_id) -> str:
    return f"pin_fail:{user_id}"


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def issue_otp(phone: str, *, purpose: str = "login", ip: str | None = None) -> str:
    """Return OTP code (6 digits). Hashed copy stored in Redis with TTL."""
    send_key = _otp_send_key(phone)
    sends = cache.get(send_key, 0)
    if sends >= settings.DJANGUI["OTP_MAX_SEND_PER_HOUR"]:
        raise RuntimeError("Trop de demandes OTP. Réessayez plus tard.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(_otp_key(phone), _hash_otp(code), timeout=settings.DJANGUI["OTP_TTL_SECONDS"])
    cache.set(_otp_attempts_key(phone), 0, timeout=settings.DJANGUI["OTP_TTL_SECONDS"])
    cache.set(send_key, sends + 1, timeout=3600)

    OTPAttempt.objects.create(phone=phone, ip=ip, purpose=purpose)
    log.info("otp_issued phone=%s purpose=%s", phone, purpose)
    # TODO: deliver via SMS provider (Africa's Talking etc.)
    return code


def verify_otp(phone: str, code: str) -> bool:
    stored = cache.get(_otp_key(phone))
    if not stored:
        return False
    attempts_key = _otp_attempts_key(phone)
    attempts = cache.get(attempts_key, 0)
    if attempts >= settings.DJANGUI["OTP_MAX_ATTEMPTS"]:
        return False
    if hmac.compare_digest(stored, _hash_otp(code)):
        cache.delete(_otp_key(phone))
        cache.delete(attempts_key)
        return True
    cache.set(attempts_key, attempts + 1, timeout=settings.DJANGUI["OTP_TTL_SECONDS"])
    return False


def register_pin_failure(user: User) -> int:
    """Return the new failure count. Locks for PIN_LOCK_MINUTES after threshold."""
    key = _pin_fail_key(user.id)
    fails = cache.get(key, 0) + 1
    cache.set(key, fails, timeout=settings.DJANGUI["PIN_LOCK_MINUTES"] * 60)
    return fails


def is_pin_locked(user: User) -> bool:
    fails = cache.get(_pin_fail_key(user.id), 0)
    return fails >= settings.DJANGUI["PIN_MAX_ATTEMPTS"]


def clear_pin_failures(user: User) -> None:
    cache.delete(_pin_fail_key(user.id))


def audit(user, action, request=None, **details):
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        ip=request.META.get("REMOTE_ADDR") if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
        details=details,
    )
