"""Exercises the real S3Storage code path (MinIO/R2 compatible) against an in-process moto S3 server."""

import boto3
import httpx
import pytest

from app.core.config import get_settings


@pytest.fixture(scope="module")
def s3_server():
    moto_server = pytest.importorskip("moto.server")
    server = moto_server.ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
def s3(s3_server, monkeypatch):
    settings = get_settings()
    for k, v in dict(s3_endpoint_url=s3_server, s3_public_endpoint_url=s3_server, s3_access_key="test", s3_secret_key="test",
                     s3_region="us-east-1", s3_public_bucket="pub", s3_private_bucket="priv",
                     s3_public_base_url=f"{s3_server}/pub").items():
        monkeypatch.setattr(settings, k, v)
    client = boto3.client("s3", endpoint_url=s3_server, aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
    for b in ("pub", "priv"):
        client.create_bucket(Bucket=b)
    client.put_bucket_policy(Bucket="pub", Policy='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::pub/*"}]}')
    from app.services.storage import S3Storage

    return S3Storage()


async def test_presigned_put_validate_and_serve_roundtrip(s3):
    key = "private/raw/abc"
    p = await s3.presign_put(key, "image/png")
    async with httpx.AsyncClient() as c:
        assert (await c.put(p.url, content=b"hello", headers=p.headers)).status_code == 200
    assert await s3.object_size(key) == 5 and await s3.object_size("private/raw/missing") is None
    assert await s3.get_object(key) == b"hello"
    await s3.delete_object(key)
    assert await s3.object_size(key) is None


async def test_public_and_private_buckets(s3):
    await s3.put_object("public/societies/x/gallery/a.jpg", b"pub-bytes", "image/jpeg")
    await s3.put_object("private/societies/x/screenshot/b.jpg", b"priv-bytes", "image/jpeg")
    async with httpx.AsyncClient() as c:
        assert (await c.get(s3.public_url("public/societies/x/gallery/a.jpg"))).content == b"pub-bytes"
        assert s3.url_for("private/societies/x/screenshot/b.jpg") is None
        signed = await s3.presigned_get("private/societies/x/screenshot/b.jpg", ttl=60)
        assert (await c.get(signed)).content == b"priv-bytes"
        # the private bucket has no public policy → unsigned access is denied
        unsigned = signed.split("?")[0]
        assert (await c.get(unsigned)).status_code in (403, 404)
