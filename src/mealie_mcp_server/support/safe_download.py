"""Bounded untrusted downloads with public-address checks and no second DNS lookup."""

import asyncio
import ipaddress
import math
import re
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from ssl import SSLContext
from typing import Protocol

import anyio
import httpcore2
import httpx2 as httpx

type HostResolver = Callable[[str], Awaitable[list[str]]]
type SocketOption = (
    tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
)


@dataclass
class DownloadResponse:
    status: int
    headers: dict[str, str]
    body: AsyncIterator[bytes]


def is_private_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(parsed, ipaddress.IPv4Address):
        a, b, c, _ = parsed.packed
        return (
            a in {0, 10, 127}
            or a >= 224
            or a == 100
            and 64 <= b <= 127
            or a == 169
            and b == 254
            or a == 172
            and 16 <= b <= 31
            or a == 192
            and b == 168
            or a == 192
            and b == 0
            and c in {0, 2}
            or a == 192
            and b == 88
            and c == 99
            or a == 198
            and b in {18, 19}
            or a == 198
            and b == 51
            and c == 100
            or a == 203
            and b == 0
            and c == 113
        )
    mapped = re.fullmatch(r"::ffff:(\d+\.\d+\.\d+\.\d+)", address, re.IGNORECASE)
    if mapped:
        return is_private_address(mapped[1])
    first, second = int(parsed) >> 112, (int(parsed) >> 96) & 0xFFFF
    return (
        not 0x2000 <= first <= 0x3FFF
        or first == 0x2001
        and (second < 0x200 or second == 0xDB8)
        or first == 0x2002
        or first == 0x3FFF
        and second < 0x1000
    )


class DownloadTransport(Protocol):
    def fetch(
        self, url: str, *, validated_addresses: tuple[str, ...], deadline: float
    ) -> AbstractAsyncContextManager[DownloadResponse]: ...


class _PinnedBackend(httpcore2.AsyncNetworkBackend):
    def __init__(
        self, addresses: tuple[str, ...], deadline: float, private_checker: Callable[[str], bool]
    ) -> None:
        self.addresses, self.deadline, self.private_checker = addresses, deadline, private_checker
        self.backend = httpcore2.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 - required HTTPCore backend signature
        local_address: str | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        last_error: Exception | None = None
        for address in self.addresses:
            try:
                numeric = str(ipaddress.ip_address(address))
            except ValueError:
                raise ValueError("download_url has an invalid pinned address.") from None
            remaining = self.deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise ValueError("Download timed out.")
            try:
                # AnyIO recognizes numeric IPs and bypasses hostname resolution entirely.
                stream = await self.backend.connect_tcp(
                    numeric,
                    port,
                    timeout=min(timeout or 5, 5, remaining),
                    socket_options=socket_options,
                )
            except (httpcore2.ConnectError, httpcore2.ConnectTimeout) as error:
                last_error = error
                continue
            peer = stream.get_extra_info("server_addr")
            if (
                not isinstance(peer, tuple)
                or not peer
                or not isinstance(peer[0], str)
                or self.private_checker(peer[0])
            ):
                with anyio.CancelScope(shield=True):
                    await stream.aclose()
                raise ValueError(
                    "download_url connected to a private or non-public address and was refused."
                )
            return stream
        raise ValueError(
            "Download failed: could not connect to the validated addresses."
        ) from last_error

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class PinnedDownloadTransport:
    def __init__(
        self,
        *,
        private_checker: Callable[[str], bool] = is_private_address,
        ssl_context: SSLContext | None = None,
    ) -> None:
        self.private_checker = private_checker
        self.ssl_context = ssl_context

    @asynccontextmanager
    async def fetch(
        self, url: str, *, validated_addresses: tuple[str, ...], deadline: float
    ) -> AsyncIterator[DownloadResponse]:
        parsed = httpx.URL(url)
        target = httpcore2.URL(
            scheme=parsed.raw_scheme, host=parsed.raw_host, port=parsed.port, target=parsed.raw_path
        )
        backend = _PinnedBackend(validated_addresses, deadline, self.private_checker)
        remaining = max(0, deadline - asyncio.get_running_loop().time())
        timeouts = dict.fromkeys(("connect", "read", "write", "pool"), remaining)
        # This pool never reads proxy environment variables, stores cookies, or reuses DNS state.
        async with httpcore2.AsyncConnectionPool(
            network_backend=backend,
            ssl_context=self.ssl_context,
            max_connections=1,
            max_keepalive_connections=0,
            retries=0,
        ) as pool:
            async with pool.stream(
                "GET",
                target,
                headers=[(b"Host", parsed.netloc), (b"Connection", b"close")],
                extensions={"timeout": timeouts},
            ) as response:
                if not 200 <= response.status <= 599:
                    raise ValueError(
                        "Download failed: source responded with unsupported HTTP status "
                        f"{response.status}."
                    )
                headers: dict[str, str] = {}
                for key, value in response.headers:
                    name = key.decode("ascii").lower()
                    text = value.decode("latin-1")
                    headers[name] = headers[name] + ", " + text if name in headers else text
                yield DownloadResponse(response.status, headers, response.aiter_stream())


async def _resolve(host: str) -> list[str]:
    values = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [str(value[4][0]) for value in values]


async def _safe_url(raw: str, resolve: HostResolver) -> tuple[httpx.URL, tuple[str, ...]]:
    try:
        url = httpx.URL(raw)
        if not url.scheme:
            raise ValueError()
    except ValueError, httpx.InvalidURL:
        raise ValueError("download_url is not a valid URL.") from None
    if url.scheme not in {"http", "https"}:
        raise ValueError("download_url must use http or https.")
    if not url.host:
        raise ValueError("download_url is not a valid URL.")
    if url.username or url.password:
        raise ValueError("download_url must not contain credentials.")
    try:
        ipaddress.ip_address(url.host)
        addresses = [url.host]
    except ValueError:
        try:
            addresses = await resolve(url.host)
        except Exception:
            addresses = []
    if not addresses:
        raise ValueError("download_url host could not be resolved.")
    if any(is_private_address(address) for address in addresses):
        raise ValueError("download_url points to a private or non-public address and was refused.")
    return url, tuple(addresses)


async def download_bounded(
    url: str,
    max_bytes: int,
    *,
    timeout_s: float = 30,
    max_redirects: int = 3,
    resolve: HostResolver | None = None,
    transport: DownloadTransport | None = None,
) -> bytes:
    deadline = asyncio.get_running_loop().time() + timeout_s
    sender = transport or PinnedDownloadTransport()
    try:
        async with asyncio.timeout_at(deadline):
            for hop in range(max_redirects + 1):
                parsed, addresses = await _safe_url(url, resolve or _resolve)
                async with sender.fetch(
                    str(parsed), validated_addresses=addresses, deadline=deadline
                ) as response:
                    if 300 <= response.status < 400:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError(
                                f"Download failed: redirect {response.status} "
                                "without a Location header."
                            )
                        if hop == max_redirects:
                            raise ValueError(
                                f"Download failed: too many redirects (max {max_redirects})."
                            )
                        url = str(parsed.join(location))
                        continue
                    if not 200 <= response.status < 300:
                        raise ValueError(
                            f"Download failed: source responded with HTTP {response.status}."
                        )
                    if response.status in {204, 205}:
                        return b""
                    try:
                        declared = float(response.headers.get("content-length", "0"))
                    except ValueError:
                        declared = 0
                    too_large = (
                        f"Downloaded file exceeds the {max_bytes / (1024 * 1024):g} MB limit."
                    )
                    if math.isfinite(declared) and declared > max_bytes:
                        raise ValueError(too_large)
                    data = bytearray()
                    async for chunk in response.body:
                        if len(data) + len(chunk) > max_bytes:
                            raise ValueError(too_large)
                        data.extend(chunk)
                    return bytes(data)
    except TimeoutError:
        raise ValueError("Download timed out.") from None
    except Exception as error:
        if isinstance(error, ValueError) and str(error).startswith(
            ("Download", "Downloaded", "download_url")
        ):
            raise
        raise ValueError("Download failed: unable to retrieve the source file.") from None
    raise AssertionError("Unreachable download state.")
