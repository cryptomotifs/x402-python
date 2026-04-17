"""Exception hierarchy for the x402 client."""

from __future__ import annotations


class X402Error(Exception):
    """Base class for all x402 client errors."""


class NotA402Error(X402Error):
    """The response parsed was not an HTTP 402 or lacked a valid accepts list."""


class NoCompatibleMethodError(X402Error):
    """The 402 accepts list contained no method matching the client preferences."""


class PaymentBuildError(X402Error):
    """Failed to build an x-payment header from the selected accept entry."""
