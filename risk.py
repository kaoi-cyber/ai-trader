"""Hard limits enforced in code, between Claude's order and the broker."""

import time
from dataclasses import dataclass

from config import Settings
from data import TRADABLE_TYPES


@dataclass
class Verdict:
    approved: bool
    amount_usd: float
    reason: str


def check(side: str, quote: dict, amount_usd: float, confidence: float,
          portfolio: dict, state: dict, s: Settings) -> Verdict:
    symbol = quote["symbol"]
    kind = quote.get("type")
    px = quote["price"]
    total = portfolio["total_value_usd"]
    held = next((p for p in portfolio["positions"] if p["symbol"] == symbol), None)
    held_value = held["value_usd"] if held else 0.0

    if side not in ("buy", "sell"):
        return Verdict(False, 0, "side must be 'buy' or 'sell'")
    if kind not in TRADABLE_TYPES:
        return Verdict(False, 0, f"{symbol} is a {kind}; only stocks, ETFs and crypto are allowed")
    if quote.get("currency") != "USD":
        return Verdict(False, 0, f"{symbol} trades in {quote.get('currency')}; only USD-priced assets are allowed")
    if kind != "CRYPTOCURRENCY" and quote.get("market_state") != "REGULAR":
        return Verdict(False, 0, f"US market is not in regular hours (state: {quote.get('market_state')}); stocks/ETFs can't be traded now")
    if confidence < s.min_confidence:
        return Verdict(False, 0, f"Confidence {confidence:.2f} is below the minimum of {s.min_confidence}")
    if state.get("trades_this_cycle", 0) >= s.max_trades_per_cycle:
        return Verdict(False, 0, f"Already made {s.max_trades_per_cycle} trades this cycle")
    if state.get("trades_today", 0) >= s.max_trades_per_day:
        return Verdict(False, 0, f"Daily trade limit of {s.max_trades_per_day} reached")

    last = state.get("last_trade_ts", {}).get(symbol)
    if last and (time.time() - last) / 60 < s.symbol_cooldown_minutes:
        return Verdict(False, 0, f"{symbol} was traded under {s.symbol_cooldown_minutes:.0f} min ago (cooldown)")

    amount = max(amount_usd, 0)
    notes = []

    if side == "sell":
        if not held:
            return Verdict(False, 0, f"No {symbol} position to sell (shorting is not allowed)")
        if amount > held_value:
            amount = held_value
            notes.append(f"clamped to position value ${held_value:,.2f}")
        # Selling always reduces risk, so the size, daily-loss and allocation limits don't block it.
    else:
        if amount > s.max_trade_usd:
            amount = s.max_trade_usd
            notes.append(f"clamped to max trade ${s.max_trade_usd:,.0f}")
        day_start = state.get("day_start_value")
        if day_start and total < day_start * (1 - s.max_daily_loss_pct / 100):
            return Verdict(False, 0, f"Daily loss limit hit (${total:,.2f} vs ${day_start:,.2f} at day start). No new buys until tomorrow; sells are still allowed.")
        if kind != "CRYPTOCURRENCY" and px < s.min_stock_price:
            return Verdict(False, 0, f"{symbol} is ${px:.2f}, below the ${s.min_stock_price:.0f} minimum stock price")
        caps = {
            "cash": portfolio["cash_usd"],
            f"{s.max_position_pct:.0f}% per-position cap": s.max_position_pct / 100 * total - held_value,
        }
        if kind == "CRYPTOCURRENCY":
            caps[f"{s.max_crypto_pct:.0f}% crypto cap"] = s.max_crypto_pct / 100 * total - portfolio["crypto_usd"]
        binding, cap = min(caps.items(), key=lambda kv: kv[1])
        if amount > cap:
            amount = max(cap, 0)
            notes.append(f"clamped to ${amount:,.2f} by {binding}")

    if amount < s.min_trade_usd:
        return Verdict(False, 0, f"Trade size ${amount:,.2f} is below the ${s.min_trade_usd:.0f} minimum" + (f" ({'; '.join(notes)})" if notes else ""))
    return Verdict(True, round(amount, 2), "Approved" + (f" ({'; '.join(notes)})" if notes else ""))
