"""Smart-contract and oracle primitives taught in notebook 6.

Notebook 6 defines these classes inline so the lesson can be read in one
place. Later notebooks import this copy: a swap pool, a lending protocol,
and the price sources a lending rule might trust.

An oracle is not a contract. It is an input a contract treats as fact.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


class SmartContract:
    """Code that lives at an address and runs when something calls it.

    The chain does not understand loans or swaps. It understands: this
    address, this method, these arguments. The methods below are the rules.
    """

    def __init__(self, address: str) -> None:
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
            raise AttributeError(
                f"{self.address} has no public method {method!r}."
            )
        func = getattr(self, method, None)
        if not callable(func):
            raise AttributeError(
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
    """Return collateral value divided by debt, at a given ETH price."""
    if collateral_eth <= 0 or debt_usd <= 0 or eth_price_usd <= 0:
        raise ValueError("Collateral, debt, and price must be positive.")
    return collateral_eth * eth_price_usd / debt_usd


def should_liquidate(ratio: float, threshold: float = 1.5) -> bool:
    """Return whether a collateral ratio is below the liquidation threshold."""
    return ratio < threshold


class MedianOracle:
    """A price source that reports the median of several independent reports."""

    def __init__(self, reports: list[PriceReport]) -> None:
        if not reports:
            raise ValueError("At least one price report is required.")
        self.reports = reports

    @property
    def price(self) -> float:
        """Median reported price — resists a single outlier report."""
        return statistics.median(report.eth_price_usd for report in self.reports)


class AMMPool(SmartContract):
    """A constant-product (x*y=k) two-asset market maker.

    This is a smart contract: it has an address, and swaps are method
    calls. The displayed spot price is ``USD reserve / ETH reserve``.
    That number is not a journalist. It is the current ratio of two
    piles of tokens.
    """

    def __init__(
        self, address: str, eth_reserve: float, usd_reserve: float
    ) -> None:
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
        price_source=None,
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

    def open_loan(
        self, borrower: str, collateral_eth: float, debt_usd: float
    ) -> Loan:
        """Open a loan for ``borrower`` and return it."""
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
        """Return collateral value divided by debt, using the configured price source."""
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
