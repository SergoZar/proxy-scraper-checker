from __future__ import annotations

from io import StringIO
from time import perf_counter
from typing import TYPE_CHECKING, Optional

import attrs

from .parsers import parse_ipv4
from .settings import CheckWebsiteType, Settings

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession

    from .proxy_type import ProxyType


@attrs.define(
    repr=False,
    unsafe_hash=True,
    weakref_slot=False,
    kw_only=True,
    getstate_setstate=False,
    match_args=False,
)
class Proxy:
    protocol: ProxyType
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    timeout: float = attrs.field(init=False, eq=False)
    exit_ip: Optional[str] = attrs.field(init=False, eq=False)

    async def check(self, *, session: AsyncSession, settings: Settings) -> None:
        async with settings.semaphore:
            start = perf_counter()
            response = await session.request(
                "GET",
                settings.check_website,
                headers=settings.check_website_type.headers,
                timeout=settings.timeout,
                proxy=f"{self.protocol._value_}://{self.username}:{self.password}@{self.host}:{self.port}"
                if self.username is not None and self.password is not None
                else f"{self.protocol._value_}://{self.host}:{self.port}",
            )
        response.raise_for_status()
        self.timeout = perf_counter() - start
        if settings.check_website_type == CheckWebsiteType.HTTPBIN_IP:
            self.exit_ip = parse_ipv4(response.json()["origin"])
        elif settings.check_website_type == CheckWebsiteType.PLAIN_IP:
            self.exit_ip = parse_ipv4(response.text)
        else:
            self.exit_ip = None

    def as_str(self, *, include_protocol: bool) -> str:
        with StringIO() as buf:
            if include_protocol:
                buf.write(f"{self.protocol.name.lower()}://")
            if self.username is not None and self.password is not None:
                buf.write(f"{self.username}:{self.password}@")
            buf.write(f"{self.host}:{self.port}")
            return buf.getvalue()
