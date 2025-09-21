"""
strategy_guard.py
-----------------
Drop-in helper to enforce: **NO ENTRY unless SL & TP are placed successfully**.

Usage:
------
1) Copy this file next to your `main.py`.
2) In main.py:
    from strategy_guard import enter_trade_protected

3) Replace your entry call with:
    ok, info = enter_trade_protected(
        exchange_or_core=exchange_or_core,   # ccxt exchange or your bot_core object
        symbol=SYMBOL,
        side=signal_side,                    # 'long' or 'short'
        qty=order_qty,
        entry_price=entry_price,
        atr=current_atr
    )
    if not ok:
        log(f"[protect] entry aborted: {info}")
        return
    else:
        log(f"[entry] {info}")

Notes:
------
- Tries several param shapes for BingX gateways:
  * TAKE_PROFIT(_MARKET) / STOP(_MARKET) with triggerPrice
  * market with takeProfitPrice / stopLossPrice
- If SL+TP could not be **accepted by the exchange**, the entry is **not sent**.
- If entry fails AFTER protections were placed, it cancels protections to avoid stale orders.
"""

from typing import Tuple

def _reduce_side(side: str) -> str:
    return 'sell' if side == 'long' else 'buy'

def _entry_side(side: str) -> str:
    return 'buy' if side == 'long' else 'sell'

def _place_any(exchange, symbol, specs, qty):
    """
    Try a sequence of order specs until one succeeds.
    Returns (success: bool, last_error: str)
    """
    last_err = ""
    for s in specs:
        try:
            exchange.create_order(symbol, s['type'], s['side'], qty, params=s['params'])
            return True, ""
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    return False, last_err

def _build_protective_specs(side: str, tp1: float, sl: float):
    reduce_side = _reduce_side(side)
    return [
        # Take Profit first (one of these must pass)
        dict(type='TAKE_PROFIT_MARKET', side=reduce_side, params={'reduceOnly': True, 'triggerPrice': tp1}),
        dict(type='TAKE_PROFIT',        side=reduce_side, params={'reduceOnly': True, 'triggerPrice': tp1}),
        dict(type='market',             side=reduce_side, params={'reduceOnly': True, 'takeProfitPrice': tp1}),
    ], [
        # Stop Loss (one of these must pass)
        dict(type='STOP_MARKET',        side=reduce_side, params={'reduceOnly': True, 'triggerPrice': sl}),
        dict(type='STOP',               side=reduce_side, params={'reduceOnly': True, 'triggerPrice': sl}),
        dict(type='market',             side=reduce_side, params={'reduceOnly': True, 'stopLossPrice': sl}),
    ]

def _cancel_safely(exchange, symbol: str):
    try:
        # Not all gateways expose cancelAllOrders; swallow errors silently.
        if hasattr(exchange, 'cancel_all_orders'):
            exchange.cancel_all_orders(symbol)
        elif hasattr(exchange, 'cancelAllOrders'):
            exchange.cancelAllOrders(symbol)
    except Exception:
        pass

def enter_trade_protected(exchange_or_core, symbol: str, side: str, qty: float, entry_price: float, atr: float) -> Tuple[bool, str]:
    """
    Workflow:
      1) Compute TP1 & SL using ATR
      2) Place protective orders (TP1 + SL) as reduceOnly conditionals
      3) If BOTH protections accepted -> send the entry order
      4) If entry fails -> cancel protections and fail safely

    Returns: (ok, info_message)
    """
    if qty <= 0:
        return False, "qty<=0"

    tp1 = entry_price + 1.2*atr if side == 'long' else entry_price - 1.2*atr
    sl  = entry_price - 1.2*atr if side == 'long' else entry_price + 1.2*atr

    tp_specs, sl_specs = _build_protective_specs(side, tp1, sl)

    # (1) TP first
    ok_tp, err_tp = _place_any(exchange_or_core, symbol, tp_specs, qty)
    if not ok_tp:
        return False, f"TP rejected by exchange ({err_tp})"

    # (2) SL second
    ok_sl, err_sl = _place_any(exchange_or_core, symbol, sl_specs, qty)
    if not ok_sl:
        # cleanup TP we just placed
        _cancel_safely(exchange_or_core, symbol)
        return False, f"SL rejected by exchange ({err_sl})"

    # (3) Entry
    try:
        exchange_or_core.create_order(symbol, 'market', _entry_side(side), qty, params={'reduceOnly': False})
        return True, f"{side} with TP={tp1:.6f} & SL={sl:.6f} confirmed"
    except Exception as e:
        _cancel_safely(exchange_or_core, symbol)
        return False, f"entry failed after protections ({type(e).__name__}: {e})"
