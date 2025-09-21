# pro_bingx_futures_pro_final
**Live Futures bot (15m, 60% risk, 10x) with professional protections.**
- Uses your `bot_core.py` (balance/orders/SL/TP...) **AS-IS** if provided.
- Robustness: retries, exponential backoff, circuit breaker, watchdog loop, keep-alive, /health.
- Setup UI: enter keys + mode (default live). Metrics + colored logs.

Deploy on Render:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn fix_bind_port:app --bind 0.0.0.0:$PORT`
- EnvVars ready: `BINGX_API_KEY`, `BINGX_API_SECRET`, `TRADE_MODE`, `BINGX_GA` (optional).

To use your core:
- Add `bot_core.py` in project root. Functions expected (no modification):
  - `fetch_ohlcv(symbol, timeframe, limit)`
  - `fetch_balance(params)`
  - `create_order(symbol, type, side, amount, params)`
  - `set_leverage(leverage, symbol, params)`
