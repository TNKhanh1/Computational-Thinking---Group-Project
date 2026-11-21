"""
Verification tests for P3.1: Multi-Tenant Auth (HS256 JWT), SQLite User Isolation,
SMARTSCHEDULE_AUTH_REQUIRED enforcement, and CORS Allowed Origins.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from web.api import app
from web.auth import get_allowed_origins


def test_auth_register_login_me_and_duplicate_rejection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "auth_test.db"))
    monkeypatch.setenv("SMARTSCHEDULE_SECRET_KEY", "unit-test-secret-key-p31")
    client = TestClient(app)

    r_reg = client.post(
        "/api/auth/register",
        json={"email": "alice@student.hcmus.edu.vn", "password": "secret123", "display_name": "Alice"},
    )
    assert r_reg.status_code == 200
    reg_data = r_reg.json()
    assert reg_data["token_type"] == "bearer"
    assert reg_data["workspace_id"].startswith("user:usr_")
    token = reg_data["access_token"]

    # Duplicate registration must return 409
    r_dup = client.post(
        "/api/auth/register",
        json={"email": "ALICE@student.hcmus.edu.vn", "password": "secret123"},
    )
    assert r_dup.status_code == 409

    # Wrong password -> 401
    r_bad = client.post(
        "/api/auth/login",
        json={"email": "alice@student.hcmus.edu.vn", "password": "wrongpassword"},
    )
    assert r_bad.status_code == 401

    # Valid login + /api/auth/me
    r_login = client.post(
        "/api/auth/login",
        json={"email": "alice@student.hcmus.edu.vn", "password": "secret123"},
    )
    assert r_login.status_code == 200
    r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    assert r_me.json()["user"]["email"] == "alice@student.hcmus.edu.vn"
    assert r_me.json()["workspace_id"] == reg_data["workspace_id"]


def test_multitenant_workspace_and_telemetry_isolation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "tenant_isolation.db"))
    monkeypatch.setenv("SMARTSCHEDULE_SECRET_KEY", "unit-test-secret-key-p31")
    client = TestClient(app)

    alice = client.post("/api/auth/register", json={"email": "a@hcmus.edu.vn", "password": "passwordA"}).json()
    bob = client.post("/api/auth/register", json={"email": "b@hcmus.edu.vn", "password": "passwordB"}).json()
    hdr_a = {"Authorization": f"Bearer {alice['access_token']}"}
    hdr_b = {"Authorization": f"Bearer {bob['access_token']}"}

    # Alice saves state & completion log
    r_put_a = client.put("/api/state", json={"state": {"owner": "alice", "tasks": ["A1"]}}, headers=hdr_a)
    assert r_put_a.status_code == 200
    assert r_put_a.json()["workspace_id"] == alice["workspace_id"]

    r_comp_a = client.post(
        "/api/tasks/complete",
        json={"task_id": "A1", "category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 75},
        headers=hdr_a,
    )
    assert r_comp_a.status_code == 200

    # Bob tries to spoof Alice's workspace_id in query/body -> must remain strictly isolated to Bob
    r_get_b = client.get(f"/api/state?workspace_id={alice['workspace_id']}", headers=hdr_b)
    assert r_get_b.status_code == 200
    assert r_get_b.json()["exists"] is False
    assert r_get_b.json()["workspace_id"] == bob["workspace_id"]

    r_logs_b = client.get(f"/api/tasks/completions?workspace_id={alice['workspace_id']}", headers=hdr_b)
    assert r_logs_b.status_code == 200
    assert r_logs_b.json()["completions"] == []
    assert r_logs_b.json()["workspace_id"] == bob["workspace_id"]

    # Alice still sees her own data
    r_get_a = client.get("/api/state", headers=hdr_a)
    assert r_get_a.status_code == 200
    assert r_get_a.json()["exists"] is True
    assert r_get_a.json()["state"]["owner"] == "alice"


def test_auth_required_flag_and_cors_origins(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "auth_req.db"))
    monkeypatch.setenv("SMARTSCHEDULE_AUTH_REQUIRED", "true")
    monkeypatch.setenv("SMARTSCHEDULE_ALLOWED_ORIGINS", "https://app.smartschedule.edu.vn, http://localhost:3000")
    client = TestClient(app)

    assert get_allowed_origins() == ["https://app.smartschedule.edu.vn", "http://localhost:3000"]

    # Unauthenticated state/calibration requests must fail with 401 when auth is enforced
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/tasks/calibration").status_code == 401

    # Authenticated user succeeds
    user = client.post("/api/auth/register", json={"email": "c@hcmus.edu.vn", "password": "passwordC"}).json()
    hdr = {"Authorization": f"Bearer {user['access_token']}"}
    assert client.get("/api/state", headers=hdr).status_code == 200
    assert client.get("/api/tasks/calibration", headers=hdr).status_code == 200
