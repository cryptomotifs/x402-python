"""x402-python — minimal Python client for the x402 HTTP payment protocol v2.

x402 is a Linux Foundation-hosted open standard (April 2026) that extends
HTTP 402 "Payment Required" with a machine-readable accept-list so clients
can pay for a resource programmatically before retrying the request.

Reference: https://cipher-x402.vercel.app
Spec: https://github.com/linuxfoundation/x402
"""

from .parser import parse_402, ParsedAccept, PaymentAccept
from .selector import select_payment_method
from .header import build_payment_header, ERC3009Authorization, SignerCallback
from .client import Client, fetch_paid
from .errors import (
    X402Error,
    NotA402Error,
    NoCompatibleMethodError,
    PaymentBuildError,
)

__all__ = [
    "parse_402",
    "ParsedAccept",
    "PaymentAccept",
    "select_payment_method",
    "build_payment_header",
    "ERC3009Authorization",
    "SignerCallback",
    "Client",
    "fetch_paid",
    "X402Error",
    "NotA402Error",
    "NoCompatibleMethodError",
    "PaymentBuildError",
]

__version__ = "0.1.0"
