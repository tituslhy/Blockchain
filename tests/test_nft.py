"""Check the NFT lesson's ownership rules and royalty arithmetic."""

import hashlib
import unittest
from decimal import Decimal

from blockchain_lib.nft import (
    NFTCollection,
    NotTheOwnerError,
    TokenDoesNotExistError,
    TokenMetadata,
)


class NFTCollectionTests(unittest.TestCase):
    """Exercise real collection state, including failed operations."""

    def setUp(self) -> None:
        """Create an artist's collection and a small off-chain artifact."""
        self.art = b"Class graduation photo; someone always blinks."
        self.metadata = TokenMetadata(
            "Class Graduation Photo",
            "The whole class together.",
            hashlib.sha256(self.art).hexdigest(),
            "https://example.invalid/meme",
        )
        self.collection = NFTCollection("class-photos.nft", "Alice", royalty_bps=500)
        self.token = self.collection.mint("Alice", self.metadata, caller="Alice")

    def test_copying_file_does_not_change_owner(self) -> None:
        """Possession of matching bytes is independent of token ownership."""
        copied_file = bytes(bytearray(self.art))
        self.assertTrue(self.collection.verify_content(self.token, copied_file))
        self.assertEqual(self.collection.owner_of(self.token), "Alice")
        self.assertFalse(self.collection.verify_content(self.token, b"edited meme"))

    def test_non_owner_cannot_transfer_or_sell(self) -> None:
        """Rejected calls leave ownership and metadata untouched."""
        with self.assertRaises(NotTheOwnerError):
            self.collection.transfer(self.token, "Jacob", "Jacob")
        with self.assertRaises(NotTheOwnerError):
            self.collection.sell(self.token, "Jacob", "Bob", Decimal("2"))
        self.assertEqual(self.collection.owner_of(self.token), "Alice")
        self.assertEqual(self.collection.metadata_of(self.token), self.metadata)

    def test_mint_is_creator_only(self) -> None:
        """A failed mint neither adds a token nor consumes its next ID."""
        with self.assertRaises(PermissionError):
            self.collection.mint("Jacob", self.metadata, caller="Jacob")
        second = self.collection.mint("Alice", self.metadata, caller="Alice")
        self.assertEqual(second, 2)

    def test_sale_quotes_exact_royalty_and_moves_only_one_token(self) -> None:
        """A resale keeps its creator and preserves the other token's owner."""
        second = self.collection.mint("Alice", self.metadata, caller="Alice")
        first_sale = self.collection.sell(self.token, "Alice", "Bob", Decimal("2"))
        resale = self.collection.sell(self.token, "Bob", "Wei Yan", Decimal("50"))
        self.assertEqual(first_sale["creator_royalty"], Decimal("0.1"))
        self.assertEqual(resale["creator_royalty"], Decimal("2.5"))
        self.assertEqual(resale["seller_receives"], Decimal("47.5"))
        self.assertEqual(resale["creator"], "Alice")
        self.assertEqual(self.collection.owner_of(self.token), "Wei Yan")
        self.assertEqual(self.collection.owner_of(second), "Alice")

    def test_direct_transfer_does_not_require_a_sale_price(self) -> None:
        """The basic transfer route can bypass royalty quotation."""
        self.collection.transfer(self.token, "Alice", "Bob")
        self.assertEqual(self.collection.owner_of(self.token), "Bob")
        self.assertEqual(
            self.collection.royalty_info(self.token, Decimal("50")),
            ("Alice", Decimal("2.5")),
        )

    def test_invalid_sale_price_cannot_move_token(self) -> None:
        """Validate prices before transfer, including non-finite values."""
        for price in ["-1", "0", "NaN", "Infinity"]:
            with self.subTest(price=price), self.assertRaises(ValueError):
                self.collection.sell(self.token, "Alice", "Bob", Decimal(price))
        self.assertEqual(self.collection.owner_of(self.token), "Alice")

    def test_missing_token_queries_fail(self) -> None:
        """A nonexistent token cannot acquire metadata, an owner, or royalties."""
        for query in [
            lambda: self.collection.owner_of(999),
            lambda: self.collection.metadata_of(999),
            lambda: self.collection.verify_content(999, self.art),
            lambda: self.collection.royalty_info(999, Decimal("2")),
        ]:
            with self.assertRaises(TokenDoesNotExistError):
                query()

    def test_empty_recipient_cannot_move_token(self) -> None:
        """Do not silently replace an owner with a missing identity."""
        with self.assertRaises(ValueError):
            self.collection.transfer(self.token, "Alice", "")
        self.assertEqual(self.collection.owner_of(self.token), "Alice")

    def test_same_file_can_back_distinct_tokens_in_distinct_collections(self) -> None:
        """Token identity includes its collection; a hash is not a minting ban."""
        second = self.collection.mint("Bob", self.metadata, caller="Alice")
        imitation = NFTCollection("imitation.nft", "Jacob")
        fake_id = imitation.mint("Jacob", self.metadata, caller="Jacob")
        self.assertNotEqual(self.token, second)
        self.assertEqual(fake_id, self.token)
        self.assertEqual(self.collection.owner_of(self.token), "Alice")
        self.assertEqual(imitation.owner_of(fake_id), "Jacob")

    def test_royalty_rate_bounds(self) -> None:
        """A rate cannot allocate more than the entire quoted sale price."""
        for rate in [-1, 10001]:
            with self.assertRaises(ValueError):
                NFTCollection("bad.nft", "Alice", royalty_bps=rate)


if __name__ == "__main__":
    unittest.main()
