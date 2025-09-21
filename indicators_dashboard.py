from flask import Blueprint, render_template_string, jsonify
import time
bp = Blueprint("metrics", __name__)
def _g(M, n, d=None): return getattr(M, n, d)
def _ctx():
    try: import main as M
    except Exception:
        class X: pass
        M = X()
    return dict(
        total_trades=_g(M,"total_trades",0),
        successful_trades=_g(M,"successful_trades",0),
        failed_trades=_g(M,"failed_trades",0),
        compound_profit=_g(M,"compound_profit",0.0),
        balance=_g(M,"cached_balance",None),
        current_price=_g(M,"current_price",0.0),
        ema200=_g(M,"ema_200_value",0.0),
        ema20=_g(M,"ema20_value",None),
        ema50=_g(M,"ema50_value",None),
        rsi=_g(M,"rsi_value",0.0),
        adx=_g(M,"adx_value",0.0),
        atr=_g(M,"current_atr",0.0),
        range_pct=_g(M,"price_range_value",None),
        bb_width=_g(M,"bb_width",None),
        supertrend=_g(M,"supertrend_dir_value",None),
        cooldown_reason=_g(M,"cooldown_reason",""),
        position_open=bool(_g(M,"position_open",False)),
        position_side=_g(M,"position_side","N/A"),
        entry_price=_g(M,"entry_price",0.0),
        tp1_price=_g(M,"tp1_price",0.0),
        tp2_price=_g(M,"tp2_price",0.0),
        sl_price=_g(M,"sl_price",0.0),
        trailing_active=_g(M,"trailing_active",False),
        pnl=_g(M,"current_pnl",0.0),
        leverage=_g(M,"LEVERAGE",10),
        risk_alloc=_g(M,"RISK_ALLOC",0.6),
        timeframe=_g(M,"INTERVAL","15m"),
        trade_mode=_g(M,"TRADE_MODE","live"),
        update_time=_g(M,"update_time",time.strftime("%Y-%m-%d %H:%M:%S"))
    )
HTML = """<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Metrics</title>
<style>
:root{--bg:#0f172a;--card:#111827;--text:#e5e7eb;--pos:#10b981;--neg:#ef4444;--muted:#9ca3af}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.card{background:var(--card);border-radius:12px;padding:16px}
.k{color:var(--muted);font-size:13px}.v{font-size:28px;font-weight:700}
.pos{color:var(--pos)}.neg{color:var(--neg)}.mono{font-family:ui-monospace,monospace}
.row{display:flex;justify-content:space-between;align-items:center;margin:6px 0}
.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#1f2937;font-size:12px}
.warn{color:#f59e0b}
</style></head><body>
<div class="wrap"><h1>📊 Metrics (Futures 15m – Pro)</h1>
<p class="mono">Lev: {{ leverage }}x • Risk: {{ (risk_alloc*100)|round(0) }}% • TF: {{ timeframe }} • Mode: {{ trade_mode }}</p>
{% if cooldown_reason %}<p class="warn">⏳ Cooldown: {{ cooldown_reason }}</p>{% endif %}
<div class="grid">
<div class="card"><div class="k">Total Trades</div><div class="v">{{ total_trades }}</div>
<div class="row"><span>Wins</span><span class="pill pos">{{ successful_trades }}</span></div>
<div class="row"><span>Losses</span><span class="pill neg">{{ failed_trades }}</span></div></div>
<div class="card"><div class="k">Compound Profit (USDT)</div>
<div class="v {% if compound_profit >= 0 %}pos{% else %}neg{% endif %}">{{ compound_profit|round(4) }}</div>
<div class="k">Balance</div><div class="v mono">{{ balance if balance is not none else "N/A" }}</div></div>
<div class="card"><div class="k">Market</div>
<div class="row"><span>Price</span><span class="mono">{{ current_price|round(6) }}</span></div>
<div class="row"><span>EMA 20 / 50 / 200</span><span class="mono">{{ ema20 if ema20 is not none else "N/A" }} / {{ ema50 if ema50 is not none else "N/A" }} / {{ ema200|round(6) }}</span></div>
<div class="row"><span>RSI / ADX</span><span class="mono">{{ rsi|round(2) }} / {{ adx|round(2) }}</span></div>
<div class="row"><span>ATR</span><span class="mono">{{ atr|round(6) }}</span></div>
<div class="row"><span>Range % / BB width</span><span class="mono">{{ range_pct if range_pct is not none else "N/A" }} / {{ bb_width if bb_width is not none else "N/A" }}</span></div>
<div class="row"><span>Supertrend</span><span class="mono">{% if supertrend is none %}N/A{% elif supertrend>0 %}BULLISH{% else %}BEARISH{% endif %}</span></div></div>
<div class="card"><div class="k">Position</div>
{% if position_open %}<div class="pill pos">ACTIVE</div>
<div class="row"><span>Side</span><span class="mono">{{ position_side }}</span></div>
<div class="row"><span>Entry</span><span class="mono">{{ entry_price|round(6) }}</span></div>
<div class="row"><span>TP1 / TP2 / SL</span><span class="mono">{{ tp1_price|round(6) }} / {{ tp2_price|round(6) }} / {{ sl_price|round(6) }}</span></div>
<div class="row"><span>Trailing</span><span class="mono">{{ 'ON' if trailing_active else 'OFF' }}</span></div>
<div class="row"><span>PnL</span><span class="mono {% if pnl >= 0 %}pos{% else %}neg{% endif %}">{{ pnl|round(4) }}</span></div>
{% else %}<div class="pill">IDLE</div><div class="k">Waiting for signals…</div>{% endif %}
<div class="k" style="margin-top:8px">Last update: {{ update_time }}</div></div>
</div></div></body></html>
"""
@bp.route("/metrics")
def metrics_html(): return render_template_string(HTML, **_ctx())
@bp.route("/metrics/json")
def metrics_json(): return jsonify(_ctx())
def register_metrics(app): app.register_blueprint(bp)
