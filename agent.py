"""API mode: runs on its own, calling Claude through the paid Anthropic API.
For the subscription-based alternative, see trade.py and ROUTINE.md.

    python agent.py            # run forever, one cycle every INTERVAL_SECONDS
    python agent.py --once     # run a single cycle and exit
    python agent.py --status   # print the paper portfolio and exit (no Claude call)
"""

import argparse
import time
from datetime import datetime

import data
import session
from broker import PaperBroker
from config import load_settings
from session import NY


def cycle(s, broker, brain, state, log) -> None:
    from brain import build_tools

    briefing = session.start_cycle(s, broker, state)
    print(f"\n=== {datetime.now(NY):%Y-%m-%d %H:%M} ET ===")
    print(session.portfolio_text(briefing["portfolio"], state, s.start_cash))

    result = brain.run_cycle(briefing, build_tools(broker, state, s, log))
    print(f"Claude: {result.get('summary', '')}")
    session.finish_cycle(s, broker, state, log, result.get("summary", ""), result.get("notes_for_next_time", ""))
    session.save_state(s, state)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--status", action="store_true", help="print the portfolio and exit")
    args = parser.parse_args()

    s = load_settings()
    state = session.load_state(s)
    broker = PaperBroker(state, s.start_cash, s.slippage_bps)

    if args.status:
        print(session.portfolio_text(broker.snapshot(), state, s.start_cash))
        return

    from brain import Brain
    brain = Brain(s)
    log = session.make_logger(s)
    print(f"PAPER TRADING | model {s.model} | every {s.interval_seconds // 60} min"
          f"{' during US market hours' if s.only_when_us_market_open else ''} | state {s.state_file}")

    while True:
        try:
            if s.only_when_us_market_open and not data.us_market_open():
                print(f"{datetime.now(NY):%H:%M} ET: US market closed, skipping cycle")
            else:
                cycle(s, broker, brain, state, log)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # One bad cycle (data outage, API error) shouldn't kill the agent.
            print(f"Cycle failed: {e!r}")
            log({"type": "cycle_error", "error": repr(e)})
            session.save_state(s, state)
        if args.once:
            break
        time.sleep(s.interval_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
