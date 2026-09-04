# Blockchain

Learn blockchain concepts by building small, deterministic models: each notebook makes one mechanism visible, then explains both what it does and what it cannot guarantee.

## Layout

- [`notebooks/`](notebooks/) — numbered lessons. New classes are defined **inline** in the notebook that first teaches them, then reused.
- [`blockchain_lib/`](blockchain_lib/) — the canonical copies of those classes. Every class in this package is used in the notebooks; we extract them as we go so later lessons can import the same objects instead of reinventing them.

Notebook 4 (permissioned chains) stays self-contained and does not land a module in `blockchain_lib/`.

## Notebooks

1. [Blockchain basics and mining](<notebooks/1. blockchain_basics_mining.ipynb>) — hash links, tamper evidence, and PoW.
2. [Proof of Stake](<notebooks/2. blockchain_pos.ipynb>) — validators, weighted selection, rewards, and slashing.
3. [Merkle trees](<notebooks/3. merkle_trees.ipynb>) — compact commitments and membership proofs.
4. [Permissioned chains](<notebooks/4. permissioned_chains.ipynb>) — membership, endorsement, ordering, and MVCC.
5. [Mempools](<notebooks/5. mempools.ipynb>) — local network views, gossip, delay-caused forks, and attestations.
6. [Oracles and smart contracts](<notebooks/6. oracles_and_smart_contracts.ipynb>) — public PoS + mempools, then swaps, loans, and the oracles those contracts treat as fact.
7. [Flash loans](<notebooks/7. flash_loans.ipynb>) — same contracts, rented capital, atomic exploits, rollback, and included ≠ succeeded.
8. [Stablecoins](<notebooks/8. stablecoins.ipynb>) — fictional USD reserves, TitusCoin issuance, transfers, redemption, and depeg pressure.
9. [Cross-chain atomic settlement](<notebooks/9. cross_chain_atomic_settlement.ipynb>) — HTLC locks, secret revelation, asymmetric timelocks, and refunds across independent chains.

## Where each library module is first instantiated

| Module | First instantiated in |
| --- | --- |
| [`pow.py`](blockchain_lib/pow.py) | [1. Blockchain basics and mining](<notebooks/1. blockchain_basics_mining.ipynb>) |
| [`pos.py`](blockchain_lib/pos.py) | [2. Proof of Stake](<notebooks/2. blockchain_pos.ipynb>) |
| [`merkle.py`](blockchain_lib/merkle.py) | [3. Merkle trees](<notebooks/3. merkle_trees.ipynb>) |
| [`mempool.py`](blockchain_lib/mempool.py) | [5. Mempools](<notebooks/5. mempools.ipynb>) |
| [`contracts.py`](blockchain_lib/contracts.py) | [6. Oracles and smart contracts](<notebooks/6. oracles_and_smart_contracts.ipynb>) |
| [`flash_loan.py`](blockchain_lib/flash_loan.py) | [7. Flash loans](<notebooks/7. flash_loans.ipynb>) |
| [`stablecoin.py`](blockchain_lib/stablecoin.py) | [8. Stablecoins](<notebooks/8. stablecoins.ipynb>) |
| [`htlc.py`](blockchain_lib/htlc.py) | [9. Cross-chain atomic settlement](<notebooks/9. cross_chain_atomic_settlement.ipynb>) |
