"""End-to-end webhook tests against the FastAPI app in paper mode."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from bot.config import AccountConfig, Config, RiskConfig, SessionConfig
from bot.main import create_app


def make_cfg():
    return Config(
        broker="paper",
        symbol="XAUUSD",
        account=AccountConfig(starting_balance=10000.0),
        risk=RiskConfig(per_trade_risk=0.01, max_open_positions=1, require_stop_loss=True),
        session=SessionConfig(enabled=False),
        webhook_secret="topsecret",
        dashboard_token="dashtoken",
    )


def client(tmp_state=True):
    cfg = make_cfg()
    app = create_app(cfg)
    # Point state at a throwaway file so tests don't touch real state.json.
    if tmp_state:
        from bot.state import BotState
        app.state.state.__dict__["_path"] = Path(tempfile.mkdtemp()) / "state.json"
    return TestClient(app), cfg


def buy_payload(secret="topsecret"):
    return {"secret": secret, "action": "buy", "symbol": "XAUUSD",
            "price": 2000.0, "sl": 1995.0, "tp": 2010.0}


def test_webhook_rejects_bad_secret():
    c, _ = client()
    r = c.post("/webhook", json=buy_payload(secret="wrong"))
    assert r.status_code == 401


def test_webhook_rejects_wrong_symbol():
    c, _ = client()
    p = buy_payload()
    p["symbol"] = "EURUSD"
    r = c.post("/webhook", json=p)
    assert r.status_code == 400


def test_webhook_opens_and_closes_position():
    c, _ = client()
    r = c.post("/webhook", json=buy_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is True
    assert body["qty"] == 20.0

    # Close at a profit of $5/unit * 20 = $100.
    close = {"secret": "topsecret", "action": "close", "symbol": "XAUUSD", "price": 2005.0}
    r2 = c.post("/webhook", json=close)
    assert r2.status_code == 200
    assert abs(r2.json()["pnl"] - 100.0) < 1e-6


def test_status_requires_token():
    c, _ = client()
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", params={"token": "dashtoken"}).status_code == 200


def test_kill_switch_then_arm():
    c, _ = client()
    assert c.post("/api/kill", params={"token": "dashtoken"}).json()["trading_enabled"] is False
    # Entry blocked while halted.
    assert c.post("/webhook", json=buy_payload()).json()["executed"] is False
    assert c.post("/api/arm", params={"token": "dashtoken"}).json()["trading_enabled"] is True
    assert c.post("/webhook", json=buy_payload()).json()["executed"] is True
