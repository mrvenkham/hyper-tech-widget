# Gold Scalper Bot

A TradingView-driven automated trading bot for scalping gold (XAUUSD / PAXG).
TradingView produces the signals; this bot receives them by webhook, applies
risk management, and executes orders through a pluggable broker. A phone-friendly
web dashboard lets you watch and control it from a PC or an Android browser.

> **Read this first.** Automated scalping of gold with leverage can lose money
> very quickly. This bot ships in **paper-trading mode by default** so no real
> order is ever placed until you deliberately switch to a live broker and remove
> the safety rails. The bundled strategy is a *starting template*, not a proven
> edge. Backtest and forward-test on a demo account before risking a cent.

## How the pieces fit together

```
  TradingView (Pine strategy + alerts)
        |  HTTPS webhook (JSON, shared secret)
        v
  Gold Scalper Bot  ──►  Risk manager  ──►  Broker (paper by default)
        |
        ├─►  Web dashboard   (open from PC or Android browser)
        └─►  Telegram alerts (optional)
```

TradingView itself does **not** place trades. It evaluates the strategy and, when
a condition triggers, sends an alert to this bot. The bot decides whether the
trade passes your risk rules and then forwards it to a broker.

### Why the engine runs on a PC/VPS, not on the phone

A phone sleeps, drops its network, and kills background apps, so a trading engine
running *on* the phone will miss fills and mismanage stops. Run the bot on an
always-on machine (a home PC left on, or a cheap VPS) and use the dashboard and
Telegram alerts from your phone. That is what "runs on both PC and Android" means
here: one engine, controllable from any device's browser.

## Quick start (paper mode)

```bash
cd gold-scalper-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit WEBHOOK_SECRET and DASHBOARD_TOKEN
python -m bot.main              # starts on http://0.0.0.0:8000
```

Open `http://<machine-ip>:8000/?token=<DASHBOARD_TOKEN>` on your PC or phone.

### One command (bot + public URL for TradingView)

On your own PC or VPS, after creating `.env`:

```bash
./start.sh
```

It starts the bot, opens a public Cloudflare tunnel, and prints the
`.../webhook` URL to paste into TradingView plus the dashboard link. Ctrl-C
stops both. This must run on your machine, not in a throwaway cloud session —
sandboxes block public tunnels.

Run the tests:

```bash
pip install -r requirements.txt
pytest -q
```

## Connecting TradingView

1. Add `strategy/gold_scalper.pine` to a TradingView chart (Pine Editor → paste →
   "Add to chart"). Tune the inputs and backtest it in the Strategy Tester.
2. Create an alert on the strategy. Set the webhook URL to your bot's public
   address: `https://<your-host>/webhook`. (TradingView webhooks require a paid
   TradingView plan and a public HTTPS URL. For local testing use a tunnel such
   as `cloudflared` or `ngrok`.)
3. Paste the alert message exactly as produced by the strategy's `alert()` calls.
   It already contains the shared secret placeholder `__SECRET__` — replace it
   with your `WEBHOOK_SECRET` value, or set the secret in the strategy input.

Example alert payload the bot accepts:

```json
{
  "secret": "your-webhook-secret",
  "action": "buy",
  "symbol": "XAUUSD",
  "price": 2345.6,
  "sl": 2343.1,
  "tp": 2349.0,
  "strategy": "gold_scalper",
  "comment": "ema+rsi pullback"
}
```

`action` is one of `buy`, `sell`, `close`, `flat`.

## Going live (do this slowly)

1. Keep paper mode on for at least a few weeks of real-time forward testing.
2. Implement a real broker in `bot/brokers/` by subclassing `Broker`
   (`bot/brokers/base.py`). `paper.py` is the reference implementation.
   See that file's header for the MetaTrader 5, OANDA, and crypto-exchange notes.
3. Set `broker: <name>` in `config.yaml` and add the broker's API keys to `.env`.
4. Start with the smallest possible position size and the daily loss limit set low.

## Safety features

- **Paper mode default** — no real orders until you change the broker.
- **Per-trade risk cap** and **daily loss limit** — breaches reject new trades.
- **Max concurrent positions** — refuses to over-stack.
- **Kill switch** — one button on the dashboard (and `/api/kill`) flattens and
  halts all trading until re-armed.
- **Shared-secret webhook auth** — alerts without the secret are rejected.
- **Trading-hours filter** — optional session window.

None of these guarantee a profit or prevent a loss. They limit how fast you can
lose. You are responsible for every trade this bot places.

## Project layout

```
gold-scalper-bot/
  bot/
    main.py           FastAPI app: webhook + dashboard + JSON API
    config.py         loads config.yaml and .env
    models.py         signal and state data models
    risk.py           risk manager and kill switch
    state.py          persisted bot state (JSON on disk)
    notifier.py       optional Telegram alerts
    brokers/
      base.py         Broker interface
      paper.py        simulated broker (default)
  strategy/
    gold_scalper.pine TradingView strategy + alerts
  web/
    dashboard.html    mobile-friendly control panel
  tests/              unit tests for risk + webhook
  config.yaml         tunable settings
  .env.example        secrets template
```

## Disclaimer

This software is provided for educational purposes with no warranty. It is not
financial advice. Trading leveraged products carries a high risk of losing money.
Only trade with money you can afford to lose.
