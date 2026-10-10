"""Uniswap V3 deployments on Base. Not wired into the paper trader yet; kept for a future live-crypto mode."""

# Uniswap V3 deployments. Verify against https://docs.uniswap.org/contracts/v3/reference/deployments
# before trading real funds.
NETWORKS = {
    "base": {
        "chain_id": 8453,
        "default_rpc": "https://mainnet.base.org",
        "weth": "0x4200000000000000000000000000000000000006",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "quoter_v2": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
        "swap_router02": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "pool_fee": 500,  # 0.05% WETH/USDC pool, the deepest on Base
    },
    "base-sepolia": {
        "chain_id": 84532,
        "default_rpc": "https://sepolia.base.org",
        "weth": "0x4200000000000000000000000000000000000006",
        "usdc": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "quoter_v2": "0xC5290058841028F1614F3A6F0F5816cAd0df5E27",
        "swap_router02": "0x94cC0AaC535CCDB3C01d6787D6413C739ae12bc4",
        "pool_fee": 3000,  # testnet liquidity is thin and varies; override with POOL_FEE
    },
}

