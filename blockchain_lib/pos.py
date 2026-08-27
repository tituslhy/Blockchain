"""Proof-of-Stake primitives: validators, blocks, and the chain they build.

Canonical implementation backing notebook 2 (`2. blockchain_pos.ipynb`,
Part 1) and reused by notebooks 5 and 6. See notebook 2 for the full
narrative walkthrough (validator setup, honest rounds, equivocation,
slashing, historical eligibility) -- this module is the code without
the lesson. Notebook 2's Part 2 (rewards, compounding stake) extends
these ideas inline within that notebook rather than through this module.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time


class Validator:
    """A network participant who locked stake as collateral to propose blocks.

    Stake is both *influence* (higher stake -> higher chance to be picked as
    proposer) and *hostage* (misbehaviour can destroy some or all of it).

    Attributes:
        name: Human-readable identity for demos / logs.
        stake: Locked currency; determines lottery weight.
        slashed_at_height: Height at which this validator was punished, or
            ``None`` if never slashed. Used to judge past eligibility.
    """

    def __init__(self, name: str, stake: float) -> None:
        self.name = name
        self.stake = stake
        self.slashed_at_height: int | None = None

    @property
    def is_slashed(self) -> bool:
        """True if this validator has been slashed at any height."""
        return self.slashed_at_height is not None

    def was_eligible_at(self, height: int) -> bool:
        """Return whether this validator was in good standing at ``height``.

        If never slashed -> always eligible.
        If slashed at height S -> eligible only for heights strictly before S.
        """
        if self.slashed_at_height is None:
            return True
        return height < self.slashed_at_height

    def __repr__(self) -> str:
        status = (
            f"SLASHED at height {self.slashed_at_height}"
            if self.is_slashed
            else "active"
        )
        return f"{self.name}: stake={self.stake:.2f} [{status}]"


class Block:
    """One link in the chain: payload, parent pointer, and who proposed it.

    Attributes:
        index: Position in the chain (0 = genesis).
        timestamp: Creation time (informational; included in the hash).
        data: Payload -- a string here; a tx batch in a real chain.
        previous_hash: Hash of the previous block (makes the chain a chain).
        proposer: Name of the validator who proposed this block.
        hash: SHA-256 digest of this block's contents, computed at creation.
    """

    def __init__(self, index: int, data: str, previous_hash: str, proposer: str) -> None:
        self.index = index
        self.timestamp = time.time()
        self.data = data
        self.previous_hash = previous_hash
        self.proposer = proposer
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Return a deterministic SHA-256 hex digest of this block's fields.

        Same inputs -> same output on every machine. That is what lets any
        node re-verify a block without trusting the proposer.
        """
        block_contents = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "proposer": self.proposer,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_contents.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"Block #{self.index} proposed by {self.proposer}\n"
            f"  data:          {self.data}\n"
            f"  previous_hash: {self.previous_hash[:16]}...\n"
            f"  hash:          {self.hash[:16]}...\n"
        )


def pick_proposer(validators: list[Validator]) -> Validator:
    """Select the next block proposer at random, weighted by stake.

    Uses ``secrets.randbelow`` (OS CSPRNG) rather than the ``random``
    module, so selection is not trivially predictable from PRNG state: a
    predictable PRNG would let an attacker forecast (or grind toward) who
    proposes next.

    Args:
        validators: Full validator set. Slashed validators are skipped.

    Returns:
        The ``Validator`` chosen to propose the next block.
    """
    active = [v for v in validators if not v.is_slashed]
    weights = [v.stake for v in active]
    total = sum(weights)
    pick = secrets.randbelow(int(total))
    cumulative = 0.0
    for validator, weight in zip(active, weights):
        cumulative += weight
        if pick < cumulative:
            return validator
    return active[-1]  # floating-point edge case: land on last active


def slash(
    validator: Validator,
    height: int,
    penalty_fraction: float = 1.0,
) -> None:
    """Destroy a fraction of stake and record when the offence occurred.

    Args:
        validator: The validator being punished.
        height: Block height associated with the misbehaviour. Later
            ``was_eligible_at`` / ``is_valid`` use this to keep honest
            *earlier* blocks valid while rejecting *later* ones.
        penalty_fraction: Fraction of stake burned in ``[0, 1]``. Real
            protocols scale this by severity; ``1.0`` is a full wipe.
    """
    lost = validator.stake * penalty_fraction
    validator.stake -= lost
    validator.slashed_at_height = height
    print(
        f"  SLASHED: {validator.name} loses {lost:.0f} coins for "
        f"misbehaviour at height {height}. Remaining stake: {validator.stake:.0f}"
    )


class Blockchain:
    """Owns the chain and enforces PoS-flavoured legitimacy rules.

    Same architectural role as a PoW blockchain (append + validate), but
    without a difficulty target. Instead we require a known, eligible
    proposer at each height.
    """

    def __init__(self, validators: list[Validator]) -> None:
        self.validators = validators
        # Genesis has no real proposer; "network" is a sentinel label.
        self.chain: list[Block] = [Block(0, "Genesis Block", "0" * 64, "network")]

    def add_block(self, data: str) -> tuple[Block, Validator]:
        """Run the stake lottery, append the winner's block, return both.

        Args:
            data: Payload for the new block.

        Returns:
            ``(new_block, proposer)``.
        """
        proposer = pick_proposer(self.validators)
        previous_block = self.chain[-1]
        new_block = Block(len(self.chain), data, previous_block.hash, proposer.name)
        self.chain.append(new_block)
        return new_block, proposer

    def propose_candidate(
        self,
        data: str,
        proposer_name: str,
        *,
        previous_hash: str | None = None,
        index: int | None = None,
    ) -> Block:
        """Build a block without appending it, so rival proposals can coexist.

        A fork happens when two proposers each build on the same parent
        before either block has propagated to the other. ``add_block``
        cannot model that -- it always extends ``self.chain`` immediately.
        This method returns a linked ``Block`` and leaves the chain
        untouched, so a caller can build several candidates for the same
        height and compare them (e.g. by attestation weight) before
        ``accept_candidate`` commits one.

        Args:
            data: Payload for the candidate block.
            proposer_name: Validator name proposing this candidate.
            previous_hash: Parent hash to build on. Defaults to the
                current tip's hash; pass an explicit value to model a
                proposer that has not yet seen the latest tip.
            index: Height for the candidate. Defaults to the next height
                after the current tip.

        Returns:
            A new ``Block`` that is not yet part of ``self.chain``.
        """
        tip = self.chain[-1]
        return Block(
            index if index is not None else len(self.chain),
            data,
            previous_hash if previous_hash is not None else tip.hash,
            proposer_name,
        )

    def accept_candidate(self, block: Block) -> None:
        """Append a previously built candidate as the new canonical tip.

        Args:
            block: A candidate produced by ``propose_candidate`` (or an
                equivalent block) whose ``previous_hash`` matches the
                chain's current tip.

        Raises:
            ValueError: If ``block.previous_hash`` does not match the
                current tip's hash -- it would not extend this chain.
        """
        tip = self.chain[-1]
        if block.previous_hash != tip.hash:
            raise ValueError(
                "Candidate does not build on the current chain tip; it "
                "belongs to a different fork or is stale."
            )
        self.chain.append(block)

    def is_valid(self) -> tuple[bool, str]:
        """Re-verify the whole chain from scratch.

        For each block after genesis:
          1. Hash integrity (tamper-evidence)
          2. Parent link matches
          3. Proposer existed and ``was_eligible_at(this_height)``

        Returns:
            ``(True, reason)`` if every check passes, else
            ``(False, first failure reason)``.

        Notes:
            Real PoS also demands cryptographic proof the proposer was
            selected for this slot (VRF / equivalent). This toy only
            checks the *name* against the validator set -- flagged, not hidden.
        """
        validators_by_name = {v.name: v for v in self.validators}

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

            proposer = validators_by_name.get(current.proposer)
            if proposer is None:
                return False, (
                    f"Block #{current.index} was proposed by an unknown validator."
                )

            if not proposer.was_eligible_at(current.index):
                return False, (
                    f"Block #{current.index} was proposed by {proposer.name}, who was "
                    f"already slashed (at height {proposer.slashed_at_height}) by the "
                    f"time this block was created."
                )

        return True, "Chain is valid."

    def detect_equivocation(
        self,
        index: int,
        proposer_name: str,
        candidate_blocks: list[Block],
    ) -> tuple[bool, str]:
        """Detect conflicting blocks at the same height from one proposer.

        Equivocation is not a property of a single linear chain; it needs
        two (or more) candidates for the same slot compared side by side.
        Note what equivocation is *not*: two different validators each
        honestly proposing their own block (e.g. an ordinary fork caused
        by network delay) is not equivocation -- only the same identity
        signing multiple conflicting blocks is. This method enforces that
        by requiring every candidate to actually name ``proposer_name``.

        Args:
            index: Height under dispute.
            proposer_name: Validator identity being checked.
            candidate_blocks: All known proposals for that height, which
                must all name ``proposer_name`` as their proposer.

        Returns:
            ``(True, description)`` if more than one distinct hash is present,
            else ``(False, description)``.

        Raises:
            ValueError: If any candidate names a different proposer --
                that is a caller error, not evidence of equivocation:
                conflicting blocks from different proposers are an
                ordinary fork, not one identity double-signing.
        """
        mismatched = {b.proposer for b in candidate_blocks if b.proposer != proposer_name}
        if mismatched:
            raise ValueError(
                "detect_equivocation compares one proposer's own candidates; "
                f"got block(s) proposed by {sorted(mismatched)}, not "
                f"{proposer_name}. Different proposers disagreeing is a "
                "fork, not equivocation."
            )
        hashes = {b.hash for b in candidate_blocks}
        if len(hashes) > 1:
            return True, (
                f"{proposer_name} signed {len(hashes)} conflicting blocks "
                f"at height {index} -- equivocation."
            )
        return False, "No equivocation detected."
