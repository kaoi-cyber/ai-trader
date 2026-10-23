"""Command-line trading tools, so Claude Code (on your subscription) can be the decision-maker
instead of the paid API. Every order still goes through the same hard risk limits.

    python trade.py begin                          # start a cycle; prints the briefing as JSON
    python trade.py portfolio
    python trade.py screen most_actives --count 15
    python trade.py quote AAPL MSFT BTC-USD
    python trade.py history NVDA --period 6mo --interval 1d
    python trade.py order NVDA buy 500 --confidence 0.7 --reason "..."
    python trade.py end --summary "..." --notes "..."
    python trade.py status                         # human-readable portfolio
"""

import argparse
import json
import sys
from datetime import datetime

import data
import session
import tools
from broker import PaperBroker
from config import load_settings


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("begin", help="start a trading cycle and print the briefing")
    sub.add_parser("portfolio", help="portfolio as JSON")
    sub.add_parser("status", help="portfolio as text")

    sp = sub.add_parser("screen", help="Yahoo predefined screener")
    sp.add_argument("name")
    sp.add_argument("--count", type=int, default=15)

    sp = sub.add_parser("quote", help="quotes for up to 10 symbols")
    sp.add_argument("symbols", nargs="+")

    sp = sub.add_parser("history", help="summarised price history")
    sp.add_argument("symbol")
    sp.add_argument("--period", default="3mo")
    sp.add_argument("--interval", default="1d")

    sp = sub.add_parser("order", help="submit a paper order (risk-checked)")
    sp.add_argument("symbol")
    sp.add_argument("side", choices=["buy", "sell"])
    sp.add_argument("amount_usd", type=float)
    sp.add_argument("--confidence", type=float, required=True)
    sp.add_argument("--reason", required=True)

    sp = sub.add_parser("end", help="finish the cycle and save notes for next time")
    sp.add_argument("--summary", required=True)
    sp.add_argument("--notes", required=True)

    args = p.parse_args()
    s = load_settings()
    lock = session.lock_state(s)  # noqa: F841 (held until exit)
    state = session.load_state(s)
    broker = PaperBroker(state, s.start_cash, s.slippage_bps)
    log = session.make_logger(s)
    t = {f.__name__: f for f in tools.build_tools(broker, state, s, log)}

    if args.cmd == "begin":
        if s.only_when_us_market_open and not data.us_market_open():
            print("MARKET_CLOSED: the US market is not open. End this run without trading.")
        elif not session.claim_cycle(state):
            started = datetime.fromtimestamp(state["cycle_started_ts"], session.NY)
            print(f"CYCLE_IN_PROGRESS: another trading run started at {started:%H:%M} New York time "
                  "and hasn't finished. End this run without trading.")
        else:
            print(json.dumps(session.start_cycle(s, broker, state), indent=2))
    elif args.cmd == "portfolio":
        print(t["get_portfolio"]())
    elif args.cmd == "status":
        print(session.portfolio_text(broker.snapshot(), state, s.start_cash))
        if state.get("notes"):
            print("\nLatest notes:\n" + state["notes"])
    elif args.cmd == "screen":
        print(t["screen_market"](args.name, args.count))
    elif args.cmd == "quote":
        print(t["get_quotes"](args.symbols))
    elif args.cmd == "history":
        print(t["get_price_history"](args.symbol, args.period, args.interval))
    elif args.cmd == "order":
        print(t["place_order"](args.symbol, args.side, args.amount_usd, args.confidence, args.reason))
    elif args.cmd == "end":
        after = session.finish_cycle(s, broker, state, log, args.summary, args.notes)
        print(session.portfolio_text(after, state, s.start_cash))

    session.save_state(s, state)


if __name__ == "__main__":
    sys.exit(main())
