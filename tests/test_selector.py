"""Tests for x402_python.selector."""

from __future__ import annotations

import pytest

from x402_python import select_payment_method
from x402_python.errors import NoCompatibleMethodError
from x402_python.parser import PaymentAccept


def mk(
    scheme: str = "erc3009",
    network: str = "eip155:8453",
    amount: int = 10_000,
    pay_to: str = "0x000000000000000000000000000000000000dead",
) -> PaymentAccept:
    return PaymentAccept(
        scheme=scheme,
        network=network,
        asset="0xasset",
        max_amount_required=amount,
        resource="https://ex.com/a",
        pay_to=pay_to,
    )


def test_selects_preferred_chain_when_available() -> None:
    a = mk(network="eip155:1", amount=5_000)  # expensive mainnet
    b = mk(network="eip155:8453", amount=20_000)  # cheap-ish base
    chosen = select_payment_method([a, b])
    assert chosen is b


def test_falls_back_to_cheapest_when_preferred_missing() -> None:
    a = mk(network="eip155:1", amount=50_000)
    b = mk(network="eip155:137", amount=20_000)  # cheapest
    c = mk(network="eip155:10", amount=30_000)
    chosen = select_payment_method([a, b, c], preferred_chain="eip155:8453")
    assert chosen is b


def test_filters_out_above_max_usd() -> None:
    # Both > $1 (amounts in USDC with 6 decimals)
    a = mk(amount=2_000_000)  # $2
    b = mk(amount=5_000_000)  # $5
    with pytest.raises(NoCompatibleMethodError):
        select_payment_method([a, b], max_amount_usd=1.0)


def test_filters_out_disallowed_scheme() -> None:
    a = mk(scheme="weird-new-scheme")
    with pytest.raises(NoCompatibleMethodError):
        select_payment_method([a])


def test_allows_exact_scheme_by_default() -> None:
    a = mk(scheme="exact", network="eip155:8453")
    chosen = select_payment_method([a])
    assert chosen.scheme == "exact"


def test_picks_cheapest_among_preferred_when_multiple() -> None:
    a = mk(network="eip155:8453", amount=50_000)
    b = mk(network="eip155:8453", amount=10_000)  # cheapest on preferred
    chosen = select_payment_method([a, b])
    assert chosen is b


def test_empty_accepts_raises() -> None:
    with pytest.raises(NoCompatibleMethodError):
        select_payment_method([])


def test_custom_allowed_schemes() -> None:
    a = mk(scheme="weird")
    chosen = select_payment_method([a], allowed_schemes=("weird",))
    assert chosen.scheme == "weird"
