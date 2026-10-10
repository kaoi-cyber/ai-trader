"""Settings loaded from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


def _load_dotenv() -> None:
    """Read .env next to this file so scheduled runs don't depend on the shell's environment.
    Variables already set in the environment win."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    model: str
    interval_seconds: int
    only_when_us_market_open: bool
    max_tool_calls_per_cycle: int
    max_web_searches_per_cycle: int

    # Paper account
    start_cash: float
    slippage_bps: float

    # Hard risk limits, enforced in code. Claude cannot override these.
    max_trade_usd: float
    max_position_pct: float
    max_crypto_pct: float
    max_daily_loss_pct: float
    max_trades_per_cycle: int
    max_trades_per_day: int
    symbol_cooldown_minutes: float
    min_confidence: float
    min_stock_price: float
    min_trade_usd: float

    state_file: str
    trade_log: str


def load_settings() -> Settings:
    _load_dotenv()
    if os.environ.get("MODE", "paper") != "paper":
        raise SystemExit("Only MODE=paper is supported for stocks right now.")
    return Settings(
        model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        interval_seconds=int(os.environ.get("INTERVAL_SECONDS", 1800)),
        only_when_us_market_open=os.environ.get("ONLY_WHEN_US_MARKET_OPEN", "true").lower() == "true",
        max_tool_calls_per_cycle=int(os.environ.get("MAX_TOOL_CALLS_PER_CYCLE", 25)),
        max_web_searches_per_cycle=int(os.environ.get("MAX_WEB_SEARCHES_PER_CYCLE", 5)),
        start_cash=_f("PAPER_START_CASH", 10_000),
        slippage_bps=_f("PAPER_SLIPPAGE_BPS", 5),
        max_trade_usd=_f("MAX_TRADE_USD", 1_000),
        max_position_pct=_f("MAX_POSITION_PCT", 15),
        max_crypto_pct=_f("MAX_CRYPTO_PCT", 25),
        max_daily_loss_pct=_f("MAX_DAILY_LOSS_PCT", 3),
        max_trades_per_cycle=int(os.environ.get("MAX_TRADES_PER_CYCLE", 3)),
        max_trades_per_day=int(os.environ.get("MAX_TRADES_PER_DAY", 10)),
        symbol_cooldown_minutes=_f("SYMBOL_COOLDOWN_MINUTES", 60),
        min_confidence=_f("MIN_CONFIDENCE", 0.6),
        min_stock_price=_f("MIN_STOCK_PRICE", 5),
        min_trade_usd=_f("MIN_TRADE_USD", 10),
        state_file=os.environ.get("STATE_FILE", "state-paper.json"),
        trade_log=os.environ.get("TRADE_LOG", "trades.jsonl"),
    )
