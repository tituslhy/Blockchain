"""Shared stablecoin teaching primitives for notebooks 7 and 8."""

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
