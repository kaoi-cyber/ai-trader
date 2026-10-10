"""Executes approved trades: simulated (paper) or as real Uniswap V3 swaps."""

from web3 import Web3

from onchain.uniswap import USDC_DECIMALS, WETH_DECIMALS, UniswapQuoter

ERC20_ABI = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "owner", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bool"}]},
]

SWAP_ROUTER02_ABI = [{
    "name": "exactInputSingle",
    "type": "function",
    "stateMutability": "payable",
    "inputs": [{
        "name": "params",
        "type": "tuple",
        "components": [
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "recipient", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMinimum", "type": "uint256"},
            {"name": "sqrtPriceLimitX96", "type": "uint160"},
        ],
    }],
    "outputs": [{"name": "amountOut", "type": "uint256"}],
}]

MIN_GAS_ETH = 0.0005


class PaperExecutor:
    """Fills at the real on-chain quote (fee and price impact included) but never sends a transaction."""

    def __init__(self, quoter: UniswapQuoter, state: dict, start_usdc: float):
        self.quoter = quoter
        self.state = state
        state.setdefault("paper_balances", {"usdc": start_usdc, "weth": 0.0})

    def balances(self) -> tuple[float, float]:
        b = self.state["paper_balances"]
        return b["usdc"], b["weth"]

    def buy(self, usd: float, price: float) -> dict:
        weth_out = self.quoter.usdc_to_weth(int(usd * 10**USDC_DECIMALS)) / 10**WETH_DECIMALS
        b = self.state["paper_balances"]
        b["usdc"] -= usd
        b["weth"] += weth_out
        return {"side": "buy_eth", "usdc_in": usd, "weth_out": weth_out, "fill_price": usd / weth_out, "tx": None}

    def sell(self, usd: float, price: float) -> dict:
        b = self.state["paper_balances"]
        weth_in = min(usd / price, b["weth"])
        usdc_out = self.quoter.weth_to_usdc(int(weth_in * 10**WETH_DECIMALS)) / 10**USDC_DECIMALS
        b["weth"] -= weth_in
        b["usdc"] += usdc_out
        return {"side": "sell_eth", "weth_in": weth_in, "usdc_out": usdc_out, "fill_price": usdc_out / weth_in, "tx": None}


class OnchainExecutor:
    """Signs and sends real swaps through Uniswap's SwapRouter02. Trades WETH, not native ETH;
    keep some native ETH in the wallet for gas."""

    def __init__(self, quoter: UniswapQuoter, s: object):
        self.quoter = quoter
        self.w3 = quoter.w3
        self.s = s
        self.account = self.w3.eth.account.from_key(s.private_key)
        self.address = self.account.address
        if self.w3.eth.chain_id != s.network["chain_id"]:
            raise SystemExit(f"RPC chain id {self.w3.eth.chain_id} != expected {s.network['chain_id']}")
        self.router_addr = Web3.to_checksum_address(s.network["swap_router02"])
        self.router = self.w3.eth.contract(address=self.router_addr, abi=SWAP_ROUTER02_ABI)
        self.usdc = self.w3.eth.contract(address=quoter.usdc, abi=ERC20_ABI)
        self.weth = self.w3.eth.contract(address=quoter.weth, abi=ERC20_ABI)

    def balances(self) -> tuple[float, float]:
        usdc = self.usdc.functions.balanceOf(self.address).call() / 10**USDC_DECIMALS
        weth = self.weth.functions.balanceOf(self.address).call() / 10**WETH_DECIMALS
        return usdc, weth

    def _send(self, fn) -> str:
        tx = fn.build_transaction({
            "from": self.address,
            "nonce": self.w3.eth.get_transaction_count(self.address, "pending"),
            "chainId": self.s.network["chain_id"],
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt["status"] != 1:
            raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
        return tx_hash.hex()

    def _swap(self, token, token_in: str, token_out: str, amount_in: int) -> tuple[int, str]:
        gas_eth = self.w3.eth.get_balance(self.address) / 10**18
        if gas_eth < MIN_GAS_ETH:
            raise RuntimeError(f"Only {gas_eth:.6f} ETH for gas; top up the wallet")

        if token.functions.allowance(self.address, self.router_addr).call() < amount_in:
            # Approve only the amount needed rather than an unlimited allowance.
            self._send(token.functions.approve(self.router_addr, amount_in))

        quoted = self.quoter.quote(token_in, token_out, amount_in)
        min_out = quoted * (10_000 - self.s.max_slippage_bps) // 10_000
        tx = self._send(self.router.functions.exactInputSingle(
            (token_in, token_out, self.s.network["pool_fee"], self.address, amount_in, min_out, 0)
        ))
        return quoted, tx

    def buy(self, usd: float, price: float) -> dict:
        amount_in = int(usd * 10**USDC_DECIMALS)
        out, tx = self._swap(self.usdc, self.quoter.usdc, self.quoter.weth, amount_in)
        weth_out = out / 10**WETH_DECIMALS
        return {"side": "buy_eth", "usdc_in": usd, "weth_out_quoted": weth_out, "fill_price": usd / weth_out, "tx": tx}

    def sell(self, usd: float, price: float) -> dict:
        held = self.weth.functions.balanceOf(self.address).call()
        amount_in = min(int(usd / price * 10**WETH_DECIMALS), held)
        out, tx = self._swap(self.weth, self.quoter.weth, self.quoter.usdc, amount_in)
        weth_in = amount_in / 10**WETH_DECIMALS
        usdc_out = out / 10**USDC_DECIMALS
        return {"side": "sell_eth", "weth_in": weth_in, "usdc_out_quoted": usdc_out, "fill_price": usdc_out / weth_in, "tx": tx}
