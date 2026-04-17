# x402-python

Minimal Python client for the [x402 HTTP payment protocol v2](https://github.com/linuxfoundation/x402) — a Linux Foundation-hosted open standard (April 2026) that turns the long-unused HTTP `402 Payment Required` status into a machine-readable payment handshake.

**Why this exists**: the x402 reference implementations ship TypeScript and Go clients. There was no Python client. This fills that gap with a tiny, typed, zero-crypto-deps package suitable for agents, scrapers, and micropayment-paid APIs.

## Install

```bash
pip install x402-python
```

Python 3.9+. The only runtime dependency is `requests`.

## Quick start

```python
from x402_python import Client, select_payment_method, build_payment_header

MY_ADDRESS = "0xYourEvmAddress..."  # signer/payer

def sign(authorization, accept):
    # Plug in your favourite EIP-712 signer here.  Example using eth-account:
    #   from eth_account import Account
    #   from eth_account.messages import encode_typed_data
    #   signable = encode_typed_data(full_message=_build_3009_typed_data(authorization, accept))
    #   return Account.sign_message(signable, private_key=PRIVATE_KEY).signature.hex()
    raise NotImplementedError("wire up your signer")

def on_payment(parsed):
    accept = select_payment_method(
        parsed.accepts,
        preferred_chain="eip155:8453",  # Base
        max_amount_usd=0.05,
    )
    return build_payment_header(accept, MY_ADDRESS, sign)

client = Client()
resp = client.fetch_paid(
    "https://cipher-x402.vercel.app/premium/mev-deep-dive",
    on_payment=on_payment,
)
print(resp.status_code, resp.text[:120])
```

## API

| Symbol | Purpose |
| --- | --- |
| `parse_402(response)` | Parse a `requests.Response` / dict / JSON string into a `ParsedAccept` dataclass. Raises `NotA402Error` on malformed input. |
| `select_payment_method(accepts, preferred_chain="eip155:8453", max_amount_usd=1.0)` | Pick the cheapest compatible method. Raises `NoCompatibleMethodError` if nothing matches. |
| `build_payment_header(accept, signer_address, signer)` | Build the base64-encoded `X-Payment` header. `signer` is a callback — this package does **not** pull in a crypto lib. |
| `Client.fetch_paid(url, on_payment=...)` | GET the URL; on a 402, call `on_payment(parsed)`, grab the header it returns, and retry once with `X-Payment` set. |
| `fetch_paid(url, on_payment=...)` | Module-level shortcut around a fresh `Client`. |

All public objects are exported from the top-level package:

```python
from x402_python import (
    parse_402, select_payment_method, build_payment_header,
    Client, fetch_paid,
    ParsedAccept, PaymentAccept, ERC3009Authorization,
    X402Error, NotA402Error, NoCompatibleMethodError, PaymentBuildError,
)
```

## Why is signing a callback?

The x402 spec is scheme-agnostic: `erc3009`, `exact`, and future schemes (Solana SPL, Bitcoin Lightning, etc.) each have their own signing payload. Baking `eth-account` into this package would pin a chain choice and drag in ~15 MB of native deps for people who only need the wire format. The callback pattern keeps the package small and chain-neutral — wire up whatever signer you already use.

A reference signer built on [`eth-account`](https://pypi.org/project/eth-account/) is ~30 lines and lives in the [examples/ folder](https://github.com/cryptomotifs/x402-python/tree/main/examples) of the repo.

## Reference implementation / live demo

- **Live x402 demo**: <https://cipher-x402.vercel.app>
- **Demo source**: <https://github.com/cryptomotifs/cipher-x402>
- **CIPHER signal starter**: <https://github.com/cryptomotifs/cipher-starter>
- **Background article**: ["Monetising Solana APIs with x402 in 2026"](https://dev.to/cryptomotifs/monetising-solana-apis-with-x402-in-2026)

## Test coverage

```
pytest -q --cov=x402_python
```

The suite mocks every HTTP call with `unittest.mock` (no network) and enforces `--cov-fail-under=80`. Current coverage: 90%+ across all modules.

## License

MIT.
