"""Shared stablecoin teaching primitives for notebooks 8 and 9."""

import json
import math

from blockchain_lib.mempool import Network, Transaction
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

    def accept_candidate(self, block: Block) -> None:
        """Append a mempool-included candidate and pay its named proposer."""
        super().accept_candidate(block)
        proposer = next(v for v in self.validators if v.name == block.proposer)
        proposer.stake += BLOCK_REWARD + FEE_PER_TX


class TokenLedger:
    """Minimal on-chain token ledger for stablecoin and HTLC lessons."""

    def __init__(
        self, symbol: str, blockchain: Blockchain, network: Network
    ) -> None:
        self.symbol = symbol
        self.blockchain = blockchain
        self.network = network
        self.balances: dict[str, float] = {}
        self.total_supply: float = 0.0

    @staticmethod
    def _require_positive(amount: float) -> None:
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Amount must be positive.")

    def record_payload(self, payload: str, tx_id: str | None = None) -> None:
        """Gossip ``payload`` as a ``Transaction`` and include it from the origin."""
        tx = Transaction(
            tx_id or f"{self.symbol}-{len(self.blockchain.chain)}",
            payload,
        )
        origin = self.network.node_names[0]
        self.network.broadcast(tx, origin)
        self.network.include(origin, tx.tx_id, self.blockchain)

    def _record(self, record: dict[str, str | float]) -> None:
        """Gossip a token event as a ``Transaction``, then include it."""
        event = str(record.get("event", "EVENT"))
        self.record_payload(
            json.dumps(record, sort_keys=True),
            tx_id=f"{self.symbol}-{event}-{len(self.blockchain.chain)}",
        )

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


class FiatBackedIssuer:
    """Model a fictional issuer's off-chain USD reserve for teaching purposes.

    The reserve is not a real bank balance and is intentionally kept off-chain.
    """

    def __init__(self, name: str, ledger: TokenLedger) -> None:
        self.name = name
        self.ledger = ledger
        self.reserve_usd: float = 0.0

    def deposit_and_mint(self, to: str, usd_amount: float) -> None:
        """Record fictional USD reserves and mint the matching token amount."""
        TokenLedger._require_positive(usd_amount)
        self.reserve_usd += usd_amount
        self.ledger.mint(to, usd_amount)

    def redeem(self, holder: str, token_amount: float) -> bool:
        """Burn tokens and release the corresponding fictional reserve amount."""
        TokenLedger._require_positive(token_amount)
        if self.reserve_usd < token_amount:
            return False
        if not self.ledger.burn(holder, token_amount):
            return False
        self.reserve_usd -= token_amount
        return True

    def record_reserve_loss(self, usd_amount: float) -> bool:
        """Record an off-chain loss against this fictional issuer's reserves."""
        TokenLedger._require_positive(usd_amount)
        if self.reserve_usd < usd_amount:
            return False
        self.reserve_usd -= usd_amount
        return True

    @property
    def reserve_ratio(self) -> float:
        """Return the fictional reserve amount divided by issued token supply."""
        if self.ledger.total_supply == 0:
            return 1.0
        return self.reserve_usd / self.ledger.total_supply

    @property
    def backing_per_token(self) -> float:
        """Return simplified fictional backing per token, not a market-price oracle."""
        return min(1.0, self.reserve_ratio)
