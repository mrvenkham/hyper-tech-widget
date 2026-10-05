"""FastAPI application: TradingView webhook, control API, and dashboard."""

from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .brokers import make_broker
from .config import Config, load_config
from .models import Action, Signal
from .notifier import Notifier
from .risk import RiskManager
from .state import BotState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("bot")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    state = BotState(cfg.account.starting_balance)
    broker = make_broker(cfg, state)
    risk = RiskManager(cfg, state)
    notifier = Notifier(cfg)

    app = FastAPI(title="Gold Scalper Bot", version="1.0.0")
    app.state.cfg = cfg
    app.state.state = state
    app.state.broker = broker
    app.state.risk = risk

    def require_token(token: str = Query(default="")) -> None:
        # Constant-time comparison; empty configured token means "open" only in
        # paper mode so local testing is painless.
        expected = cfg.dashboard_token
        if not expected:
            if cfg.broker != "paper":
                raise HTTPException(503, "DASHBOARD_TOKEN must be set for a live broker")
            return
        if not hmac.compare_digest(token, expected):
            raise HTTPException(401, "invalid or missing token")

    # --- webhook from TradingView ---
    @app.post("/webhook")
    async def webhook(request: Request):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(400, "body is not valid JSON")

        try:
            signal = Signal(**payload)
        except Exception as exc:
            raise HTTPException(422, f"invalid signal: {exc}")

        if not cfg.webhook_secret or not hmac.compare_digest(signal.secret, cfg.webhook_secret):
            log.warning("rejected webhook with bad secret")
            raise HTTPException(401, "bad secret")

        if signal.symbol != cfg.symbol:
            raise HTTPException(400, f"symbol {signal.symbol} != configured {cfg.symbol}")

        result = _handle_signal(cfg, state, broker, risk, signal)
        if result.get("executed"):
            await notifier.send(_format_alert(signal, result))
        return JSONResponse(result)

    # --- control API (token-protected) ---
    @app.get("/api/status", dependencies=[Depends(require_token)])
    def status():
        state.roll_day_if_needed()
        positions = [p.model_dump() for p in broker.open_positions()]
        return {
            "broker": broker.name,
            "symbol": cfg.symbol,
            "trading_enabled": state.trading_enabled,
            "daily_loss_breached": risk.daily_loss_breached(),
            "open_positions": positions,
            "state": state.to_dict(),
            "config": {
                "per_trade_risk": cfg.risk.per_trade_risk,
                "daily_loss_limit": cfg.risk.daily_loss_limit,
                "max_open_positions": cfg.risk.max_open_positions,
                "refresh": cfg.dashboard_refresh_seconds,
            },
        }

    @app.post("/api/kill", dependencies=[Depends(require_token)])
    def kill(price: float = Query(default=0.0)):
        pnl = broker.close_all(price) if price > 0 else 0.0
        state.set_trading_enabled(False, "kill switch")
        return {"ok": True, "flattened_pnl": pnl, "trading_enabled": False}

    @app.post("/api/arm", dependencies=[Depends(require_token)])
    def arm():
        state.set_trading_enabled(True, "manual arm")
        return {"ok": True, "trading_enabled": True}

    @app.post("/api/flat", dependencies=[Depends(require_token)])
    def flat(price: float = Query(default=0.0)):
        pnl = broker.close_all(price)
        return {"ok": True, "flattened_pnl": pnl}

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # --- dashboard ---
    @app.get("/", response_class=HTMLResponse)
    def dashboard(token: str = Query(default="")):
        # The page itself is public HTML; it calls the token-protected API with
        # the token from the URL. Serving the shell without a token is harmless.
        html = (WEB_DIR / "dashboard.html").read_text()
        return HTMLResponse(html)

    return app


def _handle_signal(cfg, state, broker, risk, signal: Signal) -> dict:
    open_positions = broker.open_positions()
    decision = risk.evaluate(signal, len(open_positions))

    if signal.action in (Action.CLOSE, Action.FLAT):
        price = signal.price or 0.0
        pnl = broker.close_all(price) if price > 0 else 0.0
        return {"executed": True, "action": signal.action.value, "pnl": pnl, "reason": "closed"}

    if not decision.allowed:
        log.info("signal rejected: %s", decision.reason)
        return {"executed": False, "reason": decision.reason}

    side = "long" if signal.action == Action.BUY else "short"
    pos = broker.open_position(
        symbol=signal.symbol,
        side=side,
        qty=decision.qty,
        price=signal.price,
        sl=decision.sl,
        tp=decision.tp,
        comment=signal.comment,
    )
    return {
        "executed": True,
        "action": signal.action.value,
        "position_id": pos.id,
        "qty": pos.qty,
        "entry": pos.entry_price,
        "sl": pos.sl,
        "tp": pos.tp,
    }


def _format_alert(signal: Signal, result: dict) -> str:
    if result.get("action") in ("close", "flat"):
        return f"\U0001f4b0 Closed {signal.symbol}. PnL {result.get('pnl', 0):.2f}"
    return (
        f"\U0001f4c8 {result.get('action', '').upper()} {signal.symbol} "
        f"qty {result.get('qty')} @ {result.get('entry')} "
        f"SL {result.get('sl')} TP {result.get('tp')}"
    )


app = create_app()


def main() -> None:
    import uvicorn

    cfg = app.state.cfg
    log.info("Starting Gold Scalper Bot: broker=%s symbol=%s", cfg.broker, cfg.symbol)
    if cfg.broker == "paper":
        log.info("PAPER MODE — no real orders will be placed.")
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
