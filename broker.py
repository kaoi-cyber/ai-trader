"""Paper broker: a simulated cash account. Long-only, no margin, no shorting.

Fills at the current Yahoo price plus a small simulated slippage. Real fills would differ
(spreads, partial fills, after-hours gaps), so treat paper results as optimistic."""

import data


class PaperBroker:
    def __init__(self, state: dict, start_cash: float, slippage_bps: float):
        self.state = state
        self.slip = slippage_bps / 10_000
        state.setdefault("cash", start_cash)
        state.setdefault("positions", {})  # symbol -> {qty, cost_basis, type}

    @property
    def cash(self) -> float:
        return self.state["cash"]

    @property
    def positions(self) -> dict:
        return self.state["positions"]

    def snapshot(self) -> dict:
        """Mark every position to market."""
        rows, invested, crypto = [], 0.0, 0.0
        for sym, p in self.positions.items():
            px = data.price(sym)
            if px is None:
                px = p["cost_basis"] / p["qty"]  # fall back to cost if a quote fails
            value = p["qty"] * px
            invested += value
            if p["type"] == "CRYPTOCURRENCY":
                crypto += value
            rows.append({
                "symbol": sym,
                "type": p["type"],
                "qty": round(p["qty"], 8),
                "price": round(px, 4),
                "value_usd": round(value, 2),
                "cost_basis_usd": round(p["cost_basis"], 2),
                "unrealized_pnl_usd": round(value - p["cost_basis"], 2),
                "unrealized_pnl_pct": round((value / p["cost_basis"] - 1) * 100, 2) if p["cost_basis"] else None,
            })
        total = self.cash + invested
        return {
            "cash_usd": round(self.cash, 2),
            "invested_usd": round(invested, 2),
            "crypto_usd": round(crypto, 2),
            "total_value_usd": round(total, 2),
            "positions": sorted(rows, key=lambda r: -r["value_usd"]),
        }

    def buy(self, symbol: str, usd: float, px: float, asset_type: str) -> dict:
        fill_px = px * (1 + self.slip)
        qty = usd / fill_px
        self.state["cash"] -= usd
        p = self.positions.setdefault(symbol, {"qty": 0.0, "cost_basis": 0.0, "type": asset_type})
        p["qty"] += qty
        p["cost_basis"] += usd
        return {"symbol": symbol, "side": "buy", "qty": qty, "fill_price": fill_px, "usd": usd}

    def sell(self, symbol: str, usd: float, px: float) -> dict:
        p = self.positions[symbol]
        fill_px = px * (1 - self.slip)
        position_value = p["qty"] * fill_px
        # Selling (nearly) everything closes the position cleanly instead of leaving dust.
        qty = p["qty"] if usd >= position_value * 0.99 else usd / fill_px
        proceeds = qty * fill_px
        cost_removed = p["cost_basis"] * qty / p["qty"]
        realized = proceeds - cost_removed
        p["qty"] -= qty
        p["cost_basis"] -= cost_removed
        if p["qty"] <= 1e-12:
            del self.positions[symbol]
        self.state["cash"] += proceeds
        self.state["realized_pnl"] = self.state.get("realized_pnl", 0.0) + realized
        return {"symbol": symbol, "side": "sell", "qty": qty, "fill_price": fill_px,
                "usd": proceeds, "realized_pnl_usd": realized}
