"""Shared blockchain teaching primitives backing the course notebooks.

Each submodule is the canonical implementation backing one notebook's
narrative; the notebooks explain *why*, this package is just the *what*:

- ``blockchain_lib.pow``    -- notebook 1 (hash chaining + proof of work)
- ``blockchain_lib.pos``    -- notebook 2 Part 1 (proof of stake)
- ``blockchain_lib.merkle`` -- notebook 3 (Merkle trees)
- ``blockchain_lib.mempool`` -- notebook 5 (local mempools + gossip);
  notebooks 6–8 import ``Transaction`` and ``Network`` and call
  ``broadcast`` then ``include``
- ``blockchain_lib.stablecoin`` -- notebooks 7 and 8 (fiat-backed tokens + HTLC escrow)

Notebook 5 defines ``Transaction`` and ``Network`` inline. From notebook 6
onwards the same two imports appear at the top:

    from blockchain_lib.mempool import Network, Transaction
    from blockchain_lib.pos import Block, Blockchain, Validator

"""
