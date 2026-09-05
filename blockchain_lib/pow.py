"""Proof-of-Work primitives: a mined block and the chain it extends.

Canonical implementation backing notebook 1's Concept 2
(`1. blockchain_basics_mining.ipynb`) -- the mining/difficulty version,
not the plain hash-chain in that notebook's Concept 1. See notebook 1
for the full narrative: hash chaining, tamper-evidence, mining vs.
verifying cost, and the attack demos.
"""

from __future__ import annotations

import hashlib
import json
import time


class Block:
    """A proof-of-work block.

    Same linking idea as a plain hash chain (previous_hash), but writing
    a valid hash now requires finding a nonce such that the hash starts
    with ``difficulty`` leading zeros. That search is mining.

    Attributes:
        index: Position in the chain (0 = genesis).
        timestamp: Creation time (informational; included in the hash).
        data: Payload stored in this block.
        previous_hash: Hash of the prior block (links the chain).
        difficulty: Required number of leading zeros in the hash.
        nonce: Counter brute-forced during mining until the hash fits.
        hash: SHA-256 digest meeting the difficulty target.
    """

    def __init__(
        self, index: int, data: str, previous_hash: str, difficulty: int = 5
    ) -> None:
        """Build a block and mine it immediately.

        Args:
            index: Position in the chain (0 = genesis).
            data: Payload stored in this block.
            previous_hash: Hash of the prior block (links the chain).
            difficulty: Required number of leading zeros in the hash.
        """
        self.index = index
        self.timestamp = time.time()
        self.data = data
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = 0
        self.hash = self.mine()

    def compute_hash(self) -> str:
        """SHA-256 of this block's contents (including the current nonce).

        Same inputs always produce the same hash. Changing data,
        previous_hash, or nonce changes the hash -- which is why
        tampering forces re-mining.

        Returns:
            Hex digest of the current block fields.
        """
        block_contents = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_contents.encode()).hexdigest()

    def mine(self) -> str:
        """Brute-force nonce until compute_hash() meets the difficulty target.

        Target example: difficulty=5 means the hash must start with
        "00000". Higher difficulty -> exponentially more attempts on
        average.

        Returns:
            The hash that met the difficulty target.
        """
        target = "0" * self.difficulty
        start = time.time()
        attempts = 0
        candidate_hash = self.compute_hash()

        while not candidate_hash.startswith(target):
            self.nonce += 1
            attempts += 1
            candidate_hash = self.compute_hash()

        elapsed = time.time() - start
        print(
            f"  mined Block #{self.index} in {attempts:,} attempts, {elapsed:.2f}s "
            f"(nonce={self.nonce}, hash={candidate_hash[:16]}...)"
        )
        return candidate_hash

    def __repr__(self) -> str:
        """Return a printable summary of this mined block."""
        return (
            f"Block #{self.index}\n"
            f"  data:          {self.data}\n"
            f"  nonce:         {self.nonce}\n"
            f"  previous_hash: {self.previous_hash[:16]}...\n"
            f"  hash:          {self.hash[:16]}...\n"
        )


class Blockchain:
    """A proof-of-work chain of Block objects.

    Extends plain hash-linking with a third check: every block's hash
    must still meet the difficulty target (leading zeros). That means
    rewriting history requires re-mining every block after the change.
    """

    def __init__(self, difficulty: int = 5) -> None:
        """Start the chain with a mined genesis block.

        Args:
            difficulty: Leading-zero requirement shared by every new block.
        """
        self.difficulty = difficulty
        # Genesis has no real parent; use a fixed dummy previous_hash.
        self.chain: list[Block] = [Block(0, "Genesis Block", "0" * 64, difficulty)]

    def add_block(self, data: str) -> None:
        """Append a new mined block linked to the current tip of the chain.

        Creating Block(...) runs mine() inside __init__, so this call
        blocks until a valid nonce is found for the given difficulty.

        Args:
            data: Payload stored in the new block.
        """
        previous_block = self.chain[-1]
        new_block = Block(len(self.chain), data, previous_block.hash, self.difficulty)
        self.chain.append(new_block)

    def is_valid(self) -> tuple[bool, str]:
        """Validate integrity, linkage, and proof-of-work for every block.

        Rules checked (from index 1 onward):
          1. Stored hash matches recomputed hash (no silent data edits).
          2. previous_hash matches the prior block's hash (chain is linked).
          3. Hash still starts with the required number of zeros (work was done).

        Returns:
            ``(True, message)`` if valid; ``(False, reason)`` on the
            first failure.
        """
        target = "0" * self.difficulty
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.hash != current.compute_hash():
                return False, f"Block #{current.index} was tampered with directly."

            if current.previous_hash != previous.hash:
                return False, (
                    f"Block #{current.index} is disconnected from "
                    f"Block #{previous.index}."
                )

            if not current.hash.startswith(target):
                return False, (
                    f"Block #{current.index} doesn't satisfy the difficulty "
                    "target -- no real work was done."
                )

        return True, "Chain is valid."

    def print_chain(self) -> None:
        """Print every block in order (mirrors notebook 1's demo helper)."""
        for block in self.chain:
            print(block)
