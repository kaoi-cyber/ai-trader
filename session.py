"""State, logging and the start/finish of a trading cycle, shared by agent.py (API mode)
and trade.py (Claude Code mode)."""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import data
from broker import PaperBroker
from config import Settings

NY = ZoneInfo("America/New_York")
HERE = os.path.dirname(os.path.abspath(__file__))


def _path(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def load_state(s: Settings) -> dict:
    path = _path(s.state_file)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_state(s: Settings, state: dict) -> None:
    path = _path(s.state_file)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def make_logger(s: Settings):
    path = _path(s.trade_log)

    def log(event: dict) -> None:
        event = {"ts": datetime.now(NY).isoformat(timespec="seconds"), **event}
        with open(path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")
    return log


def portfolio_text(snap: dict, state: dict, start_cash: float) -> str:
    total = snap["total_value_usd"]
    lines = [f"Portfolio ${total:,.2f} ({(total / start_cash - 1) * 100:+.2f}% since start) | "
             f"cash ${snap['cash_usd']:,.2f} | realized P&L ${state.get('realized_pnl', 0):,.2f}"]
    for p in snap["positions"]:
        lines.append(f"  {p['symbol']:<10} ${p['value_usd']:>10,.2f}  {p['unrealized_pnl_pct']:+.2f}%")
    return "\n".join(lines)


def start_cycle(s: Settings, broker: PaperBroker, state: dict) -> dict:
    """Roll the trading day if needed, reset the per-cycle trade counter, return the briefing."""
    snap = broker.snapshot()
    today = datetime.now(NY).date().isoformat()
    if state.get("day") != today:
        state.update(day=today, day_start_value=snap["total_value_usd"], trades_today=0)
    state["trades_this_cycle"] = 0
    return {
        "time_new_york": datetime.now(NY).strftime("%A %Y-%m-%d %H:%M"),
        "us_market_open": data.us_market_open(),
        "portfolio": snap,
        "value_at_start_of_day_usd": round(state["day_start_value"], 2),
        "risk_limits": {
            "max_trade_usd": s.max_trade_usd,
            "max_position_pct_of_portfolio": s.max_position_pct,
            "max_crypto_pct_of_portfolio": s.max_crypto_pct,
            "max_daily_loss_pct_before_buys_halt": s.max_daily_loss_pct,
            "max_trades_this_cycle": s.max_trades_per_cycle,
            "trades_left_today": max(0, s.max_trades_per_day - state.get("trades_today", 0)),
            "symbol_cooldown_minutes": s.symbol_cooldown_minutes,
            "min_confidence": s.min_confidence,
            "min_stock_price": s.min_stock_price,
        },
        "recent_trades": state.get("recent_trades", [])[-8:],
        "your_notes_from_last_cycle": state.get("notes", "(first cycle, no notes yet)"),
    }


def finish_cycle(s: Settings, broker: PaperBroker, state: dict, log, summary: str, notes: str) -> dict:
    if notes:
        state["notes"] = notes
    after = broker.snapshot()
    log({"type": "cycle", "summary": summary, "notes": notes,
         "total_value_usd": after["total_value_usd"], "cash_usd": after["cash_usd"]})
    return after
