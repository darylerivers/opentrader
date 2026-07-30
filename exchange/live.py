#!/usr/bin/env python3
"""Live Exchange — Paper trades on real CCXT market data.

Architecture:
  - OHLCV data from Coinbase (or any CCXT exchange)
  - Orders execute on an in-memory paper ledger
  - No real money ever leaves the system
  - Supports: paper trading on live data, backtesting from historical

This gives us the realism of live prices with zero capital risk.
The agent trades on real market conditions; we settle on paper.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import ExchangeBase, OHLCV, OrderResult, Balance, register_exchange

logger = logging.getLogger("opentrader.live_exchange")

# CCXT exchange IDs we support
SUPPORTED_EXCHANGES = {
    "coinbase": "coinbaseprime",
    "coinbaseprime": "coinbaseprime",
    "coinbaseadvanced": "coinbaseprime",  # fallback for live mode
    "live": "coinbaseprime",
    "kraken": "kraken",
    "kucoin": "kucoin",
    "bitfinex": "bitfinex",
}

# Default rate limits (calls per second)
RATE_LIMITS = {
    "coinbaseprime": 10,
    "kraken": 8,
    "bitfinex": 10,
    "kucoin": 10,
}


class LiveExchange(ExchangeBase):
    """Paper exchange on live CCXT OHLCV data.

    Fetches real price data from a CCXT exchange.
    All order execution is paper (in-memory ledger).
    """

    def __init__(self, name: str = "coinbase", config: dict = None):
        super().__init__(name, config)
        config = config or {}

        # Paper ledger state (same as PaperExchange)
        self._cash: float = float(config.get("initial_cash", 100_000))
        self._positions: Dict[str, float] = {}
        self._cost_basis: Dict[str, float] = {}
        self._fills: List[dict] = []
        self._order_counter: int = 1

        # CCXT exchange config
        exchange_id = SUPPORTED_EXCHANGES.get(name.lower(), name.lower())
        self._ccxt_exchange_id = exchange_id
        self._rate_limit = RATE_LIMITS.get(exchange_id, 3)
        self._last_api_call: float = 0.0
        self._ccxt = None

        # CCXT options
        self._ccxt_config = {
            "enableRateLimit": True,
            "rateLimit": int(1000 / self._rate_limit),
        }
        # Add API keys if provided
        api_key = config.get("api_key", "")
        api_secret = config.get("api_secret", "")
        if api_key and api_secret:
            self._ccxt_config["apiKey"] = api_key
            self._ccxt_config["secret"] = api_secret
        if name.lower() == "coinbaseadvanced":
            # Coinbase Advanced requires different auth
            passphrase = config.get("passphrase", "")
            if passphrase:
                self._ccxt_config["passphrase"] = passphrase

        # Cache
        self._bar_cache: Dict[str, List[OHLCV]] = {}
        self._price_cache: Dict[str, float] = {}
        self._cache_ttl = config.get("cache_ttl", 30.0)  # seconds
        self._last_fetch: Dict[str, float] = {}

    def connect(self) -> bool:
        import ccxt
        try:
            exchange_class = getattr(ccxt, self._ccxt_exchange_id)
            self._ccxt = exchange_class(self._ccxt_config)
            # Test connection by loading markets
            self._ccxt.load_markets()
            logger.info(f"Connected to {self._ccxt_exchange_id}: "
                         f"{len(self._ccxt.markets)} markets available")
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self._ccxt_exchange_id}: {e}")
            self._connected = False
            return False

    def _rate_limit_wait(self):
        """Throttle API calls to stay within rate limits."""
        elapsed = time.time() - self._last_api_call
        min_interval = 1.0 / max(self._rate_limit, 1)
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_api_call = time.time()

    def _ensure_market_symbol(self, symbol: str) -> str:
        """Normalize symbol to exchange format if needed."""
        if self._ccxt and self._ccxt.markets:
            # If it has a / it's already in exchange format
            if "/" in symbol:
                return symbol
            # Try to find the market
            for market_id in self._ccxt.markets:
                if market_id.replace("/", "").upper() == symbol.upper():
                    return market_id
        return symbol

    def discover_symbols(self, max_symbols: int = 20) -> List[str]:
        """Return top tradable USDT pairs sorted by 24h volume.
        
        Fetches markets, filters to USDT-quoted pairs, sorts by 24h volume
        descending, and returns the top N symbols.
        """
        if not self._connected or not self._ccxt:
            return []
        try:
            self._rate_limit_wait()
            markets = self._ccxt.load_markets(reload=False)
            candidates = []
            for sym, meta in markets.items():
                if not sym.endswith("/USDT"):
                    continue
                if not meta.get("active", True):
                    continue
                vol = meta.get("info", {}).get("volume") or meta.get("info", {}).get("vol") or meta.get("info", {}).get("baseVolume", 0)
                try:
                    vol = float(vol)
                except (ValueError, TypeError):
                    vol = 0.0
                candidates.append((vol, sym))
            candidates.sort(key=lambda x: x[0], reverse=True)
            return [sym for _, sym in candidates[:max_symbols]]
        except Exception as e:
            logger.warning(f"Failed to discover symbols from {self._ccxt_exchange_id}: {e}")
            return []

    def get_bars(self, symbol: str = "BTC/USDT", timeframe: str = "1h",
                 limit: int = 100) -> List[OHLCV]:
        """Fetch OHLCV bars from exchange (with cache)."""
        # Return empty if not connected (graceful fallback)
        if not self._connected or not self._ccxt:
            logger.warning(f"get_bars({symbol}, {timeframe}): using stale cache (exchange disconnected)")
            return self._bar_cache.get(f"{symbol}:{timeframe}:{limit}", [])

        # Check cache
        cache_key = f"{symbol}:{timeframe}:{limit}"
        now = time.time()
        if cache_key in self._bar_cache:
            last_fetch = self._last_fetch.get(cache_key, 0)
            if now - last_fetch < self._cache_ttl:
                return self._bar_cache[cache_key]

        # Try local bars first (for pre-loaded backtest data)
        if symbol in self._bar_cache and not self._bar_cache[symbol]:
            pass

        # Fall back to exchange
        try:
            self._rate_limit_wait()
            market = self._ensure_market_symbol(symbol)
            raw = self._ccxt.fetch_ohlcv(market, timeframe=timeframe, limit=limit)
            bars = [OHLCV(timestamp=r[0], open=r[1], high=r[2],
                          low=r[3], close=r[4], volume=r[5]) for r in raw]
            self._bar_cache[cache_key] = bars
            self._last_fetch[cache_key] = now

            # Update price cache
            if bars:
                self._price_cache[symbol] = bars[-1].close

            logger.debug(f"Fetched {len(bars)} bars for {symbol}")
            return bars
        except Exception as e:
            err_msg = str(e)
            # Coinbase Prime doesn't support 4h granularity — expected, not an error
            if "Unsupported granularity" in err_msg or "unsupported timeframe" in err_msg.lower():
                logger.info(f"Cannot fetch {symbol} {timeframe} bars: {err_msg} (skipping)")
            else:
                logger.warning(f"Failed to fetch {symbol} bars: {err_msg}")
            # Return cached bars if available
            return self._bar_cache.get(cache_key, [])

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price (from cache or exchange)."""
        # Check price cache first
        if symbol in self._price_cache:
            return self._price_cache[symbol]

        # Fetch a single bar to get latest price
        try:
            self._rate_limit_wait()
            market = self._ensure_market_symbol(symbol)
            ticker = self._ccxt.fetch_ticker(market)
            price = ticker.get("last") or ticker.get("close") or ticker.get("bid")
            if price:
                self._price_cache[symbol] = price
            return price
        except Exception as e:
            logger.debug(f"Failed to fetch ticker for {symbol}: {e}")
            return self._price_cache.get(symbol)

    def _fetch_ticker_live(self, symbol: str) -> Optional[float]:
        """Fetch current order book midpoint (bid-ask avg) for execution pricing.
        Kraken's ticker endpoint returns stale data (~$3 behind order book).
        Order book provides real-time market pricing."""
        if not self._connected or not self._ccxt:
            return None
        try:
            self._rate_limit_wait()
            market = self._ensure_market_symbol(symbol)
            ob = self._ccxt.fetch_order_book(market, limit=1)
            bid = ob.get("bids", [[0]])[0][0] if ob.get("bids") else 0
            ask = ob.get("asks", [[0]])[0][0] if ob.get("asks") else 0
            if bid > 0 and ask > 0:
                price = (bid + ask) / 2.0
                logger.debug(f"OB mid for {symbol}: bid={bid} ask={ask} mid={price}")
                self._price_cache[symbol] = price
                return price
            # Fallback: stale ticker
            ticker = self._ccxt.fetch_ticker(market)
            price = ticker.get("last") or ticker.get("close") or ticker.get("bid")
            if price:
                self._price_cache[symbol] = price
            return price
        except Exception as e:
            logger.error(f"Ticker fetch failed for {symbol}: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = "market", price: Optional[float] = None) -> OrderResult:
        """Paper execution — matches PaperExchange logic.
        Uses real-time ticker price for execution (not cached OHLCV close)."""
        if price:
            fill_price = price
        else:
            # Fetch fresh ticker — not the stale OHLCV close from cache
            fill_price = self._fetch_ticker_live(symbol) or self.get_current_price(symbol)
        if not fill_price or fill_price <= 0:
            return OrderResult(
                order_id="", symbol=symbol, side=side,
                quantity=quantity, price=0, status="rejected",
                timestamp=datetime.now(timezone.utc).isoformat(),
                raw={"error": "no price data"},
            )
        cost = fill_price * quantity

        if side.upper() == "BUY":
            if cost > self._cash:
                affordable_qty = self._cash / fill_price
                if affordable_qty <= 0:
                    return OrderResult(
                        order_id=f"live_{self._order_counter}",
                        symbol=symbol, side=side, quantity=quantity,
                        price=fill_price, status="rejected",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        raw={"error": "insufficient cash"},
                    )
                quantity = affordable_qty
                cost = fill_price * quantity
            self._cash -= cost
            self._positions[symbol] = self._positions.get(symbol, 0) + quantity
            self._cost_basis[symbol] = self._cost_basis.get(symbol, 0) + cost

        elif side.upper() == "SELL":
            pos = self._positions.get(symbol, 0)
            if pos <= 0:
                return OrderResult(
                    order_id=f"live_{self._order_counter}",
                    symbol=symbol, side=side, quantity=quantity,
                    price=fill_price, status="rejected",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    raw={"error": "no position"},
                )
            quantity = min(quantity, pos)
            self._cash += fill_price * quantity
            self._positions[symbol] -= quantity
            if self._positions[symbol] <= 0:
                del self._positions[symbol]
                self._cost_basis.pop(symbol, None)  # safe delete — may not exist on restore

        order_id = f"live_{self._order_counter}"
        self._order_counter += 1
        fill = {
            "order_id": order_id, "symbol": symbol, "side": side,
            "quantity": round(quantity, 8), "price": fill_price,
            "cost": round(cost, 2), "cash_after": round(self._cash, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._fills.append(fill)
        return OrderResult(
            order_id=order_id, symbol=symbol, side=side,
            quantity=round(quantity, 8), price=fill_price,
            status="filled", timestamp=fill["timestamp"], raw=fill,
        )

    def get_balance(self) -> Balance:
        portfolio_value = self._cash
        for sym, qty in self._positions.items():
            price = self._price_cache.get(sym, 0)
            if price <= 0:
                price = self.get_current_price(sym) or 0
            portfolio_value += price * qty
        return Balance(
            cash=round(self._cash, 2),
            total_value=round(portfolio_value, 2),
            positions={k: round(v, 8) for k, v in self._positions.items()},
        )

    def get_fills(self) -> List[dict]:
        return self._fills

    def load_bars(self, symbol: str, bars: List[dict]) -> None:
        """Pre-load OHLCV bars (for backtesting)."""
        cache_key = f"{symbol}:1h:{len(bars)}"
        self._bar_cache[cache_key] = [OHLCV.from_dict(b) for b in bars]
        if self._bar_cache[cache_key]:
            self._price_cache[symbol] = self._bar_cache[cache_key][-1].close

    def disconnect(self) -> None:
        self._connected = False
        logger.info(f"Disconnected from {self._ccxt_exchange_id}")

    def reset(self, initial_cash: float = 100_000) -> None:
        """Reset paper ledger (keeps exchange connection)."""
        self._cash = initial_cash
        self._positions.clear()
        self._cost_basis.clear()
        self._fills.clear()
        self._order_counter = 1


# ── Pre-fetch utility for backtesting ──

def fetch_historical_bars(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    count: int = 500,
    exchange_id: str = "coinbase",
) -> List[dict]:
    """Fetch historical bars for backtesting.

    Returns list of OHLCV dicts suitable for load_bars().
    """
    import ccxt
    exchange_class = getattr(ccxt, exchange_id)
    exchange = exchange_class({"enableRateLimit": True})
    exchange.load_markets()
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=count)
    bars = []
    for i, r in enumerate(raw):
        bars.append({
            "timestamp": r[0],
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "volume": r[5],
        })
    return bars


register_exchange("live", LiveExchange)
register_exchange("coinbase", LiveExchange)

# Also register exchange name variants
for name in SUPPORTED_EXCHANGES:
    if name not in ("live", "coinbase"):
        register_exchange(name, LiveExchange)
