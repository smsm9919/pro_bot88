import time
from datetime import datetime
try:
    from termcolor import colored
except Exception:
    def colored(s,*a,**k): return s
def _g(M,name,default=None, cast=float):
    try:
        v = getattr(M,name)
        return cast(v) if cast else v
    except Exception:
        return default
def _fmt(v, nd=6):
    try: return f"{float(v):.{nd}f}"
    except: return str(v)
def _fetch():
    try: import main as M
    except Exception: return None
    out = dict(
        total_trades=_g(M,'total_trades',0,int),
        wins=_g(M,'successful_trades',0,int),
        losses=_g(M,'failed_trades',0,int),
        compound_profit=_g(M,'compound_profit',0.0,float),
        balance=_g(M,'cached_balance',None,float),
        current_price=_g(M,'current_price',0.0,float),
        ema200=_g(M,'ema_200_value',0.0,float),
        ema20=_g(M,'ema20_value',None,float),
        ema50=_g(M,'ema50_value',None,float),
        rsi=_g(M,'rsi_value',0.0,float),
        adx=_g(M,'adx_value',0.0,float),
        atr=_g(M,'current_atr',0.0,float),
        range_pct=_g(M,'price_range_value',None,float),
        bbwidth=_g(M,'bb_width',None,float),
        supertrend=_g(M,'supertrend_dir_value',None,float),
        position_open=bool(_g(M,'position_open',False,cast=lambda x: bool(x))),
        position_side=_g(M,'position_side','N/A',cast=lambda x: x),
        entry_price=_g(M,'entry_price',0.0,float),
        tp1_price=_g(M,'tp1_price',0.0,float),
        tp2_price=_g(M,'tp2_price',0.0,float),
        sl_price=_g(M,'sl_price',0.0,float),
        trailing_active=_g(M,'trailing_active',False,cast=lambda x: bool(x)),
        pnl=_g(M,'current_pnl',0.0,float),
        update_time=_g(M,'update_time','',cast=lambda x: x),
        leverage=_g(M,'LEVERAGE',10,int),
        risk_alloc=_g(M,'RISK_ALLOC',0.6,float),
        timeframe=_g(M,'INTERVAL','15m', cast=lambda x: x),
        mode=_g(M,'TRADE_MODE','live', cast=lambda x: x),
        cooldown_reason=_g(M,'cooldown_reason','',cast=lambda x: x),
        daily_trade_count=_g(M,'daily_trade_count',0,int)
    )
    return out
def print_snapshot_plus():
    C = _fetch()
    if C is None:
        print(colored("[metrics+] cannot import main.py","red")); return
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    print(colored("\n================ METRICS SNAPSHOT (PLUS) ================","cyan",attrs=["bold"]))
    if C['cooldown_reason']: print(colored(f"⏳ Cooldown       : {C['cooldown_reason']}","yellow"))
    print(colored(f"⚙️  Mode           : {C['mode']} | TF={C['timeframe']} | Lev={C['leverage']}x | Risk={int(C['risk_alloc']*100)}%","white"))
    print(colored(f"📊 Trades         : total={C['total_trades']} | ✅ {C['wins']} | ❌ {C['losses']} | today={C['daily_trade_count']}","white"))
    print(colored(f"💰 Profit (USDT)  : {C['compound_profit']:.4f}","green" if C['compound_profit']>=0 else "red"))
    bal = _fmt(C['balance'],2) if C['balance'] is not None else 'N/A'
    print(colored(f"💵 Balance (USDT) : {bal}","green"))
    print(colored("-- Market --","yellow"))
    print(colored(f"   Price         : { _fmt(C['current_price']) }","white"))
    print(colored(f"   EMA20/50/200  : { _fmt(C['ema20']) } / { _fmt(C['ema50']) } / { _fmt(C['ema200']) }","white"))
    print(colored(f"   RSI / ADX     : { _fmt(C['rsi'],2) } / { _fmt(C['adx'],2) }","white"))
    print(colored(f"   ATR / Range%  : { _fmt(C['atr'],6) } / { _fmt(C['range_pct'],2) }","white"))
    print(colored(f"   BB width      : { _fmt(C['bbwidth'],2) }","white"))
    st = 'BULLISH' if (C['supertrend'] is not None and C['supertrend']>0) else ('BEARISH' if C['supertrend'] is not None else 'N/A')
    print(colored(f"   Supertrend    : {st}", "green" if st=='BULLISH' else ("red" if st=='BEARISH' else "white")))
    print(colored("-- Position --","yellow"))
    if C['position_open']:
        pnlc = "green" if C['pnl']>=0 else "red"
        print(colored(f"   Side          : {C['position_side']}","white"))
        print(colored(f"   Entry         : { _fmt(C['entry_price']) }","white"))
        print(colored(f"   TP1/TP2/SL    : { _fmt(C['tp1_price']) } / { _fmt(C['tp2_price']) } / { _fmt(C['sl_price']) }","white"))
        print(colored(f"   Trailing      : {'ON' if C['trailing_active'] else 'OFF'}","white"))
        print(colored(f"   PnL (USDT)    : { _fmt(C['pnl'],4) }",pnlc))
    else:
        print(colored("   No active position","white"))
    if C['update_time']:
        print(colored(f"🕒 Last update    : {C['update_time']}","white"))
def start_metrics_logger_plus(interval=30):
    import threading
    def _loop():
        while True:
            try: print_snapshot_plus()
            except Exception as e: print(colored(f"[metrics+] error: {e}","red"))
            time.sleep(max(5,int(interval)))
    t = threading.Thread(target=_loop, daemon=True); t.start()
    print(colored(f"[metrics+] logger started: every {interval}s","cyan"))
