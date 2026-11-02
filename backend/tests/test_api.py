import os
from datetime import timedelta

os.environ["DG_DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, utcnow
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def test_incident_correlates_with_recent_deploy(client):
    now = utcnow()
    client.post("/api/deployments", json={
        "service": "checkout", "version": "v1", "commit_sha": "aaaaaaa", "changed_files": ["docs/readme.md"],
        "deployed_at": (now - timedelta(minutes=50)).isoformat()})
    client.post("/api/deployments", json={
        "service": "checkout", "version": "v2", "commit_sha": "bbbbbbb", "changed_files": ["src/payment_gateway.py"],
        "deployed_at": (now - timedelta(minutes=5)).isoformat()})
    logs = [{"service": "checkout", "level": "ERROR", "message": f"payment gateway timeout order {i}"} for i in range(12)]
    r = client.post("/api/logs", json=logs)
    assert r.status_code == 202 and len(r.json()["incidents_opened"]) == 1

    inc = client.get("/api/incidents").json()[0]
    assert inc["top_patterns"][0]["pattern"] == "payment gateway timeout order <n>"
    assert inc["suspects"][0]["deployment"]["version"] == "v2"
    assert inc["suspects"][0]["score"] > inc["suspects"][1]["score"]


def test_below_threshold_no_incident(client):
    r = client.post("/api/logs", json=[{"service": "x", "level": "ERROR", "message": "boom"}])
    assert r.json()["incidents_opened"] == []
