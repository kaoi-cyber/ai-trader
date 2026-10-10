# AI Trader

An autonomous paper-trading agent with Claude as the portfolio manager. It researches the market,
decides what to buy and sell across **US stocks, ETFs and crypto**, and places orders against a
simulated $10,000 account. Every order passes through hard risk limits enforced in code, which
the AI cannot override.

> **Paper trading only.** No real money is used. This is an experiment in AI agents, not
> financial advice, and nothing it produces is a recommendation to buy or sell anything.

## How it works

```
                 ┌──────────────────────────────────────────────┐
  each cycle     │  Briefing: portfolio, risk limits, recent    │
 ───────────────►│  trades, Claude's notes from last cycle      │
                 └──────────────────────┬───────────────────────┘
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  Claude researches                           │
                 │  screeners · quotes · price history · news   │
                 └──────────────────────┬───────────────────────┘
                                        ▼ place_order
                 ┌──────────────────────────────────────────────┐
                 │  risk.py: hard limits, may clamp or reject   │
                 └──────────────────────┬───────────────────────┘
                                        ▼
                 ┌──────────────────────────────────────────────┐
                 │  broker.py: paper fill at live price         │
                 └──────────────────────┬───────────────────────┘
                                        ▼
                 trades.jsonl + notes saved for the next cycle
```

- **Any ticker.** Claude finds candidates with Yahoo Finance screeners (most active, gainers,
  undervalued large caps, top ETFs, ...) rather than working from a fixed watchlist.
- **Memory between cycles.** At the end of each cycle Claude writes notes: its thesis and exit
  conditions for each position, and a watchlist with price levels. The next cycle starts from them.
- **Full audit trail.** Every order, including rejected ones, is logged with Claude's reasoning
  and confidence.

## Two ways to run it

| | Claude Code on a schedule | Standalone with the API |
|---|---|---|
| Entry point | `trade.py` + [ROUTINE.md](ROUTINE.md) | `agent.py` |
| Who drives the loop | A scheduled Claude Code task | Anthropic Python SDK tool runner |
| Cost | Your Claude subscription's usage | Pay-per-use API key |
| Runs | While the Claude app is open | Anywhere Python runs |

### Setup

```bash
git clone https://github.com/<you>/ai-trader.git
cd ai-trader
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # adjust limits; add ANTHROPIC_API_KEY only for API mode
```

### Option 1: Claude Code on a schedule

1. In the Claude desktop app, create a scheduled task. Use the contents of [ROUTINE.md](ROUTINE.md)
   as the prompt, with `/path/to/ai-trader` replaced by your clone's absolute path.
2. Schedule it during US market hours. For example, twice a day: ~9:45am and ~3:30pm New York time.
3. Click **Run now** once to approve the `trade.py` commands for future runs.

You can also drive it by hand:

```bash
.venv/bin/python trade.py begin                      # start a cycle, print the briefing
.venv/bin/python trade.py screen most_actives --count 10
.venv/bin/python trade.py quote NVDA SPY BTC-USD
.venv/bin/python trade.py history NVDA --period 6mo
.venv/bin/python trade.py order SPY buy 500 --confidence 0.7 --reason "core index position"
.venv/bin/python trade.py end --summary "..." --notes "..."
```

### Option 2: Standalone with the Anthropic API

```bash
.venv/bin/python agent.py --once     # one cycle
.venv/bin/python agent.py            # loop every INTERVAL_SECONDS during market hours
```

Uses `claude-opus-5-5` with adaptive thinking, structured output for the end-of-cycle summary,
Anthropic's web search tool for news, and server-side refusal fallbacks.

### Check results

```bash
.venv/bin/python trade.py status     # portfolio, P&L and Claude's latest notes
```

To start over, delete `state-paper.json` and `trades.jsonl`.

## Risk limits

All limits are enforced in [risk.py](risk.py) and configurable in `.env`.

| Limit | Default |
|---|---|
| Max per buy | $1,000 |
| Max per position | 15% of portfolio |
| Max total crypto | 25% of portfolio |
| Daily loss before new buys halt | 3% |
| Trades per cycle / per day | 3 / 10 |
| Cooldown before re-trading a symbol | 60 min |
| Minimum confidence | 0.6 |
| Minimum stock price | $5 |
| Stocks/ETFs only during regular US hours | always |
| Long-only and cash-only: no shorting, margin or options | always |

Sells are never blocked by the size or loss limits, because exiting a position always reduces risk.

## Project layout

| File | Purpose |
|---|---|
| `trade.py` | Command-line tools for Claude Code mode |
| `agent.py` | Standalone loop for API mode |
| `brain.py` | System prompt and Claude API tool runner (API mode) |
| `tools.py` | Research and order functions shared by both modes |
| `risk.py` | Hard risk limits |
| `broker.py` | Paper broker: cash, positions, fills, P&L |
| `data.py` | Market data from Yahoo Finance (yfinance) |
| `session.py` | State, logging, cycle start and finish |
| `config.py` | Settings from `.env` |
| `ROUTINE.md` | Prompt for the scheduled Claude Code task |
| `onchain/` | Experimental Uniswap V3 on Base code (live quotes and swaps). Not wired in yet |

## Limitations

- Paper fills use the current Yahoo price plus 5 bps of slippage. Real fills are worse, especially
  for small caps and near the open and close, so paper results are optimistic.
- yfinance is an unofficial Yahoo Finance wrapper and can break or get rate-limited.
- Market-hours detection relies on Yahoo's market state. If it's wrong, stock orders are rejected.
- An LLM can't reliably predict prices. Judge the agent against simply holding SPY over the same
  period.

## Roadmap

- Dashboard: equity curve vs SPY, positions, and reasoning for each trade
- Backtesting harness to replay history through the same risk limits
- Live broker adapter (e.g. Alpaca) behind the same interface as `PaperBroker`
- Wire `onchain/` into the agent for live crypto on Base

## License

[MIT](LICENSE)
