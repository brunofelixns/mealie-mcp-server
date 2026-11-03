"""Bounded, credential-scoped asynchronous access to Mealie."""

import asyncio
import json as jsonlib
import logging
import math
from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from types import TracebackType
from typing import NoReturn, Self, cast
from urllib.parse import quote, urlencode

import anyio
import httpx2 as httpx
from pydantic import JsonValue

from mealie_mcp_server.config import Settings
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.common import UNSET, UnsetType
from mealie_mcp_server.support.strings import trim

type ParamScalar = str | int | float | bool
type ParamValue = ParamScalar | list[str] | None | UnsetType
type MultipartFiles = (
    Mapping[str, tuple[str, bytes, str]]
    | Sequence[tuple[str, tuple[str | None, bytes | str, str | None]]]
)
logger = logging.getLogger(__name__)


def encode_path_segment(value: str, label: str = "path segment") -> str:
    trimmed = trim(value) if isinstance(value, str) else ""
    if not trimmed or trimmed in {".", ".."} or "/" in trimmed or "\\" in trimmed:
        raise ValueError(f"Invalid {label}.")
    return quote(trimmed, safe="~!*'()")


def scalar_string(value: ParamScalar) -> str:
    """ECMAScript-compatible JSON scalar text used in queries and compact projections."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Query numbers must be finite.")
        if value == 0:
            return "0"
        if 1e-6 <= abs(value) < 1e21:
            text = format(Decimal(repr(value)), "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        return repr(value).replace("e-0", "e-").replace("e+0", "e+")
    return str(value)


def format_params(params: Mapping[str, ParamValue]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in params.items():
        if value is None or isinstance(value, UnsetType):
            continue
        if isinstance(value, list):
            if value:
                result[key] = ",".join(value)
        else:
            result[key] = scalar_string(value)
    return result


def build_query_string(params: Mapping[str, ParamValue]) -> str:
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None or isinstance(value, UnsetType):
            continue
        if isinstance(value, list):
            pairs.extend((key, item) for item in value)
        else:
            pairs.append((key, scalar_string(value)))
    return urlencode(pairs)


def _origin(url: httpx.URL) -> tuple[str, str, int]:
    return url.scheme, url.host, url.port or (443 if url.scheme == "https" else 80)


def _reject_non_json_constant(value: str) -> NoReturn:
    raise ValueError("Mealie returned a non-JSON numeric constant.")


@dataclass(frozen=True)
class BinaryResponse:
    content: bytes
    content_type: str
    content_disposition: str | None


@dataclass(frozen=True)
class SSEEvent:
    event: str
    data: JsonValue


class MealieClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._origin = _origin(httpx.URL(settings.mealie_base_url))
        self.self_user_id_task: asyncio.Task[str] | None = None

    async def __aenter__(self) -> Self:
        if self._http is not None:
            raise RuntimeError("MealieClient is already open.")
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.settings.mealie_api_key.get_secret_value()}"},
            verify=True,
            transport=self._transport,
            timeout=httpx.Timeout(connect=5, read=30, write=30, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
            follow_redirects=True,
            max_redirects=20,
            event_hooks={"response": [self._guard_redirect]},
        )
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._http is not None:
            try:
                with anyio.move_on_after(5, shield=True) as cleanup:
                    cached, self.self_user_id_task = self.self_user_id_task, None
                    if cached is not None and not cached.done():
                        cached.cancel()
                        await asyncio.gather(cached, return_exceptions=True)
                    await self._http.aclose()
                if cleanup.cancel_called:
                    logger.warning("Mealie client cleanup timed out.")
                else:
                    logger.debug("Mealie client closed")
            finally:
                self._http = None

    async def _guard_redirect(self, response: httpx.Response) -> None:
        if response.is_redirect and response.headers.get("location"):
            target = response.request.url.join(response.headers["location"])
            if _origin(target) != self._origin or target.username or target.password:
                raise MealieApiError(
                    response.status_code, "Mealie redirected outside its configured origin."
                )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str]] | None = None,
        json: JsonValue | UnsetType = UNSET,
        data: Mapping[str, str] | None = None,
        files: MultipartFiles | None = None,
    ) -> JsonValue:
        if self._http is None:
            raise RuntimeError("Use MealieClient inside its async context manager.")
        if not path.startswith("/api/") or path.startswith("//"):
            raise ValueError("Mealie endpoints must be relative /api/ paths.")
        if not isinstance(json, UnsetType) and (data is not None or files is not None):
            raise ValueError("JSON and multipart bodies cannot be combined.")
        content = None
        if not isinstance(json, UnsetType):
            content = jsonlib.dumps(
                json, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
        headers = {"Content-Type": "application/json"} if files is None else None
        started = monotonic()
        try:
            response = await self._http.request(
                method,
                self.settings.mealie_base_url + path,
                params=tuple(params) if params is not None else None,
                content=content,
                data=data,
                files=files,
                headers=headers,
            )
        except httpx.TimeoutException:
            suffix = (
                " Write outcome may be unknown." if method.upper() not in {"GET", "HEAD"} else ""
            )
            raise MealieTransportError("Mealie request timed out." + suffix) from None
        except httpx.RequestError:
            raise MealieTransportError("Mealie request failed.") from None
        finally:
            if self.settings.debug:
                logger.debug("Mealie HTTP %s: %.1f ms", method, (monotonic() - started) * 1000)
        if not 200 <= response.status_code < 300:
            raise MealieApiError(
                response.status_code,
                f"Mealie API error {response.status_code}.",
                body=response.text,
            )
        if response.status_code == 204:
            return None
        try:
            return cast(
                JsonValue, jsonlib.loads(response.content, parse_constant=_reject_non_json_constant)
            )
        except ValueError, UnicodeError:
            raise MealieTransportError("Mealie returned invalid JSON.") from None

    async def stream_events(
        self,
        path: str,
        *,
        json: JsonValue | UnsetType = UNSET,
        files: MultipartFiles | None = None,
        max_bytes: int = 2 * 1024 * 1024,
        max_events: int = 2048,
        max_line_bytes: int = 64 * 1024,
    ) -> AsyncGenerator[SSEEvent]:
        """Consume one native POST stream, with no redirect, reconnect or write replay.

        Bound raw bytes before decoding and bound each line even when a peer never
        sends a delimiter. SSE ids/retry fields are deliberately never acted upon.
        """
        if self._http is None:
            raise RuntimeError("Use MealieClient inside its async context manager.")
        if not path.startswith("/api/") or path.startswith("//"):
            raise ValueError("Mealie endpoints must be relative /api/ paths.")
        if min(max_bytes, max_events, max_line_bytes) <= 0:
            raise ValueError("SSE limits must be positive.")
        if not isinstance(json, UnsetType) and files is not None:
            raise ValueError("JSON and multipart bodies cannot be combined.")
        content = None
        headers = {"Accept": "text/event-stream", "Accept-Encoding": "identity"}
        if not isinstance(json, UnsetType):
            content = jsonlib.dumps(json, ensure_ascii=False, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        event_name = "message"
        data: list[bytes] = []
        line = bytearray()
        total = 0
        events = 0
        skip_lf = False
        unknown = " Write outcome may be unknown; inspect recipes before another import."

        def consume_line() -> SSEEvent | None:
            nonlocal event_name, events
            value = bytes(line)
            line.clear()
            if not value:
                if not data:
                    event_name = "message"
                    return None
                events += 1
                if events > max_events:
                    raise MealieTransportError("Mealie SSE event limit exceeded." + unknown)
                try:
                    decoded = cast(
                        JsonValue,
                        jsonlib.loads(b"\n".join(data), parse_constant=_reject_non_json_constant),
                    )
                    name = event_name
                except ValueError, UnicodeError:
                    raise MealieTransportError(
                        "Mealie returned invalid SSE data." + unknown
                    ) from None
                data.clear()
                event_name = "message"
                return SSEEvent(name, decoded)
            if value.startswith(b":"):
                return None
            field, _, field_value = value.partition(b":")
            if field_value.startswith(b" "):
                field_value = field_value[1:]
            if field == b"data":
                data.append(field_value)
            elif field == b"event":
                try:
                    event_name = field_value.decode("utf-8")
                except UnicodeError:
                    raise MealieTransportError(
                        "Mealie returned invalid SSE data." + unknown
                    ) from None
            return None

        try:
            async with (
                asyncio.timeout(300),
                self._http.stream(
                    "POST",
                    self.settings.mealie_base_url + path,
                    content=content,
                    files=files,
                    headers=headers,
                    follow_redirects=False,
                ) as response,
            ):
                if not 200 <= response.status_code < 300:
                    raise MealieApiError(
                        response.status_code, f"Mealie API error {response.status_code}."
                    )
                if (
                    response.headers.get("content-type", "").split(";", 1)[0].lower()
                    != "text/event-stream"
                ):
                    raise MealieTransportError("Mealie did not return an SSE stream." + unknown)
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise MealieTransportError(
                        "Mealie returned unsupported SSE encoding." + unknown
                    )
                async for chunk in response.aiter_raw():
                    total += len(chunk)
                    if total > max_bytes:
                        raise MealieTransportError("Mealie SSE byte limit exceeded." + unknown)
                    for byte in chunk:
                        if skip_lf and byte == 10:
                            skip_lf = False
                            continue
                        skip_lf = byte == 13
                        if byte in {10, 13}:
                            event = consume_line()
                            if event is not None:
                                yield event
                        else:
                            if len(line) >= max_line_bytes:
                                raise MealieTransportError(
                                    "Mealie SSE line limit exceeded." + unknown
                                )
                            line.append(byte)
                # An unterminated final event is discarded, per SSE framing. The
                # service requires an explicit done event before claiming success.
        except httpx.TimeoutException, TimeoutError:
            raise MealieTransportError("Mealie stream timed out." + unknown) from None
        except httpx.RequestError:
            raise MealieTransportError("Mealie stream failed." + unknown) from None

    async def get_binary(
        self,
        path: str,
        *,
        params: list[tuple[str, str]] | None = None,
        max_bytes: int = 20 * 1024 * 1024,
    ) -> BinaryResponse:
        """Download from the configured origin without buffering an unbounded response."""
        if self._http is None:
            raise RuntimeError("Use MealieClient inside its async context manager.")
        if not path.startswith("/api/") or path.startswith("//"):
            raise ValueError("Mealie endpoints must be relative /api/ paths.")
        if max_bytes <= 0:
            raise ValueError("Binary size limit must be positive.")
        target = httpx.URL(self.settings.mealie_base_url + path)
        query = tuple(params) if params is not None else None
        try:
            # HTTPX automatic redirects buffer intermediate bodies. Close each redirect
            # without reading it, and scope credentials to the configured origin.
            for redirect_count in range(21):
                async with self._http.stream(
                    "GET",
                    target,
                    headers={"Accept-Encoding": "identity"},
                    params=query,
                    follow_redirects=False,
                ) as response:
                    if response.is_redirect and response.headers.get("location"):
                        target = response.request.url.join(response.headers["location"])
                        if _origin(target) != self._origin or target.username or target.password:
                            raise MealieApiError(
                                response.status_code,
                                "Mealie redirected outside its configured origin.",
                            )
                        if redirect_count == 20:
                            raise MealieTransportError(
                                "Mealie download exceeded the redirect limit."
                            )
                        query = None
                        continue
                    if not 200 <= response.status_code < 300:
                        raise MealieApiError(
                            response.status_code, f"Mealie API error {response.status_code}."
                        )
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise MealieTransportError(
                            "Mealie returned unsupported binary content encoding."
                        )
                    length = response.headers.get("content-length")
                    if length is not None:
                        try:
                            size = int(length)
                        except ValueError:
                            raise MealieTransportError(
                                "Mealie returned invalid content length."
                            ) from None
                        if size < 0 or size > max_bytes:
                            raise MealieTransportError(
                                "Mealie binary response exceeds the size limit."
                            )
                    data = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if len(data) + len(chunk) > max_bytes:
                            raise MealieTransportError(
                                "Mealie binary response exceeds the size limit."
                            )
                        data.extend(chunk)
                    return BinaryResponse(
                        bytes(data),
                        response.headers.get("content-type", "application/octet-stream").split(
                            ";", 1
                        )[0],
                        response.headers.get("content-disposition"),
                    )
            raise MealieTransportError("Mealie download exceeded the redirect limit.")
        except httpx.TimeoutException:
            raise MealieTransportError("Mealie download timed out.") from None
        except httpx.RequestError:
            raise MealieTransportError("Mealie download failed.") from None
