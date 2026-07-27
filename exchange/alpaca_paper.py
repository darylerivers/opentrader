#!/usr/bin/env python3
"""Alpaca Paper Exchange — real prices via Alpaca/yfinance, paper settlement.

Waterfall: Alpaca (if keys) -> yfinance (cached 5min) -> synthetic GBM.
Order execution: in-memory ledger (matches exchange/paper.py pattern).
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SimpleBar:
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("opentrader.exchange.alpaca")

PROJECT = Path(__file__).resolve().parent.parent
CACHE_DB = PROJECT / "data" / "price_cache.db"
CONFIG = PROJECT / "config" / "alt_data_keys.json"

# Default industry median prices (fallback when no real data)
INDUSTRY_MEDIAN = {
    "AAPL": 190, "NVDA": 120, "MSFT": 420, "GOOGL": 175, "AMZN": 200,
    "META": 500, "TSLA": 250, "JPM": 200, "V": 280, "JNJ": 155,
    "WMT": 70, "PG": 165, "MA": 470, "XOM": 115, "HD": 370,
    "BAC": 40, "DIS": 100, "NFLX": 650, "ADBE": 520, "CRM": 290,
    "SPY": 550, "QQQ": 470, "GLD": 220, "SLV": 28, "USO": 75, "UNG": 3.5,
    "CORN": 35, "WEAT": 50, "SOYB": 28, "DBA": 25,
    "PICK": 55, "FCX": 45, "BHP": 60, "RIO": 80,
    "XLE": 95, "XOP": 40, "KOL": 20, "LIT": 60, "URNM": 25,
    "SONY": 90, "INTC": 35, "AMD": 150, "TSM": 170,
}


@dataclass
class Balance:
    cash: float = 0.0
    equity: float = 0.0
    total_value: float = 0.0
    positions: Dict[str, float] = None

    def __post_init__(self):
        if self.positions is None:
            self.positions = {}


class AlpacaPaperExchange:
    """Paper exchange with Alpaca/yfinance real prices."""

    def __init__(self, initial_cash: float = 100000.0):
        self.cash = initial_cash
        self.name = "alpaca-paper"
        self.positions: Dict[str, float] = {}
        self.trades: list = []
        self.fee_rate = 0.0005  # 5bps
        self._bars: Dict[str, list] = {}
        self._alpaca_key = ""
        self._alpaca_secret = ""
        self._yfinance_calls = 0
        self._yfinance_reset = time.time()
        self._load_keys()
        self._init_cache()

    def _load_keys(self):
        if CONFIG.exists():
            try:
                keys = json.loads(CONFIG.read_text())
                self._alpaca_key = keys.get("ALPACA_KEY", "")
                self._alpaca_secret = keys.get("ALPACA_SECRET", "")
            except Exception:
                pass

    def _init_cache(self):
        os.makedirs(CACHE_DB.parent, exist_ok=True)
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS prices "
                "(symbol TEXT PRIMARY KEY, price REAL, source TEXT, fetched_at REAL)"
            )

    def _cached_price(self, symbol: str) -> Optional[float]:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            row = conn.execute(
                "SELECT price, fetched_at FROM prices WHERE symbol=?",
                (symbol.upper(),),
            ).fetchone()
        if row:
            price, ts = row
            if time.time() - ts < 300:  # 5min TTL
                return price
        return None

    def _cache_price(self, symbol: str, price: float, source: str):
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?)",
                (symbol.upper(), price, source, time.time()),
            )

    def _fetch_yfinance(self, symbol: str) -> Optional[float]:
        if self._yfinance_calls >= 30 and time.time() - self._yfinance_reset < 60:
            logger.debug(f"yfinance rate cap hit — using fallback for {symbol}")
            return None
        self._yfinance_calls += 1
        if time.time() - self._yfinance_reset > 3600:
            self._yfinance_calls = 0
            self._yfinance_reset = time.time()
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            if price and price > 0:
                return float(price)
        except Exception as e:
            logger.debug(f"yfinance fetch failed for {symbol}: {e}")
        return None

    def _fetch_alpaca(self, symbol: str) -> Optional[float]:
        if not self._alpaca_key:
            return None
        try:
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
            req = Request(url, headers={
                "APCA-API-KEY-ID": self._alpaca_key,
                "APCA-API-SECRET-KEY": self._alpaca_secret,
            })
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                quote = data.get("quote", {})
                price = quote.get("ap") or quote.get("bp")
                if price and price > 0:
                    return float(price)
        except Exception as e:
            logger.debug(f"Alpaca fetch failed for {symbol}: {e}")
        return None

    def connect(self):
        """No-op — Alpaca uses stateless REST calls."""
        pass

    def get_current_price(self, symbol: str) -> float:
        symbol = symbol.upper()
        # 1. Cache hit
        cached = self._cached_price(symbol)
        if cached:
            return cached

        # 2. Alpaca
        price = self._fetch_alpaca(symbol)
        if price:
            self._cache_price(symbol, price, "alpaca")
            return price

        # 3. yfinance
        price = self._fetch_yfinance(symbol)
        if price:
            self._cache_price(symbol, price, "yfinance")
            return price

        # 4. Industry median fallback
        return INDUSTRY_MEDIAN.get(symbol, 100.0)

    def get_prices_batch(self, symbols: list) -> dict:
        """Fetch multiple prices in one batch (Alpaca or yfinance)."""
        result = {}
        remaining = list(symbols)

        # 1. Check cache
        for sym in list(remaining):
            cached = self._cached_price(sym)
            if cached:
                result[sym] = cached
                remaining.remove(sym)
        if not remaining:
            return result

        # 2. Alpaca batch (max 200 per call)
        if self._alpaca_key:
            try:
                chunked = ','.join(remaining[:200])
                url = f"https://data.alpaca.markets/v2/stocks/quotes?symbols={chunked}"
                req = Request(url, headers={
                    "APCA-API-KEY-ID": self._alpaca_key,
                    "APCA-API-SECRET-KEY": self._alpaca_secret,
                })
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    for sym, q in (data.get("quotes", {}) or {}).items():
                        price = q.get("ap") or q.get("bp") or q.get("latest_trade", {}).get("p")
                        if price and price > 0:
                            result[sym] = float(price)
                            self._cache_price(sym, float(price), "alpaca")
                            if sym in remaining:
                                remaining.remove(sym)
            except Exception as e:
                logger.debug(f"Alpaca batch fetch failed: {e}")

        # 3. yfinance fallback per remaining symbol
        for sym in remaining:
            price = self._fetch_yfinance(sym)
            if price:
                result[sym] = price
                self._cache_price(sym, price, "yfinance")
            else:
                result[sym] = INDUSTRY_MEDIAN.get(sym, 100.0)

        return result

    def get_bars(self, symbol: str, timeframe: str = "1h", limit: int = 80) -> List[SimpleBar]:
        """Return OHLCV bars. Uses synthetic GBM anchored by real price."""
        key = f"{symbol}:{timeframe}"
        if key in self._bars and len(self._bars[key]) >= limit:
            return self._bars[key][-limit:]

        real_price = self.get_current_price(symbol)
        import random, math
        random.seed(hash(key) % (2**31))

        bars = []
        price = real_price
        for i in range(limit):
            ret = random.gauss(0.0001, 0.01)
            price *= (1 + ret)
            o = price
            c = o * (1 + random.gauss(0, 0.005))
            h = max(o, c) * (1 + abs(random.gauss(0, 0.003)))
            l = min(o, c) * (1 - abs(random.gauss(0, 0.003)))
            v = max(100, int(random.gauss(5000, 2000)))
            bars.append(SimpleBar(open=o, high=h, low=l, close=c, volume=v))

        self._bars[key] = bars
        return bars[-limit:]

    def push_bar(self, symbol: str, bar: dict):
        """Push a new OHLCV bar (called per-cycle by harness)."""
        key = f"{symbol}:1h"
        if key not in self._bars:
            self._bars[key] = []
        b = bar[0] if isinstance(bar, list) else bar
        self._bars[key].append(SimpleBar(
            open=float(b.get("open", b.get("o", 0))),
            high=float(b.get("high", b.get("h", 0))),
            low=float(b.get("low", b.get("l", 0))),
            close=float(b.get("close", b.get("c", 0))),
            volume=float(b.get("volume", 0)),
        ))

    def load_bars(self, symbol: str, bars: list):
        key = f"{symbol}:1h"
        if key not in self._bars:
            self._bars[key] = []
        for b in bars:
            if isinstance(b, dict):
                self._bars[key].append(SimpleBar(
                    open=float(b.get("open", 0)),
                    high=float(b.get("high", 0)),
                    low=float(b.get("low", 0)),
                    close=float(b.get("close", 0)),
                    volume=float(b.get("volume", 0)),
                ))
            elif hasattr(b, "close"):
                self._bars[key].append(SimpleBar(
                    open=getattr(b, "open", 0),
                    high=getattr(b, "high", 0),
                    low=getattr(b, "low", 0),
                    close=getattr(b, "close", 0),
                    volume=getattr(b, "volume", 0),
                ))

    def get_balance(self) -> Balance:
        bal = Balance(cash=self.cash, total_value=self.cash)
        for sym, qty in self.positions.items():
            price = self.get_current_price(sym)
            val = qty * price
            bal.equity += val
            bal.total_value += val
            bal.positions[sym] = qty
        return bal

    def submit_order(self, symbol: str, quantity: float, side: str) -> dict:
        price = self.get_current_price(symbol)
        cost = quantity * price
        fee = max(0.01, cost * self.fee_rate)

        if side.upper() == "BUY":
            if cost + fee > self.cash:
                quantity = (self.cash - fee) / price
                cost = quantity * price
            self.cash -= cost + fee
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:  # SELL
            available = self.positions.get(symbol, 0)
            quantity = min(quantity, available)
            if quantity <= 0:
                return {"status": "rejected", "reason": "no position"}
            self.cash += cost - fee
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            if self.positions[symbol] <= 0:
                del self.positions[symbol]

        trade = {
            "symbol": symbol, "quantity": quantity, "side": side.upper(),
            "price": price, "cost": cost, "fee": fee, "cash_after": self.cash,
        }
        self.trades.append(trade)
        return {"status": "filled", **trade}

    def reset(self, initial_cash: float = 100000.0):
        self.cash = initial_cash
        self.positions.clear()
        self.trades.clear()
        self._bars.clear()
