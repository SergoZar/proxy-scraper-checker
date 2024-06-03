from __future__ import annotations

from enum import Enum


class ProxyType(str, Enum):
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    HTTP = "http"
