"""Shared stablecoin teaching primitives for notebooks 7 and 8."""

import json

from blockchain_lib.pos import Block, Validator
from blockchain_lib.pos import Blockchain as PoSBlockchain

BLOCK_REWARD: float = 2.0
FEE_PER_TX: float = 0.1


class Blockchain(PoSBlockchain):
    """PoS blockchain extended with a readable name and proposer rewards."""

    def __init__(self, name: str, validators: list[Validator]) -> None:
        super().__init__(validators)
        self.name = name

    def add_block(self, data: str) -> tuple[Block, Validator]:
        """Append a block through the shared PoS implementation and pay its proposer."""
        block, proposer = super().add_block(data)
        proposer.stake += BLOCK_REWARD + FEE_PER_TX
        return block, proposer


class TokenLedger:
    """Minimal on-chain token ledger for stablecoin and HTLC lessons."""

    def __init__(self, symbol: str, blockchain: Blockchain) -> None:
        self.symbol = symbol
        self.blockchain = blockchain
        self.balances: dict[str, float] = {}
        self.total_supply: float = 0.0

    @staticmethod
    def _require_positive(amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive.")

    def _record(self, record: dict[str, str | float]) -> None:
        self.blockchain.add_block(json.dumps(record, sort_keys=True))

    def mint(self, to: str, amount: float) -> None:
        self._require_positive(amount)
        self.balances[to] = self.balances.get(to, 0) + amount
        self.total_supply += amount
        self._record({"event": "MINT", "symbol": self.symbol, "to": to, "amount": amount})

    def transfer(self, sender: str, receiver: str, amount: float) -> bool:
        self._require_positive(amount)
        if self.balances.get(sender, 0) < amount:
            return False
        self.balances[sender] -= amount
        self.balances[receiver] = self.balances.get(receiver, 0) + amount
        self._record(
            {
                "event": "TRANSFER",
                "symbol": self.symbol,
                "from": sender,
                "to": receiver,
                "amount": amount,
            }
        )
        return True

    def burn(self, holder: str, amount: float) -> bool:
        self._require_positive(amount)
        if self.balances.get(holder, 0) < amount:
            return False
        self.balances[holder] -= amount
        self.total_supply -= amount
        self._record(
            {"event": "BURN", "symbol": self.symbol, "holder": holder, "amount": amount}
        )
        return True

    def lock_for_htlc(self, holder: str, amount: float, hash_lock: str) -> bool:
        self._require_positive(amount)
        if self.balances.get(holder, 0) < amount:
            return False
        self.balances[holder] -= amount
        self._record(
            {
                "event": "HTLC_LOCK",
                "symbol": self.symbol,
                "holder": holder,
                "amount": amount,
                "hash_lock": hash_lock,
            }
        )
        return True

    def release_to(self, receiver: str, amount: float) -> None:
        self._require_positive(amount)
        self.balances[receiver] = self.balances.get(receiver, 0) + amount

    def refund_to(self, sender: str, amount: float) -> None:
        self._require_positive(amount)
        self.balances[sender] = self.balances.get(sender, 0) + amount
