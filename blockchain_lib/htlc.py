"""HTLC escrow primitives taught in notebook 9.

Notebook 9 defines ``HTLCManager`` inline so the lesson can be read in
one place. This module is the copy a later notebook would import.
"""

from __future__ import annotations

import json

from blockchain_lib.merkle import sha256
from blockchain_lib.stablecoin import Blockchain, TokenLedger


class HTLCManager:
    """Manage hash-locked, time-limited escrows on one chain."""

    def __init__(self, blockchain: Blockchain, ledger: TokenLedger) -> None:
        self.blockchain = blockchain
        self.ledger = ledger
        self.locks: dict[str, dict] = {}

    def lock(
        self,
        sender: str,
        receiver: str,
        amount: float,
        hash_lock: str,
        timelock_height: int,
    ) -> bool:
        """Escrow funds behind a hash until they are claimed or expire."""
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
        """Reveal a matching secret and release the escrow to its receiver."""
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
            f"  [{self.blockchain.name}] CLAIM: "
            f"secret revealed on-chain = {secret!r}"
        )
        self.ledger.release_to(lock["receiver"], lock["amount"])
        return True

    def refund(self, hash_lock: str, current_height: int) -> bool:
        """Return unclaimed escrow after its supplied height expires."""
        lock = self.locks.get(hash_lock)
        if (
            lock is None
            or lock["claimed"]
            or current_height < lock["timelock_height"]
        ):
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
