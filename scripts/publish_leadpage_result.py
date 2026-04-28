#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_message(*, provider: str, ts: int, nonce: str, body_bytes: bytes) -> bytes:
    # Must match server canonical format in `api/leadpage_routes.py`.
    h = _sha256_hex(body_bytes)
    msg = f"v1\nprovider:{provider}\nts:{ts}\nnonce:{nonce}\nbody_sha256:{h}\n"
    return msg.encode("utf-8")


def _hmac_hex(key: str, msg: bytes) -> str:
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _nonce(provider: str) -> str:
    # Deterministic enough uniqueness for CLI usage (timestamp + hash).
    seed = f"{provider}:{time.time_ns()}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:24]


@dataclass(frozen=True)
class PublishRequest:
    url: str
    provider: str
    key: str | None
    signed: bool
    payload: dict[str, Any]


def _build_headers(req: PublishRequest, body: bytes) -> dict[str, str]:
    headers = {"content-type": "application/json"}

    if req.signed:
        if not req.key:
            raise SystemExit("--signed requires --key")
        ts = int(time.time())
        nonce = _nonce(req.provider)
        sig = _hmac_hex(
            req.key, _canonical_message(provider=req.provider, ts=ts, nonce=nonce, body_bytes=body)
        )
        headers["x-leadpage-timestamp"] = str(ts)
        headers["x-leadpage-nonce"] = nonce
        headers["x-leadpage-signature"] = sig
        return headers

    # Unsigned mode: provider key can still be passed as header auth.
    if req.key:
        headers["x-leadpage-provider-key"] = req.key
    return headers


def _http_post_json(url: str, *, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            raw = resp.read()
            return int(resp.status), raw.decode("utf-8", errors="replace")
    except Exception as e:
        raise SystemExit(f"request failed: {e}") from e


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Publish a result into the leadpage engine (optionally HMAC-signed)."
    )
    ap.add_argument("--base-url", default="http://127.0.0.1:8001", help="Backend base URL")
    ap.add_argument("--provider", required=True, help="Provider id (engine/trader namespace)")
    ap.add_argument("--run-id", required=True, help="Provider run id")
    ap.add_argument("--title", default=None, help="Optional title")
    ap.add_argument("--ticker", default=None, help="Optional ticker/symbol")
    ap.add_argument("--total-return-pct", type=float, default=None)
    ap.add_argument("--sharpe", type=float, default=None)
    ap.add_argument("--max-drawdown-pct", type=float, default=None)
    ap.add_argument("--trade-count", type=int, default=None)
    ap.add_argument("--meta-json", default=None, help='Optional JSON object string for "meta"')
    ap.add_argument("--schema-version", type=int, default=1)

    ap.add_argument("--key", default=None, help="Provider shared secret (header key or HMAC key)")
    ap.add_argument("--signed", action="store_true", help="Use HMAC signed publishing headers")
    ap.add_argument("--dry-run", action="store_true", help="Print curl command instead of sending")

    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")
    provider = str(args.provider).strip()
    if not provider:
        raise SystemExit("--provider is required")

    meta: dict[str, Any] | None = None
    if args.meta_json:
        try:
            obj = json.loads(args.meta_json)
        except Exception as e:
            raise SystemExit(f"invalid --meta-json: {e}") from e
        if not isinstance(obj, dict):
            raise SystemExit("--meta-json must be a JSON object")
        meta = obj

    payload: dict[str, Any] = {
        "schema_version": int(args.schema_version),
        "provider": provider,
        "run_id": str(args.run_id),
        "title": args.title,
        "ticker": args.ticker,
        "total_return_pct": args.total_return_pct,
        "sharpe": args.sharpe,
        "max_drawdown_pct": args.max_drawdown_pct,
        "trade_count": args.trade_count,
        "meta": meta,
    }

    # Remove null keys for cleaner signatures and smaller payloads.
    payload = {k: v for k, v in payload.items() if v is not None}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    url = f"{base}/leadpage/providers/{provider}/results"
    req = PublishRequest(
        url=url, provider=provider, key=args.key, signed=bool(args.signed), payload=payload
    )
    headers = _build_headers(req, body)

    if args.dry_run:
        hdrs = " ".join([f"-H '{k}: {v}'" for k, v in headers.items()])
        print(f"curl -X POST '{url}' {hdrs} -d '{body.decode('utf-8')}'")
        return

    status, text = _http_post_json(url, body=body, headers=headers)
    print(f"status: {status}")
    print(text)


if __name__ == "__main__":
    main()
