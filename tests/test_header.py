"""Tests for x402_python.header."""

from __future__ import annotations

import base64
import json

import pytest

from x402_python import build_payment_header
from x402_python.errors import PaymentBuildError
from x402_python.parser import PaymentAccept


ADDR = "0x" + "ab" * 20
OTHER_ADDR = "0x" + "cd" * 20


def accept(scheme: str = "erc3009") -> PaymentAccept:
    return PaymentAccept(
        scheme=scheme,
        network="eip155:8453",
        asset="0xasset",
        max_amount_required=10_000,
        resource="https://ex.com/a",
        pay_to=OTHER_ADDR,
    )


def _fixed_sig(_authz: object, _a: object) -> str:
    return "0x" + "11" * 65


def test_builds_valid_base64_header() -> None:
    header = build_payment_header(accept(), ADDR, _fixed_sig, now_ts=1_700_000_000)
    decoded = json.loads(base64.b64decode(header))
    assert decoded["x402Version"] == 2
    assert decoded["scheme"] == "erc3009"
    assert decoded["network"] == "eip155:8453"
    authz = decoded["payload"]["authorization"]
    assert authz["from"] == ADDR
    assert authz["to"] == OTHER_ADDR
    assert authz["value"] == "10000"
    assert authz["validAfter"] == "0"
    assert int(authz["validBefore"]) == 1_700_000_000 + 600
    assert authz["nonce"].startswith("0x") and len(authz["nonce"]) == 66
    assert decoded["payload"]["signature"] == "0x" + "11" * 65


def test_valid_for_seconds_controls_expiry() -> None:
    header = build_payment_header(
        accept(), ADDR, _fixed_sig, now_ts=1_000, valid_for_seconds=42
    )
    decoded = json.loads(base64.b64decode(header))
    assert decoded["payload"]["authorization"]["validBefore"] == "1042"


def test_explicit_nonce_is_honoured() -> None:
    nonce = "0x" + "aa" * 32
    header = build_payment_header(accept(), ADDR, _fixed_sig, nonce=nonce)
    decoded = json.loads(base64.b64decode(header))
    assert decoded["payload"]["authorization"]["nonce"] == nonce


def test_rejects_unknown_scheme() -> None:
    with pytest.raises(PaymentBuildError):
        build_payment_header(accept(scheme="weird"), ADDR, _fixed_sig)


def test_rejects_bad_signer_address() -> None:
    with pytest.raises(PaymentBuildError):
        build_payment_header(accept(), "not-an-address", _fixed_sig)


def test_rejects_bad_signature_return() -> None:
    def bad_signer(_a: object, _b: object) -> str:
        return "no-prefix"

    with pytest.raises(PaymentBuildError):
        build_payment_header(accept(), ADDR, bad_signer)


def test_signer_exception_wrapped() -> None:
    def boom(_a: object, _b: object) -> str:
        raise RuntimeError("kaboom")

    with pytest.raises(PaymentBuildError) as exc:
        build_payment_header(accept(), ADDR, boom)
    assert "kaboom" in str(exc.value)


def test_exact_scheme_supported() -> None:
    header = build_payment_header(accept(scheme="exact"), ADDR, _fixed_sig)
    decoded = json.loads(base64.b64decode(header))
    assert decoded["scheme"] == "exact"
