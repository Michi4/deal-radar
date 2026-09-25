"""Driver SDK: hot-swappable marketplace drivers + transport/proxy + circuit breaker."""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .contracts import CanonicalListing


class DriverManifest(BaseModel):
    id: str
    version: str = "0.1.0"
    display_name: str = ""
    regions: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    access_mode: str = "public_web"  # official_api|public_web
    automation_permission: str = "unknown"  # permitted|unknown|not_permitted
    rate_limit_rpm: int = 30


class SearchQuery(BaseModel):
    keywords: str = ""
    category: str = ""
    max_price: float | None = None
    min_price: float | None = None
    location: str = ""
    radius_km: int | None = None
    limit: int = 20


class HealthStatus(BaseModel):
    ok: bool = True
    degraded: bool = False
    last_ok_ts: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


# ---- Transport / proxy layer (interchangeable) ----
class TransportProvider(ABC):
    @abstractmethod
    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        ...


class DirectTransport(TransportProvider):
    def __init__(self, timeout: float = 15.0):
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                         headers={"User-Agent": "deal-radar/0.1 (+personal hobbyist use)"})

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)


class ProxyTransport(TransportProvider):
    """Single HTTP(S) proxy, e.g. http://user:pass@host:port. Swappable per driver."""
    def __init__(self, proxy_url: str, timeout: float = 15.0):
        self._client = httpx.AsyncClient(proxy=proxy_url, timeout=timeout, follow_redirects=True,
                                         headers={"User-Agent": "deal-radar/0.1"})

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)


class RotatingProxyTransport(TransportProvider):
    """Round-robin over N proxy URLs. On failure caller retries -> next proxy."""
    def __init__(self, proxy_urls: list[str], timeout: float = 15.0):
        self.urls = proxy_urls
        self._idx = 0
        self._clients = [httpx.AsyncClient(proxy=u, timeout=timeout, follow_redirects=True) for u in proxy_urls]

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        if not self._clients:
            raise RuntimeError("no proxies configured")
        client = self._clients[self._idx % len(self._clients)]
        self._idx += 1
        return await client.get(url, **kwargs)


def transport_from_config(cfg: dict[str, Any] | None) -> TransportProvider:
    cfg = cfg or {"type": "direct"}
    t = cfg.get("type", "direct")
    if t == "proxy":
        return ProxyTransport(cfg["url"])
    if t == "rotating":
        return RotatingProxyTransport(cfg.get("urls", []))
    return DirectTransport(timeout=float(cfg.get("timeout", 15.0)))


# ---- Circuit breaker ----
@dataclass
class CircuitBreaker:
    fail_threshold: int = 5
    cooldown_s: float = 120.0
    failures: int = 0
    opened_at: float | None = None

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.fail_threshold:
            self.opened_at = time.time()

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at > self.cooldown_s:
            self.failures = 0
            self.opened_at = None
            return False
        return True


class MarketplaceDriver(ABC):
    manifest: DriverManifest
    transport: TransportProvider = field(default=None)  # type: ignore

    def __init__(self, transport: TransportProvider | None = None):
        self.transport = transport or DirectTransport()
        self.health = HealthStatus()
        self.breaker = CircuitBreaker()

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        ...

    async def fetch_detail(self, native_id_or_url: str) -> CanonicalListing | None:
        return None

    async def health_check(self) -> HealthStatus:
        return self.health

    async def guarded_search(self, query: SearchQuery) -> tuple[list[CanonicalListing], str | None]:
        """Retry once + alternate handling. Never raises: returns ([], error)."""
        if self.breaker.is_open:
            return [], f"{self.manifest.id} circuit-open (degraded, cooldown)"
        last_err: str | None = None
        for attempt in range(2):
            try:
                res = await self.search(query)
                self.breaker.record_success()
                self.health.ok = True
                self.health.degraded = False
                self.health.last_ok_ts = time.time()
                self.health.consecutive_failures = 0
                return res, None
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                self.breaker.record_failure()
                self.health.consecutive_failures += 1
                self.health.last_error = last_err
                if self.breaker.is_open:
                    self.health.ok = False
                    self.health.degraded = True
                await asyncio.sleep(0.5 * (attempt + 1))
        self.health.ok = False
        return [], last_err


class DriverRegistry:
    def __init__(self):
        self._drivers: dict[str, MarketplaceDriver] = {}

    def register(self, driver: MarketplaceDriver) -> None:
        self._drivers[driver.manifest.id] = driver

    def get(self, driver_id: str) -> MarketplaceDriver | None:
        return self._drivers.get(driver_id)

    def ids(self) -> list[str]:
        return sorted(self._drivers.keys())

    def manifests(self) -> list[DriverManifest]:
        return [d.manifest for d in self._drivers.values()]
