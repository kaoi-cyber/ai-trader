# Changelog

## v1.0.0

First release.

- Paper-trading account with a $10,000 starting balance for US stocks, ETFs and crypto (USD pairs)
- Claude as portfolio manager, with research tools: market screeners, quotes and fundamentals,
  price history, and web search for news
- Hard risk limits enforced in code: trade size, position size, crypto allocation, daily loss halt,
  trade count, per-symbol cooldown, minimum confidence, penny-stock filter, market hours,
  and long-only/cash-only trading
- Two run modes: scheduled Claude Code task (`trade.py` + `ROUTINE.md`) or standalone Anthropic
  API agent (`agent.py`)
- Cross-cycle memory through notes Claude writes for itself
- JSONL audit log of every order (filled or rejected) and cycle summary
- Experimental Uniswap V3 on Base module (`onchain/`), not yet connected to the agent
