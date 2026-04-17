"""Build the ``X-Payment`` header for an x402-v2 retry request.

This module deliberately does **not** perform ERC-3009 signing itself — that
requires an EVM key + chain-specific EIP-712 domain data, which is a moving
target.  Instead, callers pass a :class:`SignerCallback` that returns the
signature bytes.  A reference ``eth-account`` signer is documented in the
README but intentionally not a runtime dependency.

The header format follows the x402 v2 spec:

    X-Payment: <base64-json>

where the JSON body is::

    {
      "x402Version": 2,
      "scheme": "erc3009",
      "network": "eip155:8453",
      "payload": {
        "authorization": {
          "from": "0x...",
          "to": "0x...",
          "value": "10000",
          "validAfter": "0",
          "validBefore": "1735689600",
          "nonce": "0x..."
        },
        "signature": "0x..."
      }
    }
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Callable, Mapping

from .errors import PaymentBuildError
from .parser import PaymentAccept


@dataclass(frozen=True)
class ERC3009Authorization:
    """Fields of an ERC-3009 ``transferWithAuthorization`` message."""

    from_address: str
    to: str
    value: str  # decimal string
    valid_after: str  # unix seconds, decimal string
    valid_before: str  # unix seconds, decimal string
    nonce: str  # 0x-prefixed 32-byte hex

    def to_json(self) -> dict[str, str]:
        return {
            "from": self.from_address,
            "to": self.to,
            "value": self.value,
            "validAfter": self.valid_after,
            "validBefore": self.valid_before,
            "nonce": self.nonce,
        }


SignerCallback = Callable[[ERC3009Authorization, PaymentAccept], str]
"""Callback: takes an authorization + the selected accept entry, returns a
0x-prefixed signature hex string.  Typically wraps ``eth_account`` or a remote
signer.  Left as a callback so the library has zero crypto dependencies."""


def _random_nonce() -> str:
    return "0x" + os.urandom(32).hex()


def build_payment_header(
    accept: PaymentAccept,
    signer_address: str,
    signer: SignerCallback,
    *,
    valid_for_seconds: int = 600,
    nonce: str | None = None,
    now_ts: int | None = None,
) -> str:
    """Build an ``X-Payment`` header value for the given accept entry.

    Args:
        accept: the chosen :class:`PaymentAccept` (e.g. from :func:`select_payment_method`).
        signer_address: the ``from`` address of the authorization (checksum
            format recommended).
        signer: callback that returns a hex signature for an EIP-712 typed
            data message.  The library does not attempt to sign on its own.
        valid_for_seconds: how long the authorization is valid for.
        nonce: optional override for testing; randomly generated otherwise.
        now_ts: optional override for ``time.time()``; testing hook.

    Returns:
        a string safe to drop into an ``X-Payment`` header.
    """
    if accept.scheme not in ("erc3009", "exact"):
        raise PaymentBuildError(
            f"scheme={accept.scheme!r} is not supported by this client "
            f"(only 'erc3009' and 'exact')"
        )
    if not signer_address.startswith("0x") or len(signer_address) != 42:
        raise PaymentBuildError(f"signer_address does not look like EVM: {signer_address!r}")

    now = int(now_ts if now_ts is not None else time.time())
    authz = ERC3009Authorization(
        from_address=signer_address,
        to=accept.pay_to,
        value=str(accept.max_amount_required),
        valid_after="0",
        valid_before=str(now + valid_for_seconds),
        nonce=nonce or _random_nonce(),
    )

    try:
        signature = signer(authz, accept)
    except Exception as exc:
        raise PaymentBuildError(f"signer callback raised: {exc}") from exc

    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise PaymentBuildError(
            f"signer callback must return a 0x-prefixed hex string, got {signature!r}"
        )

    payload: Mapping[str, object] = {
        "x402Version": 2,
        "scheme": accept.scheme,
        "network": accept.network,
        "payload": {
            "authorization": authz.to_json(),
            "signature": signature,
        },
    }

    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(encoded).decode("ascii")


# Re-export as asdict-friendly name
__all__ = [
    "ERC3009Authorization",
    "SignerCallback",
    "build_payment_header",
]

_ = asdict  # keep import used even though we construct dicts manually
