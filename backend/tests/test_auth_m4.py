"""Auth lifecycle: logout and change password invalidate old tokens."""


async def _register(client, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return login.json()["token"]


async def test_logout_invalidates_token(client):
    token = await _register(client, "logout@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get("/api/me", headers=headers)).status_code == 200
    logout = await client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert (await client.get("/api/me", headers=headers)).status_code == 401


async def test_change_password_invalidates_old_token(client):
    token = await _register(client, "change@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    wrong = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "wrong-password", "new_password": "newpassword123"},
    )
    assert wrong.status_code == 400

    changed = await client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "password123", "new_password": "newpassword123"},
    )
    assert changed.status_code == 200
    assert (await client.get("/api/me", headers=headers)).status_code == 401

    login = await client.post(
        "/api/auth/login", json={"email": "change@example.com", "password": "newpassword123"}
    )
    assert login.status_code == 200
