import os, time, math
import pandas as pd
import numpy as np
import ccxt
from flask import Flask, jsonify, request, redirect, render_template_string
from threading import Thread
from datetime import datetime, timezone
from dotenv import load_dotenv
from resilience import CircuitBreaker, retry

load_dotenv()

# Config
SYMBOL       = "DOGE/USDT:USDT"
INTERVAL     = "15m"
MARKET_TYPE  = "swap"
LEVERAGE     = 10
RISK_ALLOC   = 0.60
TRADE_MODE   = os.getenv("TRADE_MODE","live")

# App
app = Flask(__name__)
from indicators_dashboard import register_metrics
register_metrics(app)
from log_metrics_plus import start_metrics_logger_plus, print_snapshot_plus

# State
total_trades=successful_trades=failed_trades=0
compound_profit=0.0
position_open=False; position_side="N/A"
entry_price=tp1_price=tp2_price=sl_price=current_pnl=0.0
current_price=0.0; update_time=""
rsi_value=adx_value=ema_200_value=current_atr=0.0
price_range_value=None; bb_width=None; supertrend_dir_value=None
ema20_value=None; ema50_value=None
trailing_active=False
cached_balance=None
metrics_started=False
cooldown_until=0.0; cooldown_reason=""
anti_reentry_until=0.0
daily_trade_count=0; current_day=None
CB_ohlcv = CircuitBreaker(5, 60)
CB_balance = CircuitBreaker(5, 60)
CB_order = CircuitBreaker(3, 120)

# Try to load user core AS-IS
HAVE_CORE=False
try:
    import bot_core as CORE
    HAVE_CORE=True
except Exception:
    CORE=None

def log(m): print(m, flush=True)
def keys_missing(): return not (os.getenv("BINGX_API_KEY") and os.getenv("BINGX_API_SECRET"))
def safe_df(df): return isinstance(df, pd.DataFrame) and len(df)>0
def utc_ts(): return time.time()
def day_key(ts): return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

def reset_daily_if_needed():
    global daily_trade_count, current_day
    d = day_key(utc_ts())
    if current_day is None or d != current_day:
        daily_trade_count = 0; current_day = d; log(f"[daily] reset for {d}")

# Fallback exchange if needed
def _build_ex():
    return ccxt.bingx({
        'apiKey': os.getenv("BINGX_API_KEY",""),
        'secret': os.getenv("BINGX_API_SECRET",""),
        'enableRateLimit': True,
        'options': {'defaultType': MARKET_TYPE, 'defaultMarginMode':'isolated'},
    })
exchange = _build_ex()

# ---- Core adapters (no modification to user's functions) ----
@retry(tries=3, delay=0.5, backoff=2.0)
def core_fetch_ohlcv(symbol, timeframe, limit=500):
    if HAVE_CORE and hasattr(CORE,'fetch_ohlcv'): return CORE.fetch_ohlcv(symbol, timeframe, limit)
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

@retry(tries=3, delay=0.5, backoff=2.0)
def core_fetch_balance():
    if HAVE_CORE and hasattr(CORE,'fetch_balance'): return CORE.fetch_balance({'type':'swap'})
    return exchange.fetch_balance(params={'type':'swap'})

@retry(tries=2, delay=0.5, backoff=2.0)
def core_create_order(symbol, side, amount, price=None):
    if HAVE_CORE and hasattr(CORE,'create_order'):
        return CORE.create_order(symbol=symbol, type='market', side='buy' if side=='long' else 'sell', amount=amount, params={'reduceOnly': False})
    return exchange.create_order(symbol, type='market', side='buy' if side=='long' else 'sell', amount=amount, params={'reduceOnly': False})

def core_set_leverage(leverage):
    try:
        if HAVE_CORE and hasattr(CORE,'set_leverage'): return CORE.set_leverage(leverage, SYMBOL, params={'marginMode':'isolated'})
        return exchange.set_leverage(leverage, SYMBOL, params={'marginMode':'isolated'})
    except Exception as e:
        log(f"leverage warn: {e}")

# ---- Data / Indicators ----
def get_klines():
    try:
        if not CB_ohlcv.allow(): 
            time.sleep(2); return pd.DataFrame()
        ohlcv = core_fetch_ohlcv(SYMBOL, INTERVAL, 500)
        CB_ohlcv.on_success()
        df = pd.DataFrame(ohlcv, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna().reset_index(drop=True)
    except Exception as e:
        CB_ohlcv.on_failure()
        log(f"get_klines error: {e}")
        return pd.DataFrame()

def compute_indicators(df: pd.DataFrame):
    global rsi_value, adx_value, ema_200_value, current_atr, current_price
    global price_range_value, supertrend_dir_value, ema20_value, ema50_value, update_time, bb_width
    import ta
    close=df["close"]; high=df["high"]; low=df["low"]
    rsi=ta.momentum.RSIIndicator(close=close, window=14).rsi(); rsi_value=float(rsi.iloc[-2]) if len(rsi)>=2 else 0.0
    adx=ta.trend.ADXIndicator(high=high, low=low, close=close, window=14).adx(); adx_value=float(adx.iloc[-1]) if len(adx) else 0.0
    ema200=ta.trend.EMAIndicator(close=close, window=200).ema_indicator(); ema_200_value=float(ema200.iloc[-1]) if len(ema200) else 0.0
    ema20=ta.trend.EMAIndicator(close=close, window=20).ema_indicator(); ema50=ta.trend.EMAIndicator(close=close, window=50).ema_indicator()
    ema20_value=float(ema20.iloc[-1]) if len(ema20) else None; ema50_value=float(ema50.iloc[-1]) if len(ema50) else None
    atr=ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range(); current_atr=float(atr.iloc[-1]) if len(atr) else 0.0
    # BB width %
    bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    bb_width = float(((bb.bollinger_hband() - bb.bollinger_lband()) / close).iloc[-1]*100.0)
    current_price=float(close.iloc[-1])
    price_range_value=float((high.iloc[-1]-low.iloc[-1]) / max(low.iloc[-1],1e-9) * 100.0)
    supertrend_dir_value= 1 if close.iloc[-1] > ema200.iloc[-1] else -1
    update_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    get_balance()

def spike_filter(df: pd.DataFrame)->bool:
    last = df.tail(1).iloc[0]
    body = abs(last['close']-last['open'])
    wick = (last['high']-last['low'])
    return wick > 4*max(body, 1e-9)

def explosion_filter()->bool:
    if price_range_value and price_range_value > 3.0: return True
    if bb_width and bb_width > 3.5: return True
    return False

# ---- Balance & sizing ----
def get_balance():
    global cached_balance
    try:
        if not CB_balance.allow(): return cached_balance
        bal = core_fetch_balance()
        CB_balance.on_success()
        total=None
        if isinstance(bal, dict) and 'USDT' in bal.get('total', {}): total=float(bal['total']['USDT'])
        cached_balance=total; return total
    except Exception as e:
        CB_balance.on_failure()
        log(f"balance error: {e}"); return cached_balance

def calc_qty(price: float):
    bal = get_balance() or 0.0
    nominal = bal * RISK_ALLOC * LEVERAGE
    return max(nominal / max(price,1e-9), 0.0)

# ---- Signals (entry/exit are authorizable; SL/TP handled by your core if it supports it) ----
def signal(df: pd.DataFrame):
    if adx_value < 15: return None, "adx_low"
    if spike_filter(df): return None, "spike"
    if explosion_filter(): return None, "explosion"
    if ema20_value is None or ema50_value is None: return None, "no_ema"
    trend = "long" if supertrend_dir_value>0 else "short"
    if trend=="long" and ema20_value>ema50_value and rsi_value<70:
        return "long", "ema20>ema50 & rsi<70 & uptrend"
    if trend=="short" and ema20_value<ema50_value and rsi_value>30:
        return "short", "ema20<ema50 & rsi>30 & downtrend"
    return None, "no_setup"

# ---- Orders ----
def place_order(side: str, qty: float, price: float):
    global total_trades, position_open, position_side, entry_price
    if qty <= 0:
        log("qty<=0"); return None
    if not CB_order.allow():
        log("[circuit] orders blocked temporarily"); return None
    try:
        core_set_leverage(LEVERAGE)
        core_create_order(SYMBOL, side, qty, price)
        total_trades += 1; position_open=True; position_side=side; entry_price=price
        log(f"[entry] {side} qty={qty:.4f} @≈{price:.6f}")
        CB_order.on_success()
        return True
    except Exception as e:
        CB_order.on_failure()
        log(f"order error: {e}")
        return None

def update_pnl():
    global current_pnl
    if not position_open: current_pnl=0.0; return
    bal = get_balance() or 0.0
    nominal = bal * RISK_ALLOC * LEVERAGE
    delta = (current_price - entry_price) if position_side=="long" else (entry_price - current_price)
    current_pnl = nominal * (delta / max(entry_price,1e-9))

def close_position():
    global position_open, position_side, entry_price, tp1_price, tp2_price, sl_price, current_pnl, trailing_active
    position_open=False; position_side="N/A"; entry_price=tp1_price=tp2_price=sl_price=current_pnl=0.0; trailing_active=False

# ---- Main loop with watchdog/backoff ----
def main_loop():
    global metrics_started
    backoff=5
    while True:
        try:
            if keys_missing():
                time.sleep(3); continue
            reset_daily_if_needed()
            df=get_klines()
            if not safe_df(df):
                log("No market data, retry")
                time.sleep(backoff); backoff=min(backoff*2,60); continue
            backoff=5
            compute_indicators(df)
            price = float(df['close'].iloc[-1])
            if not position_open:
                sig, why = signal(df)
                if sig:
                    qty = calc_qty(price)
                    place_order(sig, qty, price)
                    log(f"signal={sig} reason={why} qty={qty:.4f}")
            else:
                update_pnl()
            if not metrics_started:
                try: start_metrics_logger_plus(30); print_snapshot_plus(); metrics_started=True
                except Exception as e: log(f"[metrics] start err: {e}")
            time.sleep(10)
        except Exception as e:
            log(f"[loop] error: {e}")
            time.sleep(5)

def keep_alive():
    while True:
        try:
            url=os.getenv("RENDER_EXTERNAL_URL") or ""
            if url:
                import requests as R; R.get(url, timeout=5); log("Keep-alive ping sent")
        except Exception: pass
        time.sleep(60)

# Routes
SETUP_HTML = """<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Setup BingX Futures</title></head><body style="font-family:system-ui;margin:24px">
<h2>🔐 Setup (Pro, Live)</h2>
<form method="POST">
<label>BingX API Key</label><br><input name="BINGX_API_KEY" style="width:420px" required /><br><br>
<label>BingX API Secret</label><br><input name="BINGX_API_SECRET" style="width:420px" required /><br><br>
<label>Mode</label><br>
<select name="TRADE_MODE" style="width:420px">
  <option value="live" selected>live</option>
  <option value="paper">paper</option>
</select><br><br>
<label>BingX GA (optional)</label><br><input name="BINGX_GA" style="width:420px" /><br><br>
<button type="submit">Save</button>
</form>
<p>لو أضفت <b>bot_core.py</b> (دوالك الأساسية) في الجذر، هنستخدمها كما هي بدون أي تعديل.</p>
</body></html>"""

@app.route("/", methods=["GET"])
def home():
    if keys_missing(): return redirect("/setup")
    return jsonify(status="ok", mode=TRADE_MODE, core=HAVE_CORE, tf=INTERVAL)

@app.route("/health")
def health(): return jsonify(ok=True, ts=datetime.utcnow().isoformat()+"Z")

@app.route("/setup", methods=["GET","POST"])
def setup():
    global TRADE_MODE
    if request.method=="POST":
        k = request.form.get("BINGX_API_KEY","").strip()
        s = request.form.get("BINGX_API_SECRET","").strip()
        m = request.form.get("TRADE_MODE","live").strip()
        g = request.form.get("BINGX_GA","").strip()
        if not k or not s: return "Missing key/secret", 400
        with open(".env","w") as f:
            f.write(f"BINGX_API_KEY={k}\nBINGX_API_SECRET={s}\nTRADE_MODE={m}\nBINGX_GA={g}\n")
        os.environ["BINGX_API_KEY"]=k; os.environ["BINGX_API_SECRET"]=s; os.environ["TRADE_MODE"]=m; os.environ["BINGX_GA"]=g
        TRADE_MODE=m
        return redirect("/metrics")
    return render_template_string(SETUP_HTML)

Thread(target=keep_alive, daemon=True).start()
Thread(target=main_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8000)))
