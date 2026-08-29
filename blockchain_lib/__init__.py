"""Shared blockchain teaching primitives backing the course notebooks.

Each submodule is the canonical implementation backing one notebook's
narrative; the notebooks explain *why*, this package is just the *what*:

- ``blockchain_lib.pow``    -- notebook 1 (hash chaining + proof of work)
- ``blockchain_lib.pos``    -- notebook 2 Part 1 (proof of stake)
- ``blockchain_lib.merkle`` -- notebook 3 (Merkle trees)
- ``blockchain_lib.stablecoin`` -- notebooks 7 and 8 (fiat-backed tokens + HTLC escrow)

Notebooks 5 and 6 import from ``blockchain_lib.pos``; notebooks 7 and 8
import from ``blockchain_lib.stablecoin`` instead of redefining the same
classes inline.
"""
