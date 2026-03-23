# tests/test_web_server.py
import os

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import web_server.web_server as ws
from src.config import Config


@pytest.fixture
def client(tmp_path):
    cfg_path = str(tmp_path / "config.json")
    cfg = Config(cfg_path)
    ws.init(cfg, lambda: "IDLE")
    ws.app.config["TESTING"] = True
    return ws.app.test_client(), cfg


def test_dashboard_returns_200(client):
    c, _ = client
    resp = c.get("/")
    assert resp.status_code == 200
    assert b"INTERCOM BRIDGE" in resp.data


def test_api_status(client):
    c, _ = client
    resp = c.get("/api/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["state"] == "IDLE"
    assert data["operation_mode"] == "dynamic"


def test_api_config_get(client):
    c, cfg = client
    resp = c.get("/api/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["operation_mode"] == "dynamic"
    assert data["hold_time_ms"] == 3000
    assert "profiles" in data


def test_api_config_post_mode(client):
    c, cfg = client
    resp = c.post("/api/config", json={"operation_mode": "latch"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert cfg.operation_mode == "latch"


def test_api_config_post_hold_time(client):
    c, cfg = client
    resp = c.post("/api/config", json={"hold_time_ms": 5000})
    assert resp.status_code == 200
    assert cfg.hold_time_ms == 5000


def test_api_config_post_invalid_mode_ignored(client):
    c, cfg = client
    resp = c.post("/api/config", json={"operation_mode": "invalid_mode"})
    assert resp.status_code == 200
    assert cfg.operation_mode == "dynamic"  # unchanged


def test_chess_page_returns_200(client):
    c, _ = client
    resp = c.get("/chess")
    assert resp.status_code == 200
    assert b"CHESS BASIC" in resp.data


def test_chess_page_has_sse_connect(client):
    c, _ = client
    resp = c.get("/chess")
    assert b"chess/events" in resp.data


def test_notify_chess_exit_puts_to_listeners():
    q_mock = ws.queue.SimpleQueue()
    ws._chess_event_listeners.append(q_mock)
    try:
        ws.notify_chess_exit()
        assert q_mock.get_nowait() == "EXIT"
    finally:
        ws._chess_event_listeners.remove(q_mock)
