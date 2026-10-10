"""Market data from Yahoo Finance via yfinance: stocks, ETFs and crypto (e.g. BTC-USD).

yfinance is unofficial and occasionally breaks or rate-limits; it's fine for paper trading,
but a live version should use a broker's data feed."""

import logging
import math
import time

import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

TRADABLE_TYPES = {"EQUITY", "ETF", "CRYPTOCURRENCY"}

SCREENS = [
    "most_actives", "day_gainers", "day_losers", "small_cap_gainers", "aggressive_small_caps",
    "growth_technology_stocks", "undervalued_growth_stocks", "undervalued_large_caps",
    "most_shorted_stocks", "top_etfs_us", "top_performing_etfs", "technology_etfs",
]

_cache: dict[str, tuple[float, dict]] = {}
CACHE_SECONDS = 60


def _clean(v):
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 4)
    return v


def info(symbol: str) -> dict | None:
    """Quote details for one symbol, cached for a minute. None if Yahoo doesn't know it."""
    symbol = symbol.upper().strip()
    hit = _cache.get(symbol)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        raw = yf.Ticker(symbol).info
    except Exception:
        return None
    price = raw.get("regularMarketPrice") or raw.get("currentPrice")
    if not raw or not price:
        return None
    q = {
        "symbol": symbol,
        "name": raw.get("shortName") or raw.get("longName"),
        "type": raw.get("quoteType"),
        "currency": raw.get("currency"),
        "market_state": raw.get("marketState"),
        "price": price,
        "change_pct_today": raw.get("regularMarketChangePercent"),
        "volume": raw.get("regularMarketVolume"),
        "avg_volume_3m": raw.get("averageVolume"),
        "market_cap": raw.get("marketCap"),
        "sector": raw.get("sector"),
        "trailing_pe": raw.get("trailingPE"),
        "forward_pe": raw.get("forwardPE"),
        "fifty_day_avg": raw.get("fiftyDayAverage"),
        "two_hundred_day_avg": raw.get("twoHundredDayAverage"),
        "fifty_two_week_high": raw.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": raw.get("fiftyTwoWeekLow"),
        "next_earnings_ts": raw.get("earningsTimestamp"),
    }
    q = {k: _clean(v) for k, v in q.items() if v is not None}
    _cache[symbol] = (time.time(), q)
    return q


def price(symbol: str) -> float | None:
    q = info(symbol)
    return q["price"] if q else None


def us_market_open() -> bool:
    q = info("SPY")
    return bool(q and q.get("market_state") == "REGULAR")


def history(symbol: str, period: str, interval: str) -> dict | None:
    try:
        h = yf.Ticker(symbol.upper()).history(period=period, interval=interval)
    except Exception:
        return None
    if h.empty:
        return None
    closes = h["Close"].tolist()

    def ret(n: int):
        return round((closes[-1] / closes[-n - 1] - 1) * 100, 2) if len(closes) > n else None

    daily_moves = [abs(b / a - 1) for a, b in zip(closes, closes[1:])]
    step = max(1, len(closes) // 40)  # keep the prompt small: at most ~40 points
    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "bars": len(closes),
        "last_close": round(closes[-1], 4),
        "return_last_5_bars_pct": ret(5),
        "return_last_20_bars_pct": ret(20),
        "return_full_period_pct": round((closes[-1] / closes[0] - 1) * 100, 2),
        "high": round(float(h["High"].max()), 4),
        "low": round(float(h["Low"].min()), 4),
        "avg_abs_move_per_bar_pct": round(sum(daily_moves) / len(daily_moves) * 100, 2) if daily_moves else None,
        "sma_20": round(sum(closes[-20:]) / min(20, len(closes)), 4),
        "sma_50": round(sum(closes[-50:]) / min(50, len(closes)), 4),
        "closes_sampled_oldest_first": [round(c, 4) for c in closes[::step]],
    }


def screen(name: str, count: int) -> list[dict]:
    res = yf.screen(name, count=count)
    rows = []
    for q in res.get("quotes", []):
        rows.append({k: _clean(v) for k, v in {
            "symbol": q.get("symbol"),
            "name": q.get("shortName"),
            "type": q.get("quoteType"),
            "price": q.get("regularMarketPrice"),
            "change_pct_today": q.get("regularMarketChangePercent"),
            "volume": q.get("regularMarketVolume"),
            "market_cap": q.get("marketCap"),
            "forward_pe": q.get("forwardPE"),
        }.items() if v is not None})
    return rows
