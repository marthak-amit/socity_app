import pytest

from app.api.v1 import auth as auth_module
from app.services.otp import ConsoleOtpProvider
from tests.helpers import login, next_phone


async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"


async def test_otp_login_flow_and_me(client):
    a = await login(client, "Asha")
    r = await a.get("/me")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["name"] == "Asha" and body["memberships"] == []
    assert a.tokens["user"]["phone"] == a.phone and a.tokens["is_new_user"] is True


async def test_phone_normalisation_and_second_login_is_same_user(client):
    a = await login(client, "Asha", phone="9876543210")
    assert a.phone == "9876543210"
    assert a.user["phone"] == "+919876543210"
    b = await login(client, None, phone="+919876543210")
    assert b.user["id"] == a.user["id"] and b.tokens["is_new_user"] is False


async def test_invalid_phone_rejected(client):
    r = await client.post("/api/v1/auth/otp/request", json={"phone": "123456"})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_phone"


async def test_wrong_otp_and_attempt_limit(client):
    phone = next_phone()
    await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    for _ in range(5):
        r = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": "000000"})
        assert r.status_code == 400
    good = ConsoleOtpProvider.last_codes[phone]
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": good})
    assert r.status_code == 429  # locked out after 5 wrong attempts even with the right code


async def test_otp_single_use(client):
    phone = next_phone()
    await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    code = ConsoleOtpProvider.last_codes[phone]
    assert (await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})).status_code == 200
    assert (await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})).status_code == 400


async def test_otp_request_rate_limited_per_phone(client, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "otp_per_phone_per_hour", 3)
    phone = next_phone()
    codes = []
    for _ in range(3):
        codes.append((await client.post("/api/v1/auth/otp/request", json={"phone": phone})).status_code)
    r = await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert codes == [200, 200, 200] and r.status_code == 429


async def test_otp_resend_cooldown(client, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "otp_resend_cooldown_seconds", 30)
    phone = next_phone()
    assert (await client.post("/api/v1/auth/otp/request", json={"phone": phone})).status_code == 200
    r = await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "otp_cooldown"


async def test_dev_otp_echo(client, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "otp_dev_echo", True)
    r = await client.post("/api/v1/auth/otp/request", json={"phone": next_phone()})
    assert len(r.json()["dev_otp"]) == 6


async def test_refresh_rotation_and_reuse_detection(client):
    a = await login(client, "Asha")
    old = a.tokens["refresh_token"]
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    # replaying the rotated token is treated as theft: it fails AND revokes the family
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401 and r2.json()["detail"]["code"] == "token_reused"
    r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": new})
    assert r3.status_code == 401


async def test_access_token_cannot_be_used_as_refresh_and_vice_versa(client):
    a = await login(client, "Asha")
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": a.tokens["access_token"]})).status_code == 401
    r = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {a.tokens['refresh_token']}"})
    assert r.status_code == 401


async def test_unauthenticated_requests_rejected(client):
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await client.get("/api/v1/me", headers={"Authorization": "Bearer junk"})).status_code == 401


async def test_logout_revokes_refresh(client):
    a = await login(client, "Asha")
    await client.post("/api/v1/auth/logout", json={"refresh_token": a.tokens["refresh_token"]})
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": a.tokens["refresh_token"]})
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/me", "/societies/00000000-0000-0000-0000-000000000000"])
async def test_protected_paths_need_auth(client, path):
    assert (await client.get(f"/api/v1{path}")).status_code == 401
