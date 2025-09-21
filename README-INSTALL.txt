Install / Integrate (1 minute)
------------------------------
1) Add `strategy_guard.py` to your repo root (next to main.py).
2) Open `main.py` and import:
       from strategy_guard import enter_trade_protected
3) Where you place orders now, replace it with:
       ok, info = enter_trade_protected(exchange_or_core=exchange, symbol=SYMBOL,
                                        side=signal_side, qty=order_qty,
                                        entry_price=entry_price, atr=current_atr)
       if not ok:
           log(f"[protect] {info}")
           return
       else:
           log(f"[entry] {info}")
4) Done. The bot will never enter a position unless the exchange
   accepts TP and SL reduceOnly orders first.

Tips:
- If you use your own `bot_core.py`, pass it as `exchange_or_core`.
- If your core exposes a different cancel method, you can update `_cancel_safely` accordingly.
