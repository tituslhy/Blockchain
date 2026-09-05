"""Shared blockchain teaching primitives backing the course notebooks.

Each submodule is the canonical implementation backing one notebook's
narrative; the notebooks explain *why*, this package is just the *what*:

- ``blockchain_lib.pow``        -- notebook 1 (hash chaining + proof of work)
- ``blockchain_lib.pos``        -- notebook 2 Part 1 (proof of stake)
- ``blockchain_lib.merkle``     -- notebook 3 (Merkle trees)
- ``blockchain_lib.mempool``    -- notebook 5 (local mempools + gossip)
- ``blockchain_lib.contracts``  -- notebook 6 (smart contracts + oracles)
- ``blockchain_lib.flash_loan`` -- notebook 7 (atomic flash-loan execution)
- ``blockchain_lib.stablecoin`` -- notebooks 8 and 9 (fiat-backed tokens)
- ``blockchain_lib.htlc``       -- notebook 9 (hash-locked cross-chain escrow)

Notebook 5 defines ``Transaction`` and ``Network`` inline. From notebook 6
onwards the same two imports appear at the top:

    from blockchain_lib.mempool import Network, Transaction
    from blockchain_lib.pos import Block, Blockchain, Validator

Notebook 7 then adds:

    from blockchain_lib.contracts import (
        AMMPool, LendingProtocol, Loan, MedianOracle, PriceFeed, PriceReport,
        submit_call,
    )
    from blockchain_lib.flash_loan import FlashLoanProvider, run_flash_attack

Notebooks 8 and 9 continue the same objects:

    from blockchain_lib.stablecoin import Blockchain, FiatBackedIssuer, TokenLedger
    from blockchain_lib.htlc import HTLCManager
"""
