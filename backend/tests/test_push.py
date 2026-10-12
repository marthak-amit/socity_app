import json

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.models import PushToken
from app.services.push import FcmPushProvider
from tests.helpers import login


def make_service_account(tmp_path) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    path = tmp_path / "sa.json"
    path.write_text(json.dumps({"project_id": "societypass-test", "client_email": "svc@societypass-test.iam.gserviceaccount.com",
                                "private_key": pem, "token_uri": "https://oauth2.googleapis.com/token"}))
    return str(path)


async def test_fcm_v1_payload_and_invalid_token_pruning(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "oauth2.googleapis.com":
            assert b"jwt-bearer" in request.content
            return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3600})
        body = json.loads(request.content)["message"]
        if body["token"] == "dead-token":
            return httpx.Response(404, json={"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}})
        return httpx.Response(200, json={"name": "projects/x/messages/1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = FcmPushProvider(make_service_account(tmp_path), client=client)
        invalid = await provider.send(["good-token", "dead-token"], "Your pass is ready", "Approved", {"type": "order_approved", "n": 3})
    assert invalid == ["dead-token"]
    sends = [c for c in calls if c.url.host == "fcm.googleapis.com"]
    assert len(sends) == 2 and all(c.headers["authorization"] == "Bearer ya29.test" for c in sends)
    assert sends[0].url.path == "/v1/projects/societypass-test/messages:send"
    msg = json.loads(sends[0].content)["message"]
    assert msg["notification"] == {"title": "Your pass is ready", "body": "Approved"}
    assert msg["data"] == {"type": "order_approved", "n": "3"}  # data values stringified for FCM
    # the OAuth token is cached: only one token request for two sends
    assert len([c for c in calls if c.url.host == "oauth2.googleapis.com"]) == 1


async def test_device_token_registration_is_per_user_and_moves_between_users(client):
    from sqlalchemy import select

    from app.core.db import SessionLocal

    a, b = await login(client, "A"), await login(client, "B")
    assert (await a.post("/me/push-tokens", {"token": "fcm-token-123456", "platform": "android"})).status_code == 200
    assert (await b.post("/me/push-tokens", {"token": "fcm-token-123456", "platform": "ios"})).status_code == 200  # same device, new login
    async with SessionLocal() as db:
        rows = (await db.scalars(select(PushToken))).all()
    assert len(rows) == 1 and str(rows[0].user_id) == b.id
    # a user can't unregister someone else's token
    assert (await a.delete("/me/push-tokens", {"token": "fcm-token-123456"})).status_code == 200
    async with SessionLocal() as db:
        assert len((await db.scalars(select(PushToken))).all()) == 1
