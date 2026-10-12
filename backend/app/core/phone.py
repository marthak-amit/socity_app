import phonenumbers

from app.core.config import get_settings
from app.core.errors import bad_request


def normalize_phone(raw: str) -> str:
    """Return E.164. Bare 10-digit numbers get the default country code (+91)."""
    raw = raw.strip()
    default_region = phonenumbers.region_code_for_country_code(
        int(get_settings().default_country_code.lstrip("+"))
    )
    try:
        num = phonenumbers.parse(raw, None if raw.startswith("+") else default_region)
    except phonenumbers.NumberParseException as e:
        raise bad_request("invalid_phone", "Enter a valid phone number") from e
    if not phonenumbers.is_valid_number(num):
        raise bad_request("invalid_phone", "Enter a valid phone number")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def try_normalize_phone(raw: str) -> str | None:
    try:
        return normalize_phone(raw)
    except Exception:
        return None
