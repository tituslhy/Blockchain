"""Merkle tree primitives: batch commitment and membership proofs.

Canonical implementation backing notebook 3 (`3. merkle_trees.ipynb`).
See that notebook for the full narrative and the diploma-batch demo
(``Certificate`` / ``issue_batch`` / ``verify_certificate`` stay inline
there -- they're demo scaffolding specific to that story, not a general
abstraction other notebooks need).
"""

from __future__ import annotations

import hashlib


def sha256(data: str) -> str:
    """Deterministic hash helper used throughout."""
    return hashlib.sha256(data.encode()).hexdigest()


class MerkleTree:
    """A binary tree of hashes, built bottom-up from a list of documents.

    Each document becomes a "leaf" (individually hashed). Leaves are
    paired up and hashed together to form the next layer up. This
    repeats until exactly one hash remains -- the "Merkle root" -- which
    is the ONLY thing that needs to be published on-chain.

    Caveats / assumptions:
      - Relies on SHA-256 being collision-resistant: this whole scheme
        breaks if two different documents can be found that hash the
        same.
      - Leaf order matters and must be agreed/fixed ahead of time --
        the tree commits to a specific ORDERED batch, not just a set.
      - Odd-sized layers duplicate the last hash so it can pair with
        itself (see `_build`). This is the simplest fix for "odd number
        of nodes", but it's not free: naive duplicate-padding is what
        let an attacker on early Bitcoin construct a modified
        transaction list with the SAME Merkle root as the original, by
        duplicating the last transaction (CVE-2012-2459). Production
        systems (e.g. Certificate Transparency, RFC 6962) instead use
        domain-separated hashing -- leaves and internal nodes are
        hashed with different prefixes -- to remove this ambiguity.
        This module keeps the simple version for teaching purposes.
      - A Merkle tree proves a document was included in the batch that
        produced a given root -- it says nothing about whether the
        document's CONTENTS were true or correct at issuance. Garbage
        in, verifiably-tamper-evident garbage out.

    Attributes:
        leaves: Hashes of the original documents, in order.
        layers: Every layer of the tree, from leaves (layers[0]) up to
            the root (layers[-1], containing exactly one hash).
    """

    def __init__(self, documents: list[str]) -> None:
        if not documents:
            raise ValueError("Need at least one document to build a tree.")
        self.leaves: list[str] = [sha256(doc) for doc in documents]
        self.layers: list[list[str]] = [self.leaves]
        self._build()

    def _build(self) -> None:
        """Repeatedly hash pairs of the current layer until one hash remains."""
        current = self.layers[0]
        while len(current) > 1:
            next_layer: list[str] = []
            for i in range(0, len(current), 2):
                left = current[i]
                # odd count -> duplicate the last item so it can pair with itself
                right = current[i + 1] if i + 1 < len(current) else current[i]
                next_layer.append(sha256(left + right))
            self.layers.append(next_layer)
            current = next_layer

    @property
    def root(self) -> str:
        """The single hash summarizing the ENTIRE batch of documents."""
        return self.layers[-1][0]

    def get_proof(self, leaf_index: int) -> list[tuple[str, str]]:
        """Build the minimal sibling-hash path proving a document's membership.

        This is the entire point of the structure: instead of needing
        ALL other documents, you need exactly one sibling hash per
        LEVEL of the tree -- log2(N) hashes total, not N-1.

        Args:
            leaf_index: Position of the document to prove membership for.

        Returns:
            A list of (position, hash) pairs. Position ("left"/"right")
            tells the verifier which side of the combination the
            sibling hash belongs on.
        """
        proof: list[tuple[str, str]] = []
        index = leaf_index
        for layer in self.layers[:-1]:  # every layer except the root itself
            is_right_node = index % 2 == 1
            pair_index = index - 1 if is_right_node else index + 1
            if pair_index < len(layer):
                sibling_hash = layer[pair_index]
            else:
                # `index` is the odd node out at the end of this layer --
                # `_build` paired it with itself, so the "sibling" IS
                # this node's own hash. It must still be included, or
                # the verifier's recomputed hash won't match the real
                # root for this leaf.
                sibling_hash = layer[index]
            position = "left" if is_right_node else "right"
            proof.append((position, sibling_hash))
            index //= 2
        return proof


def verify_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Independently recompute the root from a leaf hash + its proof, and
    check it matches the published root -- without ever seeing any other
    document in the batch.

    Args:
        leaf_hash: Hash of the document being proven.
        proof: Sibling hashes returned by MerkleTree.get_proof().
        root: The published root hash to check against.

    Returns:
        True if the leaf genuinely belongs to the tree that produced root.
    """
    current_hash = leaf_hash
    for position, sibling_hash in proof:
        if position == "left":
            current_hash = sha256(sibling_hash + current_hash)
        else:
            current_hash = sha256(current_hash + sibling_hash)
    return current_hash == root
