"""Smart-contract and oracle primitives taught in notebook 6.

Notebook 6 defines these classes inline so the lesson can be read in one
place. Later notebooks import this copy: a swap pool, a lending protocol,
and the price sources a lending rule might trust.

An oracle is not a contract. It is an input a contract treats as fact.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Protocol

from blockchain_lib.mempool import Network, Transaction
from blockchain_lib.pos import Block, Blockchain


class SmartContract:
    """Code that lives at an address and runs when something calls it.

    The chain does not understand loans or swaps. It understands: this
    address, this method, these arguments. The methods below are the rules.
    """

    def __init__(self, address: str) -> None:
        """Store the address this contract will be called at.

        Args:
            address: Non-empty on-chain name, e.g. ``amm.eth``.

        Raises:
            ValueError: If ``address`` is empty.
        """
        if not address:
            raise ValueError("Contract address must be non-empty.")
        self.address = address

    def call(self, method: str, **kwargs):
        """Invoke a public method by name.

        Args:
            method: Public method name. Names starting with ``_`` are
                not part of the callable surface.
            **kwargs: Arguments forwarded to that method.

        Returns:
            Whatever the underlying method returns.

        Raises:
            AttributeError: If ``method`` is private or missing.
        """
        if method.startswith("_") or method == "call":
            raise AttributeError(f"{self.address} has no public method {method!r}.")
        func = getattr(self, method, None)
        if not callable(func):
            raise AttributeError(  # noqa: TRY004
                f"{self.address} has no public method {method!r}."
            )
        return func(**kwargs)


@dataclass(frozen=True)
class PriceReport:
    """One reported ETH/USD price from a named source.

    Attributes:
        source: Who reported this price. Nothing here authenticates them.
        eth_price_usd: The reported price.
    """

    source: str
    eth_price_usd: float


def collateral_ratio(
    collateral_eth: float, debt_usd: float, eth_price_usd: float
) -> float:
    """Return collateral value divided by debt, at a given ETH price.

    Args:
        collateral_eth: ETH locked as collateral. Must be positive.
        debt_usd: Outstanding debt in USD. Must be positive.
        eth_price_usd: ETH/USD price the caller is treating as fact.

    Returns:
        Collateral value divided by debt.

    Raises:
        ValueError: If any input is not positive.
    """
    if collateral_eth <= 0 or debt_usd <= 0 or eth_price_usd <= 0:
        raise ValueError("Collateral, debt, and price must be positive.")
    return collateral_eth * eth_price_usd / debt_usd


def should_liquidate(ratio: float, threshold: float = 1.5) -> bool:
    """Return whether a collateral ratio is below the liquidation threshold.

    Args:
        ratio: Collateral value divided by debt.
        threshold: Minimum healthy ratio. Defaults to 1.5.

    Returns:
        True if ``ratio`` is strictly below ``threshold``.
    """
    return ratio < threshold


class PriceSource(Protocol):
    """Anything a lending rule can ask for a price.

    ``MedianOracle`` and ``PriceFeed`` both satisfy this. So does any
    object with a ``price`` property — including a thin AMM used as a
    bad oracle.
    """

    @property
    def price(self) -> float:
        """Return the price this source currently treats as fact."""
        ...


def submit_call(
    network: Network,
    chain: Blockchain,
    origin: str,
    tx_id: str,
    contract: SmartContract,
    method: str,
    **kwargs: Any,
) -> tuple[Any, Transaction, Block]:
    """Gossip a contract call, include it as a ``Block``, then run it.

    Inclusion is the notary stamp. ``call`` is the form being filled in.
    A proposer who never heard the gossip cannot stamp it — notebook 5
    still applies.

    Args:
        network: Gossip network whose local mempools will see the call.
        chain: Chain that will record the inclusion.
        origin: Node that first broadcasts the transaction.
        tx_id: Unique identifier for this call.
        contract: Contract to invoke after inclusion.
        method: Public method name on ``contract``.
        **kwargs: Arguments forwarded to that method.

    Returns:
        ``(result, transaction, block)`` — whatever the method returned,
        the gossiped transaction, and the block that included it.
    """
    arg_preview = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    description = f"{contract.address}.{method}({arg_preview})"
    network.broadcast(Transaction(tx_id, description), origin=origin)
    tx, block = network.include(origin, tx_id, chain)
    result = contract.call(method, **kwargs)
    return result, tx, block


class MedianOracle:
    """A price source that reports the median of several independent reports."""

    def __init__(self, reports: list[PriceReport]) -> None:
        """Store the reports this oracle will median.

        Args:
            reports: Non-empty list of named price reports.

        Raises:
            ValueError: If ``reports`` is empty.
        """
        if not reports:
            raise ValueError("At least one price report is required.")
        self.reports = reports

    @property
    def price(self) -> float:
        """Return the median reported price.

        Returns:
            Median of ``eth_price_usd`` across ``self.reports``.
        """
        return statistics.median(report.eth_price_usd for report in self.reports)


class PriceFeed(SmartContract):
    """A contract that stores price reports as they arrive.

    Each ``report`` call is meant to be stamped into its own Block.
    ``latest`` is whatever the last stamp said. A ``MedianOracle`` over
    ``reports`` is a different choice.
    """

    def __init__(self, address: str) -> None:
        """Create an empty feed at ``address``.

        Args:
            address: On-chain address of this feed.
        """
        super().__init__(address)
        self.reports: list[PriceReport] = []

    def report(self, source: str, eth_price_usd: float) -> PriceReport:
        """Append one report and return it.

        Args:
            source: Label for who sent this number. Not a signature.
            eth_price_usd: Reported ETH/USD price. Must be positive.

        Returns:
            The stored ``PriceReport``.

        Raises:
            ValueError: If ``eth_price_usd`` is not positive.
        """
        if eth_price_usd <= 0:
            raise ValueError("Reported price must be positive.")
        posted = PriceReport(source, eth_price_usd)
        self.reports.append(posted)
        return posted

    @property
    def latest(self) -> PriceReport:
        """Return the most recently stamped report.

        Returns:
            The last item in ``self.reports``.

        Raises:
            IndexError: If no report has been posted yet.
        """
        return self.reports[-1]

    @property
    def price(self) -> float:
        """Return the median of every report stored so far.

        Returns:
            Median ETH/USD price across ``self.reports``.
        """
        return statistics.median(report.eth_price_usd for report in self.reports)


class AMMPool(SmartContract):
    """A constant-product (x*y=k) two-asset market maker.

    This is a smart contract: it has an address, and swaps are method
    calls. The displayed spot price is ``USD reserve / ETH reserve``.
    That number is not a journalist. It is the current ratio of two
    piles of tokens.
    """

    def __init__(self, address: str, eth_reserve: float, usd_reserve: float) -> None:
        """Create a pool at ``address`` with the given reserves.

        Args:
            address: On-chain address of this pool.
            eth_reserve: ETH held by the pool. Must be positive.
            usd_reserve: USD held by the pool. Must be positive.

        Raises:
            ValueError: If either reserve is not positive.
        """
        super().__init__(address)
        if eth_reserve <= 0 or usd_reserve <= 0:
            raise ValueError("AMM reserves must be positive.")
        self.eth_reserve = eth_reserve
        self.usd_reserve = usd_reserve

    @property
    def spot_price(self) -> float:
        """Current displayed price: USD reserve per unit of ETH reserve."""
        return self.usd_reserve / self.eth_reserve

    @property
    def constant_product(self) -> float:
        """The invariant ``x * y`` a swap should preserve (no fees here)."""
        return self.eth_reserve * self.usd_reserve

    def swap_eth_for_usd(self, eth_in: float) -> float:
        """Sell ETH into the pool, moving both reserves and the spot price.

        Args:
            eth_in: ETH sold into the pool. Must be positive.

        Returns:
            USD received in exchange.

        Raises:
            ValueError: If ``eth_in`` is not positive.
        """
        if eth_in <= 0:
            raise ValueError("Swap input must be positive.")
        k = self.constant_product
        new_eth_reserve = self.eth_reserve + eth_in
        new_usd_reserve = k / new_eth_reserve
        usd_out = self.usd_reserve - new_usd_reserve
        self.eth_reserve, self.usd_reserve = new_eth_reserve, new_usd_reserve
        return usd_out

    def swap_usd_for_eth(self, usd_in: float) -> float:
        """Sell USD into the pool, moving both reserves and the spot price.

        Args:
            usd_in: USD sold into the pool. Must be positive.

        Returns:
            ETH received in exchange.

        Raises:
            ValueError: If ``usd_in`` is not positive.
        """
        if usd_in <= 0:
            raise ValueError("Swap input must be positive.")
        k = self.constant_product
        new_usd_reserve = self.usd_reserve + usd_in
        new_eth_reserve = k / new_usd_reserve
        eth_out = self.eth_reserve - new_eth_reserve
        self.usd_reserve, self.eth_reserve = new_usd_reserve, new_eth_reserve
        return eth_out


@dataclass(frozen=True)
class Loan:
    """A borrower's position: collateral posted against debt owed.

    Attributes:
        collateral_eth: ETH locked as collateral. Must be positive.
        debt_usd: Outstanding debt in USD. Must be positive.
    """

    collateral_eth: float
    debt_usd: float

    def __post_init__(self) -> None:
        """Reject non-positive collateral or debt.

        Raises:
            ValueError: If either field is not positive.
        """
        if self.collateral_eth <= 0 or self.debt_usd <= 0:
            raise ValueError("Loan collateral and debt must be positive.")


class LoanNotFoundError(Exception):
    """Raised when a borrower has no open loan."""


class PositionNotLiquidatableError(Exception):
    """Raised when liquidation is attempted on a still-healthy position."""


class LendingProtocol(SmartContract):
    """A toy lending protocol that liquidates undercollateralised loans.

    Its one deliberate flaw: by default it prices collateral from
    ``pool.spot_price`` -- a single, on-chain, manipulable number -- unless
    a ``price_source`` (e.g. a ``MedianOracle``) is supplied instead.
    """

    def __init__(
        self,
        address: str,
        pool: AMMPool,
        liquidation_ratio: float = 1.5,
        price_source: PriceSource | None = None,
    ) -> None:
        """Configure the protocol's price source and liquidation threshold.

        Args:
            address: On-chain address of this contract.
            pool: The AMM this protocol reads a price from by default.
            liquidation_ratio: Minimum healthy collateral ratio. Must be
                positive.
            price_source: Optional object exposing a ``.price`` property.
                When given, it is trusted instead of ``pool.spot_price``.

        Raises:
            ValueError: If ``liquidation_ratio`` is not positive.
        """
        super().__init__(address)
        if liquidation_ratio <= 0:
            raise ValueError("Liquidation ratio must be positive.")
        self.pool = pool
        self.liquidation_ratio = liquidation_ratio
        self.price_source = price_source
        self.loans: dict[str, Loan] = {}

    def open_loan(self, borrower: str, collateral_eth: float, debt_usd: float) -> Loan:
        """Open a loan for ``borrower`` and return it.

        Args:
            borrower: Non-empty borrower identifier.
            collateral_eth: ETH locked as collateral. Must be positive.
            debt_usd: Outstanding debt in USD. Must be positive.

        Returns:
            The registered ``Loan``.
        """
        return self.add_loan(borrower, Loan(collateral_eth, debt_usd))

    def add_loan(self, borrower: str, loan: Loan) -> Loan:
        """Register an open loan for a borrower.

        Args:
            borrower: Non-empty borrower identifier.
            loan: The loan to register.

        Returns:
            The registered ``Loan``.

        Raises:
            ValueError: If ``borrower`` is empty.
        """
        if not borrower:
            raise ValueError("Borrower name must be non-empty.")
        self.loans[borrower] = loan
        return loan

    def collateral_ratio(self, loan: Loan) -> float:
        """Return collateral value divided by debt.

        Reads ``price_source.price`` when one was supplied, otherwise
        ``pool.spot_price``. That read is a contract-to-contract call
        when the source is another contract.

        Args:
            loan: Position to value.

        Returns:
            Collateral value divided by debt at the configured price.
        """
        price = (
            self.price_source.price
            if self.price_source is not None
            else self.pool.spot_price
        )
        return loan.collateral_eth * price / loan.debt_usd

    def liquidate(self, borrower: str) -> Loan:
        """Seize and remove a borrower's loan if it is unhealthy.

        Args:
            borrower: The borrower to liquidate.

        Returns:
            The removed ``Loan``.

        Raises:
            LoanNotFoundError: If ``borrower`` has no open loan.
            PositionNotLiquidatableError: If the loan's collateral ratio
                is still at or above ``self.liquidation_ratio``.
        """
        if borrower not in self.loans:
            raise LoanNotFoundError(f"No loan for {borrower}.")
        loan = self.loans[borrower]
        if self.collateral_ratio(loan) >= self.liquidation_ratio:
            raise PositionNotLiquidatableError("Position is still healthy.")
        return self.loans.pop(borrower)
