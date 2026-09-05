"""Flash-loan primitives taught in notebook 7.

Notebook 7 imports this module after explaining the heist in prose.
The snapshot/rollback loop lives here so the notebook does not carry a
second copy of the same classes. It depends on the swap and lending
contracts from ``blockchain_lib.contracts``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from blockchain_lib.contracts import AMMPool, LendingProtocol, Loan
from blockchain_lib.mempool import Transaction
from blockchain_lib.pos import Block


class InsufficientRepaymentError(Exception):
    """Raised when a flash-loan action cannot return its borrowed principal."""


@dataclass(frozen=True)
class WorldSnapshot:
    """A pre-action copy of every modeled object a flash loan might mutate.

    Attributes:
        pool_eth: AMM ETH reserve before the action.
        pool_usd: AMM USD reserve before the action.
        loans: Copy of the lending protocol's open loans before the action.
        provider_eth: Flash-loan provider liquidity before the action.
    """

    pool_eth: float
    pool_usd: float
    loans: dict[str, Loan]
    provider_eth: float


@dataclass(frozen=True)
class AttackTrace:
    """A structured record of what a flash-loan attack actually did.

    Attributes:
        borrowed_eth: Principal borrowed for the transaction.
        usd_from_dump: USD received from selling the borrowed ETH.
        manipulated_price: AMM spot price immediately after the dump.
        victim_ratio: Victim's collateral ratio at the manipulated price.
        debt_paid_usd: USD paid to liquidate the victim.
        collateral_seized: ETH collateral seized from the victim.
        eth_bought_back: ETH bought back with the leftover USD.
        eth_before_repayment: Total attacker ETH before repaying principal.
        principal_repaid: ETH principal returned to the flash-loan provider.
    """

    borrowed_eth: float
    usd_from_dump: float
    manipulated_price: float
    victim_ratio: float
    debt_paid_usd: float
    collateral_seized: float
    eth_bought_back: float
    eth_before_repayment: float
    principal_repaid: float


class FlashLoanProvider:
    """Lends ETH that must be repaid before the same call returns.

    Snapshots every modeled object the action touches beforehand and
    restores that snapshot if the action raises or fails to repay --
    modelling atomic all-or-nothing execution without a real EVM.
    """

    def __init__(self, eth_available: float) -> None:
        """Set the provider's lendable liquidity.

        Args:
            eth_available: ETH the provider can lend. Must be positive.

        Raises:
            ValueError: If ``eth_available`` is not positive.
        """
        if eth_available <= 0:
            raise ValueError("Flash-loan liquidity must be positive.")
        self.eth_available = eth_available

    def execute(
        self,
        amount_eth: float,
        action: Callable[[float], tuple[float, AttackTrace]],
        pool: AMMPool,
        protocol: LendingProtocol,
    ) -> tuple[float, AttackTrace]:
        """Lend ``amount_eth``, run ``action``, then commit or roll back.

        Args:
            amount_eth: ETH to lend. Must be positive and available.
            action: Callable taking the borrowed ETH amount and returning
                ``(eth_before_repayment, trace)``.
            pool: The AMM the action may mutate (snapshotted first).
            protocol: The lending protocol the action may mutate
                (snapshotted first).

        Returns:
            ``(profit_eth, trace)`` where ``profit_eth`` is whatever ETH
            remains after repaying the principal.

        Raises:
            ValueError: If ``amount_eth`` is not positive or exceeds
                available liquidity.
            InsufficientRepaymentError: If ``action`` cannot return at
                least ``amount_eth``. In this case (or any other
                exception from ``action``), ``pool``, ``protocol``, and
                this provider's balance are restored from the snapshot.
        """
        if amount_eth <= 0 or amount_eth > self.eth_available:
            raise ValueError("Flash-loan amount is unavailable.")
        snapshot = WorldSnapshot(
            pool.eth_reserve,
            pool.usd_reserve,
            dict(protocol.loans),
            self.eth_available,
        )
        self.eth_available -= amount_eth
        try:
            eth_before_repayment, trace = action(amount_eth)
            if eth_before_repayment < amount_eth:
                raise InsufficientRepaymentError(
                    f"Only {eth_before_repayment:.4f} ETH available to repay "
                    f"{amount_eth:.4f} ETH."
                )
            self.eth_available += amount_eth
            return eth_before_repayment - amount_eth, trace
        except Exception:
            pool.eth_reserve = snapshot.pool_eth
            pool.usd_reserve = snapshot.pool_usd
            protocol.loans = dict(snapshot.loans)
            self.eth_available = snapshot.provider_eth
            raise


def run_flash_attack(
    amount_eth: float, pool: AMMPool, protocol: LendingProtocol, victim: str
) -> tuple[float, AttackTrace]:
    """Borrow, dump, liquidate, buy back, and report the resulting trace.

    Args:
        amount_eth: ETH to borrow and dump into ``pool``.
        pool: The AMM to manipulate.
        protocol: The lending protocol whose price source will be read.
        victim: Borrower name to liquidate once the price is manipulated.

    Returns:
        ``(eth_before_repayment, trace)`` -- total attacker ETH before
        repaying the flash-loan principal, and a structured trace of the
        attack's steps.

    Raises:
        PositionNotLiquidatableError: If the victim is not actually
            liquidatable at the manipulated price (propagates from
            ``protocol.liquidate``).
        InsufficientRepaymentError: If the liquidation proceeds leave no
            USD for the buyback swap.
    """
    print(f"STEP 1 — BORROW: {amount_eth:.2f} ETH arrives temporarily.")
    usd_from_dump = pool.swap_eth_for_usd(amount_eth)
    manipulated_price = pool.spot_price
    print(
        f"STEP 2 — DUMP: sell {amount_eth:.2f} ETH for ${usd_from_dump:,.2f}; "
        f"AMM price becomes ${manipulated_price:,.2f}/ETH."
    )
    victim_loan = protocol.loans[victim]
    victim_ratio = protocol.collateral_ratio(victim_loan)
    seized_loan = protocol.liquidate(victim)
    debt_paid_usd = seized_loan.debt_usd
    collateral_seized = seized_loan.collateral_eth
    print(
        f"STEP 3 — LIQUIDATE: victim ratio is {victim_ratio:.2f}; "
        f"pay ${debt_paid_usd:,.2f} debt and seize {collateral_seized:.2f} ETH."
    )
    usd_for_buyback = usd_from_dump - debt_paid_usd
    if usd_for_buyback <= 0:
        raise InsufficientRepaymentError("Liquidation leaves no USD for the buyback.")
    eth_bought_back = pool.swap_usd_for_eth(usd_for_buyback)
    eth_before_repayment = eth_bought_back + collateral_seized
    print(
        f"STEP 4 — BUY BACK: remaining ${usd_for_buyback:,.2f} buys back "
        f"{eth_bought_back:.2f} ETH; attacker holds {eth_before_repayment:.2f} ETH."
    )
    print(f"STEP 5 — REPAY: return {amount_eth:.2f} ETH principal to the provider.")
    trace = AttackTrace(
        borrowed_eth=amount_eth,
        usd_from_dump=usd_from_dump,
        manipulated_price=manipulated_price,
        victim_ratio=victim_ratio,
        debt_paid_usd=debt_paid_usd,
        collateral_seized=collateral_seized,
        eth_bought_back=eth_bought_back,
        eth_before_repayment=eth_before_repayment,
        principal_repaid=amount_eth,
    )
    return eth_before_repayment, trace


@dataclass(frozen=True)
class TransactionReceipt:
    """Inclusion records the attempt; status says whether state changes survived.

    Attributes:
        transaction: The gossiped payload that was included.
        block: Block that recorded the attempt.
        status: ``SUCCESS`` or ``REVERTED``.
        gas_used: Teaching stand-in for gas, not a real EVM meter.
        state_effect: Human-readable note about whether world state changed.
    """

    transaction: Transaction
    block: Block
    status: str
    gas_used: int
    state_effect: str
