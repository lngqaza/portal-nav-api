"""API key and admin token validation."""
from core.config import settings


def validate_api_key(headers: dict) -> str:
    key = headers.get("x-api-key", "")
    if not key or key not in settings.API_KEYS:
        raise PermissionError("Invalid or missing API key")
    return key


def validate_admin_token(headers: dict) -> str:
    auth = headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token or token != settings.ADMIN_TOKEN:
        raise PermissionError("Invalid or missing admin token")
    return token
