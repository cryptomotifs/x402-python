"""Tests for x402_python.parser."""

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from x402_python import parse_402
from x402_python.errors import NotA402Error
from x402_python.parser import PaymentAccept


def make_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "x402Version": 2,
        "accepts": [
            {
                "scheme": "erc3009",
                "network": "eip155:8453",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "maxAmountRequired": "10000",
                "resource": "https://cipher-x402.vercel.app/premium/mev-deep-dive",
                "payTo": "0xabc0000000000000000000000000000000000001",
                "description": "MEV deep-dive article",
                "mimeType": "application/json",
                "expiresAt": "2026-12-31T23:59:59Z",
            }
        ],
    }
    body.update(overrides)
    return body


class _FakeResp:
    def __init__(self, status: int, body: Mapping[str, Any] | str) -> None:
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self._body = body

    def json(self) -> Any:
        if isinstance(self._body, str):
            return json.loads(self._body)
        return self._body

    @property
    def text(self) -> str:
        if isinstance(self._body, str):
            return self._body
        return json.dumps(self._body)


def test_parse_402_from_response_happy_path() -> None:
    resp = _FakeResp(402, make_body())
    parsed = parse_402(resp)
    assert parsed.x402_version == 2
    assert len(parsed.accepts) == 1
    a = parsed.accepts[0]
    assert isinstance(a, PaymentAccept)
    assert a.scheme == "erc3009"
    assert a.network == "eip155:8453"
    assert a.max_amount_required == 10000
    assert float(a.max_amount_usd) == pytest.approx(0.01)


def test_parse_402_from_mapping() -> None:
    parsed = parse_402(make_body())
    assert parsed.accepts[0].description == "MEV deep-dive article"


def test_parse_402_from_string() -> None:
    parsed = parse_402(json.dumps(make_body()))
    assert parsed.accepts[0].pay_to == "0xabc0000000000000000000000000000000000001"


def test_parse_402_preserves_unknown_fields_in_extra() -> None:
    body = make_body()
    body["accepts"][0]["customField"] = "hello"
    parsed = parse_402(body)
    assert parsed.accepts[0].extra == {"customField": "hello"}


def test_parse_402_integer_amount_allowed() -> None:
    body = make_body()
    body["accepts"][0]["maxAmountRequired"] = 10000
    parsed = parse_402(body)
    assert parsed.accepts[0].max_amount_required == 10000


def test_parse_402_rejects_bool_amount() -> None:
    body = make_body()
    body["accepts"][0]["maxAmountRequired"] = True
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_non_402_status() -> None:
    resp = _FakeResp(200, make_body())
    with pytest.raises(NotA402Error):
        parse_402(resp)


def test_parse_402_rejects_malformed_json_string() -> None:
    with pytest.raises(NotA402Error):
        parse_402("{not json")


def test_parse_402_rejects_non_object_body() -> None:
    with pytest.raises(NotA402Error):
        parse_402("[1,2,3]")


def test_parse_402_rejects_old_version() -> None:
    body = make_body(x402Version=1)
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_missing_accepts() -> None:
    body = make_body()
    del body["accepts"]
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_empty_accepts() -> None:
    body = make_body(accepts=[])
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_accept_entry_missing_field() -> None:
    body = make_body()
    del body["accepts"][0]["payTo"]
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_non_object_accept_entry() -> None:
    body = make_body(accepts=["not-an-object"])
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_rejects_garbage_amount_string() -> None:
    body = make_body()
    body["accepts"][0]["maxAmountRequired"] = "not-a-number"
    with pytest.raises(NotA402Error):
        parse_402(body)


def test_parse_402_response_json_raises() -> None:
    class Broken(_FakeResp):
        def json(self) -> Any:
            raise ValueError("broken")

    with pytest.raises(NotA402Error):
        parse_402(Broken(402, "broken"))
