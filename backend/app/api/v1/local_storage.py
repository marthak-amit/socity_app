"""Dev/test-only endpoints that emulate presigned S3 URLs on the local filesystem backend."""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from app.services.storage import LocalStorage, get_storage, is_private

router = APIRouter(prefix="/_local-storage", tags=["local-storage"], include_in_schema=False)


def _store() -> LocalStorage:
    s = get_storage()
    assert isinstance(s, LocalStorage)
    return s


@router.put("/upload")
async def upload(request: Request, key: str = Query(...), exp: int = Query(...), sig: str = Query(...)):
    store = _store()
    if not store.verify("put", key, exp, sig):
        raise HTTPException(403, "bad signature")
    body = await request.body()
    await store.put_object(key, body, request.headers.get("content-type", "application/octet-stream"))
    return Response(status_code=200)


@router.get("/private")
async def private_get(key: str = Query(...), exp: int = Query(...), sig: str = Query(...)):
    store = _store()
    if not store.verify("get", key, exp, sig) or not is_private(key):
        raise HTTPException(403, "bad signature")
    path = store.path_for(key)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"})


@router.get("/files/{key:path}")
async def public_get(key: str):
    store = _store()
    if is_private(key):
        raise HTTPException(403)
    path = store.path_for(key)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000"})
