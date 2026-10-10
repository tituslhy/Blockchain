"""NFT teaching primitives introduced inline in notebook 10.

This models ERC-721's individual ownership and ERC-2981-style royalty
quotations. It is not a complete implementation of either standard and
does not transfer ETH. See notebook 10 for the worked examples.
"""

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from blockchain_lib.contracts import SmartContract


@dataclass(frozen=True)
class TokenMetadata:
    """Describe the off-chain artifact without storing its file bytes.

    Attributes:
        name: Human-readable title.
        description: What the creator says the artifact depicts.
        content_hash: SHA-256 digest of the artifact bytes in this model.
        uri: Location used to retrieve the artifact in this model.
    """

    name: str
    description: str
    content_hash: str
    uri: str


class NotTheOwnerError(PermissionError):
    """Raised when someone tries to move another holder's token."""


class TokenDoesNotExistError(LookupError):
    """Raised when a token ID has not been minted in this collection."""


class NFTCollection(SmartContract):
    """Track each token separately, with a creator and royalty quotation.

    Caller names stand in for authenticated wallet addresses. Ownership
    lives in Python memory; blocks record calls, as in notebook 6.
    """

    def __init__(self, address: str, creator: str, royalty_bps: int = 500) -> None:
        """Set the creator and rate; 500 basis points means five percent."""
        super().__init__(address)
        if not creator:
            raise ValueError("A collection needs a creator.")
        if not 0 <= royalty_bps <= 10_000:
            raise ValueError("Royalty basis points must be between 0 and 10,000.")
        self.creator = creator
        self.royalty_bps = royalty_bps
        self._next_id = 1
        self._owners: dict[int, str] = {}
        self._metadata: dict[int, TokenMetadata] = {}

    def mint(self, to: str, metadata: TokenMetadata, caller: str) -> int:
        """Create a token; this collection lets only its creator mint."""
        if caller != self.creator:
            raise PermissionError(f"Only {self.creator} can mint in this collection.")
        if not to:
            raise ValueError("A token needs a recipient.")
        token_id = self._next_id
        self._next_id += 1
        self._owners[token_id] = to
        self._metadata[token_id] = metadata
        return token_id

    def owner_of(self, token_id: int) -> str:
        """Return this token's owner, or reject an unminted ID."""
        if token_id not in self._owners:
            raise TokenDoesNotExistError(f"Token #{token_id} does not exist.")
        return self._owners[token_id]

    def metadata_of(self, token_id: int) -> TokenMetadata:
        """Read the pointer and hash attached to an existing token."""
        self.owner_of(token_id)
        return self._metadata[token_id]

    def transfer(self, token_id: int, caller: str, to: str) -> None:
        """Move a token only when its current owner is the caller."""
        current = self.owner_of(token_id)
        if caller != current:
            raise NotTheOwnerError(
                f"{caller} does not own token #{token_id}; {current} does."
            )
        if not to:
            raise ValueError("A transfer needs a recipient.")
        self._owners[token_id] = to

    def royalty_info(
        self, token_id: int, sale_price_eth: Decimal
    ) -> tuple[str, Decimal]:
        """Quote a royalty recipient and amount; no money moves here."""
        self.owner_of(token_id)
        if not sale_price_eth.is_finite() or sale_price_eth < 0:
            raise ValueError("Sale price must be finite and non-negative.")
        amount = sale_price_eth * Decimal(self.royalty_bps) / Decimal(10_000)
        return self.creator, amount

    def sell(
        self, token_id: int, caller: str, to: str, price_eth: Decimal
    ) -> dict[str, str | int | Decimal]:
        """Transfer a token and return its proposed payout split.

        This classroom helper computes allocations, not ETH settlement.
        It is separate from the basic transfer route, which has no price.
        """
        creator, royalty = self.royalty_info(token_id, price_eth)
        if price_eth == 0:
            raise ValueError("Use transfer for a gift; sale price must be positive.")
        # Validate the price before any ownership changes.
        self.transfer(token_id, caller, to)
        return {
            "token_id": token_id,
            "seller": caller,
            "buyer": to,
            "price_eth": price_eth,
            "seller_receives": price_eth - royalty,
            "creator": creator,
            "creator_royalty": royalty,
        }

    def verify_content(self, token_id: int, file_bytes: bytes) -> bool:
        """Check byte integrity, without deciding authorship or availability."""
        metadata = self.metadata_of(token_id)
        return hashlib.sha256(file_bytes).hexdigest() == metadata.content_hash
