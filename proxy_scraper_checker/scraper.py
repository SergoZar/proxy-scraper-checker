from __future__ import annotations

import asyncio
import itertools
import logging
from typing import TYPE_CHECKING

import aiofiles

from .parsers import PROXY_REGEX
from .proxy import Proxy
from .proxy_type import ProxyType
from .utils import bytes_decode, is_http_url

if TYPE_CHECKING:
    from curl_cffi.requests import AsyncSession
    from rich.progress import Progress, TaskID

    from .settings import Settings
    from .storage import ProxyStorage

logger = logging.getLogger(__name__)


async def scrape_one(
    *,
    progress: Progress,
    proto: ProxyType,
    session: AsyncSession,
    source: str,
    storage: ProxyStorage,
    task: TaskID,
    timeout: float,
) -> None:
    try:
        if is_http_url(source):
            r = await session.get(source, timeout=timeout)
            r.raise_for_status()
            text = r.text
        else:
            async with aiofiles.open(source, "rb") as f:
                content = await f.read()
            text = bytes_decode(content)
    except Exception as e:
        logger.warning(
            "%s | %s.%s: %s",
            source,
            e.__class__.__module__,
            e.__class__.__qualname__,
            e,
        )
    else:
        proxies = PROXY_REGEX.finditer(text)
        try:
            proxy = next(proxies)
        except StopIteration:
            logger.warning("%s | No proxies found", source)
        else:
            for proxy in itertools.chain((proxy,), proxies):  # noqa: B020
                try:
                    protocol = ProxyType[
                        proxy.group("protocol").upper().rstrip("S")
                    ]
                except AttributeError:
                    protocol = proto
                storage.add(
                    Proxy(
                        protocol=protocol,
                        host=proxy.group("host"),
                        port=int(proxy.group("port")),
                        username=proxy.group("username"),
                        password=proxy.group("password"),
                    )
                )
    progress.advance(task_id=task, advance=1)


async def scrape_all(
    *,
    progress: Progress,
    session: AsyncSession,
    settings: Settings,
    storage: ProxyStorage,
) -> None:
    progress_tasks = {
        proto: progress.add_task(
            description="", total=len(sources), col1="Scraper", col2=proto.name
        )
        for proto, sources in settings.sources.items()
    }
    await asyncio.gather(
        *(
            scrape_one(
                progress=progress,
                proto=proto,
                session=session,
                source=source,
                storage=storage,
                task=progress_tasks[proto],
                timeout=settings.source_timeout,
            )
            for proto, sources in settings.sources.items()
            for source in sources
        )
    )
