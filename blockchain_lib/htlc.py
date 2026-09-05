"""HTLC escrow primitives taught in notebook 9.

Notebook 9 imports ``HTLCManager`` from this module after explaining
lock, claim, and refund in prose. The hash helper is
``blockchain_lib.merkle.sha256`` — same digest as notebook 3.
"""

from __future__ import annotations

import json
from typing import Any

from blockchain_lib.merkle import sha256
from blockchain_lib.stablecoin import Blockchain, TokenLedger


class HTLCManager:
    """Manage hash-locked, time-limited escrows on one chain."""

    def __init__(self, blockchain: Blockchain, ledger: TokenLedger) -> None:
        """Bind this manager to one named chain and its token ledger.

        Args:
            blockchain: Chain whose height and name this escrow uses.
            ledger: Token ledger that debit/credits the locked amount.
        """
        self.blockchain = blockchain
        self.ledger = ledger
        self.locks: dict[str, dict[str, Any]] = {}

    def lock(
        self,
        sender: str,
        receiver: str,
        amount: float,
        hash_lock: str,
        timelock_height: int,
    ) -> bool:
        """Escrow funds behind a hash until they are claimed or expire.

        Args:
            sender: Holder whose tokens are debited now.
            receiver: Party who may claim by revealing the secret.
            amount: Tokens to lock. Must be positive.
            hash_lock: SHA-256 of the secret; safe to share.
            timelock_height: Height at which ``sender`` may refund.

        Returns:
            True if the debit succeeded and the lock was recorded.
        """
        if not self.ledger.lock_for_htlc(sender, amount, hash_lock):
            return False
        self.locks[hash_lock] = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timelock_height": timelock_height,
            "claimed": False,
        }
        return True

    def claim(self, hash_lock: str, secret: str) -> bool:
        """Reveal a matching secret and release the escrow to its receiver.

        Args:
            hash_lock: Hash that identifies the lock.
            secret: Preimage of ``hash_lock``. Published on-chain.

        Returns:
            True if the secret matched and funds were released.
        """
        lock = self.locks.get(hash_lock)
        if lock is None or lock["claimed"] or sha256(secret) != hash_lock:
            print(f"  [{self.blockchain.name}] CLAIM FAILED.")
            return False
        lock["claimed"] = True
        record = json.dumps(
            {
                "event": "HTLC_CLAIM",
                "receiver": lock["receiver"],
                "amount": lock["amount"],
                "hash_lock": hash_lock,
                "revealed_secret": secret,
            },
            sort_keys=True,
        )
        self.ledger.record_payload(record)
        print(
            f"  [{self.blockchain.name}] CLAIM: secret revealed on-chain = {secret!r}"
        )
        self.ledger.release_to(lock["receiver"], lock["amount"])
        return True

    def refund(self, hash_lock: str, current_height: int) -> bool:
        """Return unclaimed escrow after its supplied height expires.

        Args:
            hash_lock: Hash that identifies the lock.
            current_height: Chain height used to test the timelock.

        Returns:
            True if the lock had expired and funds were returned.
        """
        lock = self.locks.get(hash_lock)
        if lock is None or lock["claimed"] or current_height < lock["timelock_height"]:
            return False
        record = json.dumps(
            {
                "event": "HTLC_REFUND",
                "sender": lock["sender"],
                "amount": lock["amount"],
            },
            sort_keys=True,
        )
        self.ledger.record_payload(record)
        self.ledger.refund_to(lock["sender"], lock["amount"])
        return True
