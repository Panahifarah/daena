from __future__ import annotations

from typing import Any

import httpx

from daena.pipeline.base import DeliveryResult, Sink
from daena.pipeline.record import Record


class HTTPSink(Sink):
    """Delivers records to a remote HTTP endpoint.

    Supports configurable URL, method, headers, timeouts, and batching.
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        cfg = config or {}
        self._url: str = cfg.get("url", "http://localhost:9999/ingest")
        self._method: str = cfg.get("method", "POST").upper()
        self._headers: dict[str, str] = cfg.get("headers", {})
        self._timeout: float = float(cfg.get("timeout", 30.0))
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            headers=self._headers,
        )

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def deliver(self, record: Record) -> DeliveryResult:
        if self._client is None:
            return DeliveryResult(
                success=False,
                record_id=record.record_id,
                error="HTTP sink not initialized",
            )

        payload = {
            "id": record.record_id,
            "source": record.source,
            "type": record.record_type,
            "timestamp": record.timestamp,
            "body": record.body,
            "metadata": record.metadata,
        }

        try:
            response = await self._client.request(
                method=self._method,
                url=self._url,
                json=payload,
            )
            if response.is_success:
                return DeliveryResult(success=True, record_id=record.record_id)
            if 400 <= response.status_code < 500 and response.status_code not in (429,):
                return DeliveryResult(
                    success=False,
                    record_id=record.record_id,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    permanent=True,
                )
            return DeliveryResult(
                success=False,
                record_id=record.record_id,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )
        except httpx.TimeoutException as exc:
            return DeliveryResult(
                success=False,
                record_id=record.record_id,
                error=f"Timeout: {exc}",
            )
        except httpx.RequestError as exc:
            return DeliveryResult(
                success=False,
                record_id=record.record_id,
                error=str(exc),
            )
