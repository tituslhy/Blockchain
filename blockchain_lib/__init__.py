"""Shared blockchain teaching primitives backing the course notebooks.

Each submodule is the canonical implementation backing one notebook's
narrative; the notebooks explain *why*, this package is just the *what*:

- ``blockchain_lib.pow``    -- notebook 1 (hash chaining + proof of work)
- ``blockchain_lib.pos``    -- notebook 2 Part 1 (proof of stake)
- ``blockchain_lib.merkle`` -- notebook 3 (Merkle trees)
- ``blockchain_lib.mempool`` -- notebook 5 (local mempools + gossip);
  notebook 6 imports these and subclasses ``Network``
- ``blockchain_lib.stablecoin`` -- notebooks 7 and 8 (fiat-backed tokens + HTLC escrow)

Notebook 5 defines ``Transaction`` and ``Network`` inline (and they live
here for later reuse). Notebook 6 imports them from this package and
imports ``Blockchain`` from ``blockchain_lib.pos``. Notebooks 7 and 8
import from ``blockchain_lib.stablecoin`` instead of redefining the same
classes inline.
"""
