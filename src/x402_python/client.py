"""High-level convenience client that does GET -> 402 -> pay -> retry."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

import requests

from .errors import NotA402Error, X402Error
from .parser import ParsedAccept, parse_402


OnPayment = Callable[[ParsedAccept], str]
"""Callback that receives the parsed 402 accept-list and returns the full
base64-encoded X-Payment header value.  Typically built with
:func:`x402_python.select_payment_method` + :func:`x402_python.build_payment_header`."""


class Client:
    """Tiny wrapper around :class:`requests.Session` with automatic 402 retry.

    Usage::

        from x402_python import Client, select_payment_method, build_payment_header

        def pay(parsed):
            accept = select_payment_method(parsed.accepts, preferred_chain="eip155:8453")
            return build_payment_header(accept, MY_ADDRESS, my_signer)

        c = Client()
        r = c.fetch_paid("https://cipher-x402.vercel.app/premium/mev-deep-dive", on_payment=pay)
        print(r.text)
    """

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 30.0) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout

    def fetch_paid(
        self,
        url: str,
        *,
        on_payment: OnPayment,
        method: str = "GET",
        headers: Optional[Mapping[str, str]] = None,
        max_retries: int = 1,
        **request_kwargs: Any,
    ) -> requests.Response:
        """GET ``url``.  If a 402 comes back, call ``on_payment`` + retry.

        ``on_payment`` receives the parsed accept list and must return the
        full (already base64-encoded) value for the ``X-Payment`` header.

        ``max_retries`` defaults to 1 — i.e. at most one 402 round-trip.  This
        protects against infinite loops if the server keeps returning 402 with
        updated quotes.
        """
        hdrs: dict[str, str] = dict(headers or {})
        response = self._session.request(
            method, url, headers=hdrs, timeout=self._timeout, **request_kwargs
        )

        retries = 0
        while response.status_code == 402 and retries < max_retries:
            try:
                parsed = parse_402(response)
            except NotA402Error:
                # malformed 402 — surface as-is
                return response

            payment_header = on_payment(parsed)
            if not payment_header:
                raise X402Error("on_payment callback returned empty header")

            hdrs["X-Payment"] = payment_header
            response = self._session.request(
                method, url, headers=hdrs, timeout=self._timeout, **request_kwargs
            )
            retries += 1

        return response


def fetch_paid(
    url: str,
    *,
    on_payment: OnPayment,
    method: str = "GET",
    headers: Optional[Mapping[str, str]] = None,
    max_retries: int = 1,
    **request_kwargs: Any,
) -> requests.Response:
    """Module-level shortcut for :meth:`Client.fetch_paid` with a fresh client."""
    return Client().fetch_paid(
        url,
        on_payment=on_payment,
        method=method,
        headers=headers,
        max_retries=max_retries,
        **request_kwargs,
    )
