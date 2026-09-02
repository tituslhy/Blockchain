"""Shared mempool primitives backing notebook 5 and reused by notebook 6.

Canonical implementation of the local-inbox model taught in
``5. mempools.ipynb``. Notebook 5 defines the same classes inline so the
lesson can be read without jumping to this file; later notebooks import
from here instead of inventing a second waiting room.

See notebook 5 for the full narrative (gossip, delay-caused forks,
attestations). This module is the code without the lesson. Notebook 6
subclasses ``Network`` so a proposer can include only a transaction it
has actually received.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


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
