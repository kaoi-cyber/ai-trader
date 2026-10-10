"""Market data: on-chain Uniswap quotes (the price we can actually trade at) plus
optional CoinGecko history for broader context."""

import requests
from web3 import Web3

WETH_DECIMALS = 18
USDC_DECIMALS = 6

QUOTER_V2_ABI = [{
    "name": "quoteExactInputSingle",
    "type": "function",
    "stateMutability": "nonpayable",
    "inputs": [{
        "name": "params",
        "type": "tuple",
        "components": [
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "fee", "type": "uint24"},
            {"name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
    }],
    "outputs": [
        {"name": "amountOut", "type": "uint256"},
        {"name": "sqrtPriceX96After", "type": "uint160"},
        {"name": "initializedTicksCrossed", "type": "uint32"},
        {"name": "gasEstimate", "type": "uint256"},
    ],
}]


class UniswapQuoter:
    def __init__(self, rpc_url: str, network: dict):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
        self.net = network
        self.weth = Web3.to_checksum_address(network["weth"])
        self.usdc = Web3.to_checksum_address(network["usdc"])
        self.quoter = self.w3.eth.contract(
            address=Web3.to_checksum_address(network["quoter_v2"]), abi=QUOTER_V2_ABI
        )

    def quote(self, token_in: str, token_out: str, amount_in: int) -> int:
        """Exact output amount (base units) for selling amount_in, including pool fee and price impact."""
        out = self.quoter.functions.quoteExactInputSingle(
            (token_in, token_out, amount_in, self.net["pool_fee"], 0)
        ).call()
        return out[0]

    def usdc_to_weth(self, usdc_base_units: int) -> int:
        return self.quote(self.usdc, self.weth, usdc_base_units)

    def weth_to_usdc(self, weth_base_units: int) -> int:
        return self.quote(self.weth, self.usdc, weth_base_units)

    def eth_price_usd(self) -> float:
        """Mid-ish price: average of selling 0.01 ETH and buying with $30."""
        sell = self.weth_to_usdc(10**16) / 10**USDC_DECIMALS / 0.01
        buy_eth = self.usdc_to_weth(30 * 10**USDC_DECIMALS) / 10**WETH_DECIMALS
        return (sell + 30 / buy_eth) / 2


def coingecko_context() -> dict | None:
    """Hourly ETH prices for the last 7 days, summarised. Returns None if unavailable."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/ethereum/market_chart",
            params={"vs_currency": "usd", "days": 7},
            timeout=15,
        )
        r.raise_for_status()
        prices = [p[1] for p in r.json()["prices"]]
    except Exception:
        return None
    if len(prices) < 30:
        return None

    def pct(a: float, b: float) -> float:
        return round((b - a) / a * 100, 2)

    last = prices[-1]
    # ~hourly points: sample every 6h so the prompt stays small
    return {
        "change_1h_pct": pct(prices[-2], last),
        "change_24h_pct": pct(prices[-25], last),
        "change_7d_pct": pct(prices[0], last),
        "high_7d": round(max(prices), 2),
        "low_7d": round(min(prices), 2),
        "prices_every_6h_oldest_first": [round(p, 2) for p in prices[::6]],
    }
