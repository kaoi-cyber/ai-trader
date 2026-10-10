"""Research and order functions shared by the API agent (brain.py) and the CLI (trade.py)."""

import json
import time

import data
import risk
from broker import PaperBroker
from config import Settings


def build_tools(broker: PaperBroker, state: dict, s: Settings, log) -> list:
    """Plain functions; brain.py wraps them as Claude API tools, trade.py exposes them as CLI commands."""
    def get_portfolio() -> str:
        """Current cash, positions marked to market, unrealized P&L, and today's starting value."""
        snap = broker.snapshot()
        snap["value_at_start_of_day_usd"] = round(state.get("day_start_value", 0), 2)
        snap["realized_pnl_all_time_usd"] = round(state.get("realized_pnl", 0), 2)
        return json.dumps(snap)

    def screen_market(screen: str, count: int = 15) -> str:
        """List stocks or ETFs from a Yahoo Finance predefined screener.

        Args:
            screen: One of most_actives, day_gainers, day_losers, small_cap_gainers, aggressive_small_caps, growth_technology_stocks, undervalued_growth_stocks, undervalued_large_caps, most_shorted_stocks, top_etfs_us, top_performing_etfs, technology_etfs.
            count: Number of results, 1-25.
        """
        if screen not in data.SCREENS:
            return f"Unknown screen {screen!r}. Choose from: {', '.join(data.SCREENS)}"
        try:
            return json.dumps(data.screen(screen, max(1, min(count, 25))))
        except Exception as e:
            return f"Screener failed: {e!r}"

    def get_quotes(symbols: list[str]) -> str:
        """Live quote and fundamentals for up to 10 symbols: price, today's change, volume, market cap, P/E, 50/200-day averages, 52-week range, next earnings timestamp, and market state.

        Args:
            symbols: Ticker symbols, e.g. ["AAPL", "SPY", "BTC-USD"].
        """
        out = {}
        for sym in symbols[:10]:
            out[sym.upper()] = data.info(sym) or "not found"
        return json.dumps(out)

    def get_price_history(symbol: str, period: str = "3mo", interval: str = "1d") -> str:
        """Summarised price history: returns, high/low, volatility, 20/50-bar moving averages, and up to ~40 sampled closes.

        Args:
            symbol: Ticker symbol.
            period: One of 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y.
            interval: One of 15m, 1h, 1d, 1wk. Intraday intervals only work for periods up to 1mo.
        """
        h = data.history(symbol, period, interval)
        return json.dumps(h) if h else f"No history for {symbol} ({period}, {interval})"

    def place_order(symbol: str, side: str, amount_usd: float, confidence: float, reasoning: str) -> str:
        """Submit a paper market order. Hard risk limits are checked first; the order may be clamped to a smaller size or rejected, and the result says which.

        Args:
            symbol: Ticker symbol, e.g. "MSFT" or "ETH-USD".
            side: "buy" or "sell".
            amount_usd: Dollar value to buy, or dollar value of the position to sell. To close a position, pass its full value.
            confidence: 0.0-1.0, how confident you are in this trade's thesis.
            reasoning: The thesis for this trade, in one or two sentences.
        """
        quote = data.info(symbol)
        if not quote:
            return f"REJECTED: no quote found for {symbol}"
        sym = quote["symbol"]
        portfolio = broker.snapshot()
        verdict = risk.check(side, quote, amount_usd, confidence, portfolio, state, s)
        entry = {"type": "order", "symbol": sym, "side": side, "requested_usd": amount_usd,
                 "confidence": confidence, "reasoning": reasoning, "price": quote["price"],
                 "verdict": verdict.__dict__}
        if not verdict.approved:
            log(entry)
            print(f"  ✗ {side} {sym} ${amount_usd:,.0f}: {verdict.reason}")
            return f"REJECTED: {verdict.reason}"

        if side == "buy":
            fill = broker.buy(sym, verdict.amount_usd, quote["price"], quote["type"])
        else:
            fill = broker.sell(sym, verdict.amount_usd, quote["price"])
        state["trades_this_cycle"] = state.get("trades_this_cycle", 0) + 1
        state["trades_today"] = state.get("trades_today", 0) + 1
        state.setdefault("last_trade_ts", {})[sym] = time.time()
        recent = state.setdefault("recent_trades", [])
        recent.append({"time": time.strftime("%Y-%m-%d %H:%M"), "reasoning": reasoning,
                       **{k: round(v, 6) if isinstance(v, float) else v for k, v in fill.items()}})
        del recent[:-20]
        entry["fill"] = fill
        log(entry)
        print(f"  ✓ {side} {sym} ${fill['usd']:,.2f} @ {fill['fill_price']:,.4f}: {reasoning}")
        return f"FILLED ({verdict.reason}): {json.dumps(fill)}"

    return [get_portfolio, screen_market, get_quotes, get_price_history, place_order]
