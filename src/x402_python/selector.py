"""Pick the cheapest compatible payment method from an x402 accept list."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Sequence

from .errors import NoCompatibleMethodError
from .parser import PaymentAccept


def select_payment_method(
    accepts: Sequence[PaymentAccept] | Iterable[PaymentAccept],
    preferred_chain: str = "eip155:8453",
    max_amount_usd: float | Decimal = 1.0,
    allowed_schemes: Iterable[str] = ("erc3009", "exact"),
) -> PaymentAccept:
    """Select the cheapest compatible :class:`PaymentAccept`.

    Selection rules (in order):

    1. scheme must be in ``allowed_schemes`` (default: ``erc3009`` / ``exact``)
    2. estimated USD cost must be ``<= max_amount_usd``
    3. prefer the entry whose ``network`` equals ``preferred_chain``
    4. among those, pick the cheapest (smallest ``max_amount_required``)

    Raises :class:`NoCompatibleMethodError` if nothing survives the filter.
    """
    accepts_list = list(accepts)
    if not accepts_list:
        raise NoCompatibleMethodError("accepts list is empty")

    max_usd = Decimal(str(max_amount_usd))
    allowed = set(allowed_schemes)

    candidates = [
        a
        for a in accepts_list
        if a.scheme in allowed and a.max_amount_usd <= max_usd
    ]
    if not candidates:
        raise NoCompatibleMethodError(
            f"no accept entry matches scheme in {sorted(allowed)} "
            f"with max_amount_usd<={max_usd}"
        )

    preferred = [a for a in candidates if a.network == preferred_chain]
    pool = preferred if preferred else candidates

    return min(pool, key=lambda a: a.max_amount_required)
