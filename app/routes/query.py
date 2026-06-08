import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.database import get_session
from app.services.query_router import route
import app.services.hot_path as hot_path_service

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def validate_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    if x_api_key not in settings.api_keys_list():
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


class QueryRequest(BaseModel):
    query: str
    context: str = None


class BatchQueryRequest(BaseModel):
    queries: list
    context: str = None


@router.post("")
@limiter.limit("100/minute")
async def query_nav(request: Request, body: QueryRequest, api_key: str = Depends(validate_api_key), session=Depends(get_session)):
    result = await route(body.query, session)
    return JSONResponse(result.dict())


@router.post("/batch")
@limiter.limit("20/minute")
async def batch_query(request: Request, body: BatchQueryRequest, api_key: str = Depends(validate_api_key), session=Depends(get_session)):
    if len(body.queries) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 queries per batch request")
    results = await asyncio.gather(*[route(str(q), session) for q in body.queries])
    return JSONResponse([r.dict() for r in results])


@router.get("/suggest")
async def suggest(q: str = "", session=Depends(get_session)):
    rows = await hot_path_service.get_top_paths(session, limit=50)
    filtered = [
        {"path": r.path, "label": r.label}
        for r in rows
        if q.lower() in r.label.lower()
    ][:5]
    return JSONResponse(filtered)
