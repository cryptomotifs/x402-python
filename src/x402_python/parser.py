"""Parse HTTP 402 responses that follow the x402 v2 accept-list format.

An x402 v2 response looks like::

    HTTP/1.1 402 Payment Required
    Content-Type: application/json
    X-Payment-Version: 2

    {
      "x402Version": 2,
      "accepts": [
        {
          "scheme": "erc3009",
          "network": "eip155:8453",
          "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
          "maxAmountRequired": "10000",
          "resource": "https://example.com/premium/a",
          "payTo": "0xabc...",
          "description": "Access to resource A",
          "mimeType": "application/json",
          "expiresAt": "2026-12-31T23:59:59Z"
        }
      ]
    }

This module normalises that payload into typed ``PaymentAccept`` dataclasses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from .errors import NotA402Error


@runtime_checkable
class _ResponseLike(Protocol):
    """Duck-typed subset of ``requests.Response`` we need.

    Keeping it a Protocol means callers can pass any object that exposes
    ``status_code`` + ``headers`` + ``text``/``json()``.  That makes unit testing
    trivial and lets the library stay dep-free beyond ``requests``.
    """

    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self) -> Any: ...

    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class PaymentAccept:
    """One entry inside the ``accepts`` array of an x402 v2 402 body."""

    scheme: str
    network: str
    asset: str
    max_amount_required: int
    resource: str
    pay_to: str
    description: str = ""
    mime_type: str = ""
    expires_at: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def max_amount_usd(self) -> Decimal:
        """Rough USD estimate assuming the asset is a 6-decimal stablecoin (USDC/USDT).

        Non-stable assets should be priced by the caller — this is a convenience
        default that matches the most common x402 flow today.
        """
        # USDC/USDT on EVM have 6 decimals; Solana USDC also has 6 decimals.
        return Decimal(self.max_amount_required) / Decimal(10**6)


@dataclass(frozen=True)
class ParsedAccept:
    """The full accept-list payload."""

    x402_version: int
    accepts: Sequence[PaymentAccept]
    raw: Mapping[str, Any]


def _coerce_int(value: Any) -> int:
    """x402 spec requires a decimal string for amounts, but accept int too."""
    if isinstance(value, bool):  # bool is a subclass of int in Python
        raise NotA402Error("maxAmountRequired must be a string or integer, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise NotA402Error(f"maxAmountRequired not an integer: {value!r}") from exc
    raise NotA402Error(f"maxAmountRequired not an integer-like: {value!r}")


def _parse_accept_entry(entry: Mapping[str, Any]) -> PaymentAccept:
    try:
        scheme = str(entry["scheme"])
        network = str(entry["network"])
        asset = str(entry["asset"])
        max_amount = _coerce_int(entry["maxAmountRequired"])
        resource = str(entry["resource"])
        pay_to = str(entry["payTo"])
    except KeyError as exc:
        raise NotA402Error(f"accept entry missing required field {exc}") from exc

    known_keys = {
        "scheme",
        "network",
        "asset",
        "maxAmountRequired",
        "resource",
        "payTo",
        "description",
        "mimeType",
        "expiresAt",
    }
    extra = {k: v for k, v in entry.items() if k not in known_keys}

    return PaymentAccept(
        scheme=scheme,
        network=network,
        asset=asset,
        max_amount_required=max_amount,
        resource=resource,
        pay_to=pay_to,
        description=str(entry.get("description", "")),
        mime_type=str(entry.get("mimeType", "")),
        expires_at=str(entry.get("expiresAt", "")),
        extra=extra,
    )


def parse_402(response: _ResponseLike | Mapping[str, Any] | str) -> ParsedAccept:
    """Parse an HTTP 402 response body into a :class:`ParsedAccept`.

    Accepts:

    * a ``requests.Response``-like object (status_code must be 402),
    * a pre-parsed JSON ``Mapping``,
    * a raw JSON ``str``.

    Raises :class:`NotA402Error` if the payload is not a valid x402 v2 envelope.
    """
    if isinstance(response, str):
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise NotA402Error(f"body is not valid JSON: {exc}") from exc
    elif isinstance(response, Mapping):
        payload = response
    else:
        # Response-like.
        if response.status_code != 402:
            raise NotA402Error(
                f"expected status 402, got {response.status_code}"
            )
        try:
            payload = response.json()
        except Exception as exc:  # json() may raise any number of errors
            raise NotA402Error(f"response.json() failed: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise NotA402Error("x402 body must be a JSON object")

    version = payload.get("x402Version", 1)
    if not isinstance(version, int) or version < 2:
        raise NotA402Error(
            f"unsupported x402Version={version!r} (this client requires v2)"
        )

    accepts_raw = payload.get("accepts")
    if not isinstance(accepts_raw, Iterable) or isinstance(accepts_raw, (str, bytes)):
        raise NotA402Error("x402 body must contain an 'accepts' array")

    accepts: list[PaymentAccept] = []
    for entry in accepts_raw:
        if not isinstance(entry, Mapping):
            raise NotA402Error(f"accept entry must be an object, got {type(entry)!r}")
        accepts.append(_parse_accept_entry(entry))

    if not accepts:
        raise NotA402Error("accepts list is empty — server did not offer any payment methods")

    return ParsedAccept(x402_version=version, accepts=accepts, raw=dict(payload))
