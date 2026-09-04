"""Shared mempool primitives taught in notebook 5 and imported after that.

Notebook 5 defines ``Transaction`` and ``Network`` inline so the lesson
can be read in one place. Later notebooks import this copy and use the
same two calls: ``broadcast`` then ``include``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from blockchain_lib.pos import Block, Blockchain


@dataclass(frozen=True)
class Transaction:
    """One gossiped payment-like fact, identified by its tx_id.

    Attributes:
        tx_id: Unique identifier a node uses to track this transaction
            across its own mempool and others' gossip.
        description: Human-readable summary, for demo printing only.
    """

    tx_id: str
    description: str


class Network:
    """A set of nodes, each holding its own local mempool.

    There is no shared, global mempool here on purpose: ``broadcast``
    delivers a transaction to each peer independently and probabilistically,
    modelling how gossip reaches honest nodes at different times.
    """

    def __init__(self, node_names: list[str], rng: random.Random) -> None:
        """Create one empty mempool per node.

        Args:
            node_names: Every node's identity; must be non-empty.
            rng: A seeded ``random.Random`` so a demo run is repeatable.
                This is a classroom convenience, not protocol-grade
                randomness. Real gossip timing is not something a single
                seed could faithfully reproduce, and nothing here needs
                to resist being predicted.

        Raises:
            ValueError: If ``node_names`` is empty.
        """
        if not node_names:
            raise ValueError("A network needs at least one node.")
        self.node_names = list(node_names)
        self.rng = rng
        self.mempools: dict[str, dict[str, Transaction]] = {
            name: {} for name in node_names
        }

    def broadcast(self, transaction: Transaction, origin: str) -> None:
        """Deliver a transaction to its origin, then probabilistically to peers.

        Args:
            transaction: The transaction being gossiped.
            origin: The node that first received/sent it; always gets it.

        Raises:
            ValueError: If ``origin`` is not a known node.
        """
        if origin not in self.mempools:
            raise ValueError(f"Unknown origin node: {origin}")
        self.mempools[origin][transaction.tx_id] = transaction
        for name in self.node_names:
            if name != origin and self.rng.random() < 0.5:
                self.mempools[name][transaction.tx_id] = transaction

    def mempool_ids(self, node_name: str) -> list[str]:
        """Return a node's currently known transaction IDs, sorted.

        Args:
            node_name: The node whose local view to read.

        Returns:
            Sorted list of transaction IDs that node has received so far.

        Raises:
            ValueError: If ``node_name`` is not a known node.
        """
        if node_name not in self.mempools:
            raise ValueError(f"Unknown node: {node_name}")
        return sorted(self.mempools[node_name])

    def get(self, node_name: str, tx_id: str) -> Transaction | None:
        """Return one node's copy of ``tx_id``, or ``None`` if it has not heard it.

        Args:
            node_name: The node whose local mempool to read.
            tx_id: Transaction identifier to look up.

        Raises:
            ValueError: If ``node_name`` is not a known node.
        """
        if node_name not in self.mempools:
            raise ValueError(f"Unknown node: {node_name}")
        return self.mempools[node_name].get(tx_id)

    def drop(self, tx_id: str) -> None:
        """Remove ``tx_id`` from every local mempool after inclusion.

        Nodes that never received the transaction are left unchanged.
        """
        for mempool in self.mempools.values():
            mempool.pop(tx_id, None)

    def include(
        self, proposer: str, tx_id: str, chain: Blockchain
    ) -> tuple[Transaction, Block]:
        """Include ``tx_id`` from ``proposer``'s mempool and append a block.

        A proposer may include only a transaction sitting in *their*
        mempool. After inclusion the transaction is dropped from every
        local inbox: it is no longer waiting; it is history (or a
        receipt of an attempt).

        Args:
            proposer: Node that believes it can propose this transaction.
            tx_id: Identifier of the transaction to include.
            chain: The PoS chain that will record the inclusion.

        Returns:
            The included ``Transaction`` and the new ``Block``.

        Raises:
            ValueError: If ``proposer`` is unknown, or ``tx_id`` is not
                in that proposer's local mempool, or the candidate does
                not build on the current tip.
        """
        transaction = self.get(proposer, tx_id)
        if transaction is None:
            raise ValueError(
                f"{proposer} cannot include {tx_id}: "
                "it is not in their local mempool."
            )
        block = chain.propose_candidate(transaction.description, proposer)
        chain.accept_candidate(block)
        self.drop(tx_id)
        return transaction, block
