from __future__ import annotations

import os

from web3 import Web3

W3: Web3 | None = None


def init_w3() -> None:
    """
    Optional chain client init for non-custodial read-only diagnostics.
    Payout signing is explicitly disabled in this module.
    """
    global W3
    rpc_url = os.getenv("RPC_URL", "").strip()
    if not rpc_url:
        raise RuntimeError("RPC_URL is required to initialize Web3 client")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Unable to connect to the configured RPC_URL")

    W3 = w3


async def subscribe_to_blocks() -> None:
    raise RuntimeError(
        "Direct websocket monitoring in utils.crypto is disabled. "
        "Use configured payment provider webhooks/polling instead."
    )


async def handle_pending_transactions() -> None:
    raise RuntimeError(
        "Legacy pending-transaction scanner is disabled. "
        "Use the payment provider abstraction instead."
    )


async def wait_for_transaction(_wallet_or_hash: str):
    raise RuntimeError(
        "wait_for_transaction is disabled. Payment detection must use provider APIs."
    )


def sign_and_send(_amount, _to):
    raise RuntimeError(
        "Direct private-key signing in bot runtime is disabled for safety. "
        "Use provider-managed payout APIs via TradeService."
    )
