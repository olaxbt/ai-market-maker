from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class NexusDataConfig:
    """Config for Nexus two-domain API.

    Defaults match `repo-improvement/nexus-data-skill.md`.
    """

    auth_base: str = "https://api.olaxbt.xyz/api"
    api_base: str = "https://api-data.olaxbt.xyz/api/v1"
    jwt: str | None = None
    api_key: str | None = None
    timeout_s: float = 20.0

    @staticmethod
    def from_env() -> "NexusDataConfig":
        return NexusDataConfig(
            auth_base=(os.getenv("NEXUS_AUTH_BASE") or "https://api.olaxbt.xyz/api").rstrip("/"),
            api_base=(os.getenv("NEXUS_API_BASE") or "https://api-data.olaxbt.xyz/api/v1").rstrip(
                "/"
            ),
            jwt=(os.getenv("NEXUS_JWT") or "").strip() or None,
            api_key=(os.getenv("NEXUS_API_KEY") or "").strip() or None,
            timeout_s=float(os.getenv("NEXUS_TIMEOUT_S") or "30"),
        )


class NexusDataClient:
    def __init__(self, cfg: NexusDataConfig | None = None):
        self.cfg = cfg or NexusDataConfig.from_env()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.cfg.jwt:
            headers["Authorization"] = f"Bearer {self.cfg.jwt}"
        if self.cfg.api_key:
            headers["x-api-key"] = self.cfg.api_key
        return headers

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.cfg.api_base}{path}"
        timeout = self.cfg.timeout_s if timeout_s is None else timeout_s
        with httpx.Client(timeout=timeout) as client:
            r = client.get(url, headers=self._headers(), params=params)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Surface a more actionable hint for common auth failures.
                if r.status_code in (401, 403):
                    raise httpx.HTTPStatusError(
                        f"{e}. Nexus Skills API requires a wallet JWT and/or a valid x-api-key. "
                        "Set NEXUS_JWT and/or NEXUS_API_KEY.",
                        request=e.request,
                        response=e.response,
                    ) from None
                raise
            data = r.json()
            return data if isinstance(data, dict) else {"data": data}

    def get_openapi_document(self, *, timeout_s: float | None = None) -> dict[str, Any]:
        """Fetch OpenAPI 3 JSON (same auth as data calls). Path overridable via ``NEXUS_OPENAPI_PATH``."""
        path = (os.getenv("NEXUS_OPENAPI_PATH") or "/openapi.json").strip()
        if not path.startswith("/"):
            path = "/" + path
        to = timeout_s if timeout_s is not None else min(self.cfg.timeout_s, 60.0)
        return self.get(path, timeout_s=to)

    def healthcheck(self) -> dict[str, Any]:
        """Best-effort connectivity check.

        Many endpoints require JWT; we still return a structured result.
        """
        out: dict[str, Any] = {
            "api_base": self.cfg.api_base,
            "has_jwt": bool(self.cfg.jwt),
            "has_api_key": bool(self.cfg.api_key),
        }
        try:
            # pick a low-cost endpoint; if JWT missing/invalid it may 401/403.
            self.get("/news", params={"limit": 1})
            out["ok"] = True
        except Exception as e:
            out["ok"] = False
            out["error"] = str(e)
        return out
