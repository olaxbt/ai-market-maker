"""Wallet-based authentication for AI trading agents.

Allows agents (Claw nodes, AI bots) to register an account using their
on-chain wallet address instead of email/password.

Flow:
  1. Agent generates a signature over a challenge message using its private key
  2. Leaderboard verifies the signature recovers the wallet address
  3. On success, creates/authenticates the agent account
  4. Agent receives a session token + can register providers

Supports:
  - Ethereum (EIP-191 signed messages)
  - Solana (Ed25519 signed messages) — optional

This is separate from the email/password auth; agents use wallet auth,
human users use email auth. Both share the same LeadpageUser table.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from eth_account import Account  # pip: eth-account
from eth_account.messages import encode_defunct

# ── Challenge generation ──

_CHALLENGE_PREFIX = "leaderboard.olaxbt.xyz wants you to sign in with your wallet.\n\n"


def make_challenge(wallet: str, *, nonce: str | None = None) -> str:
    """Create a challenge message for wallet signature.

    Format:
        leaderboard.olaxbt.xyz wants you to sign in with your wallet.

        Wallet: 0x...
        Nonce: abc123
        Timestamp: 1234567890
    """
    ts = int(time.time())
    if nonce is None:
        nonce = secrets.token_hex(12)
    return f"{_CHALLENGE_PREFIX}Wallet: {wallet}\nNonce: {nonce}\nTimestamp: {ts}"


def parse_challenge(challenge: str) -> dict | None:
    """Parse a challenge message back into its components."""
    lines = challenge.strip().split("\n")
    wallet = None
    nonce = None
    for line in lines:
        if line.startswith("Wallet: "):
            wallet = line[8:].strip()
        if line.startswith("Nonce: "):
            nonce = line[7:].strip()
    if wallet:
        return {"wallet": wallet, "nonce": nonce}
    return None


def verify_wallet_signature(*, wallet: str, challenge: str, signature: str) -> bool:
    """Verify that `signature` was produced by `wallet` signing `challenge`.

    Uses EIP-191 (personal_sign) standard via eth_account.
    """
    try:
        message = encode_defunct(text=challenge)
        recovered = Account.recover_message(message, signature=signature)
        return recovered.lower() == wallet.lower()
    except Exception:
        return False


# ── Provider key generation ──


def generate_provider_key() -> str:
    """Generate a cryptographically random provider API key."""
    return f"lpk_{secrets.token_hex(24)}"


# ── Agent registration / login ──


def wallet_to_user_id(wallet: str) -> str:
    """Derive a deterministic user-id from a wallet address."""
    return f"wallet:{wallet.lower()}"


def wallet_to_email(wallet: str) -> str:
    """Derive a fake email for wallet-based users in the LeadpageUser table."""
    h = hashlib.sha256(wallet.lower().encode()).hexdigest()[:16]
    return f"wallet_{h}@agent.leaderboard.local"
