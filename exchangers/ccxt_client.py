# exchangers/ccxt_client.py
import os
import time
import logging
import ccxt
import httpx
from typing import List, Dict, Any

logger = logging.getLogger("ccxt_client")

class ExchangeManager:
    def __init__(self, mode="paper", supabase_url=None, supabase_key=None):
        self.mode = mode
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.exchanges = {}
        # create exchange clients if keys exist
        self._init_exchanges()

    def _init_exchanges(self):
        bin_key = os.getenv("EXCHANGE_BINANCE_KEY")
        bin_sec = os.getenv("EXCHANGE_BINANCE_SECRET")
        if bin_key and bin_sec:
            ex = ccxt.binance({"apiKey": bin_key, "secret": bin_sec, "enableRateLimit": True})
            self.exchanges["binance"] = ex
            self._validate_keys("binance", ex)

        cb_key = os.getenv("EXCHANGE_COINBASE_KEY")
        cb_sec = os.getenv("EXCHANGE_COINBASE_SECRET")
        if cb_key and cb_sec:
            ex = ccxt.coinbasepro({"apiKey": cb_key, "secret": cb_sec})
            self.exchanges["coinbase"] = ex
            self._validate_keys("coinbase", ex)

    def _validate_keys(self, name, ex):
        # Best-effort detection of withdrawal perms. Many exchanges don't expose permissions.
        try:
            # attempt a harmless private request: fetch_balance
            bal = ex.fetch_balance()
            logger.info(f"{name} balance keys OK (sample asset keys: {list(bal.get('total',{}) )[:5]})")
            # if exchange returns 'info' with permissions, check it
            info = getattr(ex, 'api', None)
        except Exception as e:
            logger.warning(f"Key validation for {name} failed: {e}")

    def connected(self) -> List[str]:
        return list(self.exchanges.keys())

    async def create_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        if self.mode == "paper":
            return self._simulate_fill(symbol, side, amount)
        # live mode
        # pick first connected exchange
        if not self.exchanges:
            raise RuntimeError("No exchanges configured for live mode")
        ex = next(iter(self.exchanges.values()))
        # place market order
        try:
            order = ex.create_market_order(symbol, side, amount)
            # write to supabase if configured
            self._write_trade_record(exchange=ex.id, symbol=symbol, side=side, amount=amount, price=order.get("average") or order.get("price", 0), mode="live", raw=order)
            return {"status": "ok", "order": order}
        except Exception as e:
            logger.exception("Live order failed")
            return {"status": "error", "error": str(e)}

    def _simulate_fill(self, symbol, side, amount):
        # use public API to get last price, or fallback to sample data
        price = self._fetch_mark_price(symbol) or 0.0
        record = {
            "exchange": "paper",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "fee": 0,
            "mode": "paper",
            "timestamp": time.time()
        }
        self._write_trade_record(**record)
        # update positions table naive
        if side == "buy":
            self._insert_position(symbol, "buy", amount, price)
        else:
            # naive: remove positions of same symbol
            self._close_position(symbol, amount, price)
        return {"status": "simulated", "fill": record}

    def _fetch_mark_price(self, symbol):
        # try exchange public fetch if available
        try:
            # use ccxt public market from binance if available
            ex = self.exchanges.get("binance")
            if ex:
                ohlc = ex.fetch_ohlcv(symbol, timeframe="1m", limit=1)
                if ohlc:
                    return float(ohlc[-1][4])
        except Exception:
            pass
        # fallback: 0
        return 0.0

    def _write_trade_record(self, exchange="paper", symbol="", side="", amount=0.0, price=0.0, fee=0.0, mode="paper", raw=None):
        if not self.supabase_url or not self.supabase_key:
            logger.info("Supabase not configured; skipping trade write.")
            return
        url = f"{self.supabase_url}/rest/v1/trades"
        headers = {"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}", "Content-Type": "application/json", "Prefer": "return=representation"}
        payload = {
            "exchange": exchange,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "fee": fee,
            "mode": mode,
            "raw": raw or {}
        }
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code not in (200,201):
                logger.warning(f"Supabase write failed: {r.status_code} {r.text}")
        except Exception as e:
            logger.exception("Failed writing trade to supabase")

    def _insert_position(self, symbol, side, amount, entry_price):
        if not self.supabase_url or not self.supabase_key:
            logger.info("Supabase not configured; skipping position insert.")
            return
        url = f"{self.supabase_url}/rest/v1/positions"
        headers = {"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}", "Content-Type": "application/json", "Prefer": "return=representation"}
        payload = {"symbol": symbol, "exchange": "paper", "side": side, "amount": amount, "entry_price": entry_price}
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code not in (200,201):
                logger.warning(f"Supabase insert position failed: {r.status_code} {r.text}")
        except Exception:
            logger.exception("Failed to insert position")

    def _close_position(self, symbol, amount, exit_price):
        # simple: delete positions with same symbol
        if not self.supabase_url or not self.supabase_key:
            logger.info("Supabase not configured; skipping position close.")
            return
        # fetch positions
        url = f"{self.supabase_url}/rest/v1/positions?symbol=eq.{symbol}"
        headers = {"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"}
        try:
            r = httpx.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                logger.warning("Failed to fetch positions for close")
                return
            positions = r.json()
            for p in positions:
                # delete position
                del_url = f"{self.supabase_url}/rest/v1/positions?id=eq.{p['id']}"
                resp = httpx.delete(del_url, headers={"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"})
        except Exception:
            logger.exception("Error closing position")

    def list_positions(self):
        if not self.supabase_url or not self.supabase_key:
            return []
        url = f"{self.supabase_url}/rest/v1/positions"
        headers = {"apikey": self.supabase_key, "Authorization": f"Bearer {self.supabase_key}"}
        try:
            r = httpx.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            logger.exception("Failed to list positions")
        return []
