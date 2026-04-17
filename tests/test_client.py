"""Tests for x402_python.client."""

from __future__ import annotations

import json
from typing import Any, List
from unittest.mock import MagicMock

import pytest
import requests

from x402_python import Client, fetch_paid
from x402_python.errors import X402Error
from x402_python.parser import ParsedAccept


PAID_BODY = {"access": "granted", "content": "MEV alpha"}
A402_BODY = {
    "x402Version": 2,
    "accepts": [
        {
            "scheme": "erc3009",
            "network": "eip155:8453",
            "asset": "0xasset",
            "maxAmountRequired": "10000",
            "resource": "https://cipher-x402.vercel.app/premium/mev-deep-dive",
            "payTo": "0x" + "bb" * 20,
        }
    ],
}


def _mock_resp(status: int, body: Any) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.headers = {"Content-Type": "application/json"}
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


def test_pays_once_and_retries() -> None:
    calls: List[dict[str, Any]] = []
    session = MagicMock()

    def request(method: str, url: str, **kwargs: Any) -> MagicMock:
        calls.append({"method": method, "url": url, "headers": dict(kwargs["headers"])})
        if len(calls) == 1:
            return _mock_resp(402, A402_BODY)
        return _mock_resp(200, PAID_BODY)

    session.request.side_effect = request

    def on_payment(parsed: ParsedAccept) -> str:
        assert parsed.x402_version == 2
        assert parsed.accepts[0].scheme == "erc3009"
        return "BASE64HEADER=="

    c = Client(session=session)
    resp = c.fetch_paid("https://cipher-x402.vercel.app/premium/mev-deep-dive", on_payment=on_payment)

    assert resp.status_code == 200
    assert resp.json() == PAID_BODY
    assert len(calls) == 2
    assert "X-Payment" not in calls[0]["headers"]
    assert calls[1]["headers"]["X-Payment"] == "BASE64HEADER=="


def test_non_402_passthrough() -> None:
    session = MagicMock()
    session.request.return_value = _mock_resp(200, PAID_BODY)

    c = Client(session=session)
    resp = c.fetch_paid("https://x/a", on_payment=lambda p: "x")
    assert resp.status_code == 200
    assert session.request.call_count == 1


def test_on_payment_empty_header_raises() -> None:
    session = MagicMock()
    session.request.return_value = _mock_resp(402, A402_BODY)

    c = Client(session=session)
    with pytest.raises(X402Error):
        c.fetch_paid("https://x/a", on_payment=lambda p: "")


def test_max_retries_stops_loop() -> None:
    session = MagicMock()
    session.request.return_value = _mock_resp(402, A402_BODY)

    c = Client(session=session)
    resp = c.fetch_paid("https://x/a", on_payment=lambda p: "h", max_retries=1)
    # After 1 retry we stop and return the still-402 response.
    assert resp.status_code == 402
    assert session.request.call_count == 2


def test_malformed_402_returned_as_is() -> None:
    session = MagicMock()
    session.request.return_value = _mock_resp(402, {"not": "x402"})

    c = Client(session=session)
    resp = c.fetch_paid("https://x/a", on_payment=lambda p: "h")
    assert resp.status_code == 402


def test_module_level_fetch_paid_uses_fresh_client() -> None:
    # Just exercise the shortcut — patch requests.Session inside Client.
    import x402_python.client as client_mod

    real_session = MagicMock(spec=requests.Session)
    real_session.request.return_value = _mock_resp(200, PAID_BODY)
    client_mod.requests.Session = MagicMock(return_value=real_session)  # type: ignore[assignment]
    try:
        r = fetch_paid("https://x/a", on_payment=lambda p: "h")
        assert r.status_code == 200
    finally:
        client_mod.requests.Session = requests.Session  # type: ignore[assignment]
