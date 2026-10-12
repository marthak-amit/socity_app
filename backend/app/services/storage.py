"""Object storage abstraction.

Layout: every client upload lands in the *private* bucket under `private/raw/<upload-id>` via a presigned
PUT. The API then validates + re-encodes it (EXIF stripped) and writes the final object, so unvalidated bytes
are never served. Final keys are `public/...` (public bucket, plain URLs) or `private/...` (presigned GET).
"""

import asyncio
import hashlib
import hmac
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@dataclass
class PresignedPut:
    url: str
    method: str = "PUT"
    headers: dict[str, str] = field(default_factory=dict)


def is_private(key: str) -> bool:
    return key.startswith("private/")


class Storage(ABC):
    @abstractmethod
    async def presign_put(self, key: str, content_type: str) -> PresignedPut: ...

    @abstractmethod
    async def put_object(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def get_object(self, key: str) -> bytes: ...

    @abstractmethod
    async def object_size(self, key: str) -> int | None:
        """Size in bytes, or None if the object doesn't exist."""

    @abstractmethod
    async def delete_object(self, key: str) -> None: ...

    @abstractmethod
    def public_url(self, key: str) -> str: ...

    @abstractmethod
    async def presigned_get(self, key: str, ttl: int | None = None) -> str: ...

    def url_for(self, key: str | None) -> str | None:
        """Public URL for public keys; None for private keys (they need `presigned_get`)."""
        if not key or is_private(key):
            return None
        return self.public_url(key)


# ----------------------------------------------------------------------------- local filesystem (dev/tests)
class LocalStorage(Storage):
    """Filesystem backend served through the API itself — lets the whole stack run without MinIO."""

    def __init__(self, root: str, base_url: str, secret: str) -> None:
        self.root = Path(root).resolve()
        self.base = base_url.rstrip("/") + "/api/v1/_local-storage"
        self.secret = secret.encode()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid key")
        return p

    def sign(self, action: str, key: str, exp: int) -> str:
        return hmac.new(self.secret, f"{action}:{key}:{exp}".encode(), hashlib.sha256).hexdigest()

    def verify(self, action: str, key: str, exp: int, sig: str) -> bool:
        return exp >= time.time() and hmac.compare_digest(sig, self.sign(action, key, exp))

    async def presign_put(self, key: str, content_type: str) -> PresignedPut:
        exp = int(time.time()) + get_settings().presign_put_ttl_seconds
        return PresignedPut(
            url=f"{self.base}/upload?key={key}&exp={exp}&sig={self.sign('put', key, exp)}",
            headers={"Content-Type": content_type},
        )

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        def _w():
            p = self.path_for(key)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)

        await asyncio.to_thread(_w)

    async def get_object(self, key: str) -> bytes:
        return await asyncio.to_thread(self.path_for(key).read_bytes)

    async def object_size(self, key: str) -> int | None:
        p = self.path_for(key)
        return p.stat().st_size if p.is_file() else None

    async def delete_object(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)

    def public_url(self, key: str) -> str:
        return f"{self.base}/files/{key}"

    async def presigned_get(self, key: str, ttl: int | None = None) -> str:
        exp = int(time.time()) + (ttl or get_settings().presign_get_ttl_seconds)
        return f"{self.base}/private?key={key}&exp={exp}&sig={self.sign('get', key, exp)}"

    def wipe(self) -> None:  # tests
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------- S3 / MinIO / R2
class S3Storage(Storage):
    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        s = get_settings()
        self.s = s
        cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})
        common = dict(
            aws_access_key_id=s.s3_access_key, aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region, config=cfg,
        )
        self.client = boto3.client("s3", endpoint_url=s.s3_endpoint_url or None, **common)
        # Presigned URLs must be reachable by the phone → may use a different host than the API's.
        self.signer = boto3.client(
            "s3", endpoint_url=(s.s3_public_endpoint_url or s.s3_endpoint_url) or None, **common
        )

    def _bucket(self, key: str) -> str:
        return self.s.s3_private_bucket if is_private(key) else self.s.s3_public_bucket

    async def presign_put(self, key: str, content_type: str) -> PresignedPut:
        url = self.signer.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket(key), "Key": key, "ContentType": content_type},
            ExpiresIn=self.s.presign_put_ttl_seconds,
        )
        return PresignedPut(url=url, headers={"Content-Type": content_type})

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object, Bucket=self._bucket(key), Key=key, Body=data, ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable" if not is_private(key) else "private",
        )

    async def get_object(self, key: str) -> bytes:
        def _g():
            return self.client.get_object(Bucket=self._bucket(key), Key=key)["Body"].read()

        return await asyncio.to_thread(_g)

    async def object_size(self, key: str) -> int | None:
        from botocore.exceptions import ClientError

        def _h():
            try:
                return self.client.head_object(Bucket=self._bucket(key), Key=key)["ContentLength"]
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                    return None
                raise

        return await asyncio.to_thread(_h)

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self._bucket(key), Key=key)

    def public_url(self, key: str) -> str:
        base = self.s.s3_public_base_url.rstrip("/")
        return f"{base}/{key}"

    async def presigned_get(self, key: str, ttl: int | None = None) -> str:
        return self.signer.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket(key), "Key": key},
            ExpiresIn=ttl or self.s.presign_get_ttl_seconds,
        )


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(s.local_storage_dir, s.api_public_url, s.jwt_secret)
