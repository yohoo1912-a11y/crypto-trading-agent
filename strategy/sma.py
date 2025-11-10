# strategy/sma.py
import asyncio
import logging
import numpy as np
import pandas as pd
from exchangers.ccxt_client import ExchangeManager

logger = logging.getLogger("sma_strategy")

class SMAStrategy:
    def __init__(self, exchange_manager: ExchangeManager, symbol="BTC/USDT", timeframe="1m", short=20, long=50):
        self.exchange_manager = exchange_manager
        self.symbol = symbol
        self.timeframe = timeframe
        self.short = short
        self.long = long

    async def run_once(self):
        # fetch recent OHLCV
        price = await self._fetch_last_price()
        if price is None:
            logger.info("No price data, skipping")
            return
        # in real backtest we'd use historical data; here compute SMA from public ohlcv
        df = await self._fetch_ohlcv_df(limit=self.long + 10)
        if df is None or len(df) < self.long:
            logger.info("not enough data for sma")
            return
        df["sma_short"] = df["close"].rolling(self.short).mean()
        df["sma_long"] = df["close"].rolling(self.long).mean()
        last = df.iloc[-1]
        prev = df.iloc[-2]
        signal = None
        # detect cross
        if prev["sma_short"] <= prev["sma_long"] and last["sma_short"] > last["sma_long"]:
            signal = "buy"
        elif prev["sma_short"] >= prev["sma_long"] and last["sma_short"] < last["sma_long"]:
            signal = "sell"
        if signal:
            logger.info(f"SMA signal {signal} at price {price}")
            # simple fixed size for demo
            await self.exchange_manager.create_order(self.symbol, signal, 0.001)

    async def _fetch_last_price(self):
        # use binance if available
        try:
            ex = self.exchange_manager.exchanges.get("binance")
            if ex:
                ohlc = ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=1)
                if ohlc:
                    return float(ohlc[-1][4])
        except Exception:
            pass
        # fallback: try coinbase
        try:
            ex = self.exchange_manager.exchanges.get("coinbase")
            if ex:
                ohlc = ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=1)
                if ohlc:
                    return float(ohlc[-1][4])
        except Exception:
            pass
        return None

    async def _fetch_ohlcv_df(self, limit=100):
        # prefer exchange public data
        try:
            ex = self.exchange_manager.exchanges.get("binance")
            if ex:
                ohlc = ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=limit)
                df = pd.DataFrame(ohlc, columns=["timestamp","open","high","low","close","volume"])
                return df
        except Exception:
            pass
        # fallback to sample CSV
        try:
            df = pd.read_csv("data/sample_minute_ohlc.csv")
            return df.tail(limit)
        except Exception:
            logger.exception("No data available")
            return None
