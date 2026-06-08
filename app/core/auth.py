from fastapi import Header, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security = HTTPBearer()


def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if x_api_key not in settings.api_keys_list():
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def require_admin(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    if credentials.credentials != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return credentials.credentials
