"""Bounded, credential-scoped asynchronous access to Mealie."""

import json as jsonlib
import math
from collections.abc import Mapping
from decimal import Decimal
from types import TracebackType
from typing import NoReturn, Self, cast
from urllib.parse import quote, urlencode

import httpx2 as httpx
from pydantic import JsonValue

from mealie_mcp_server.config import Settings
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.common import UNSET, UnsetType

type ParamScalar = str | int | float | bool
type ParamValue = ParamScalar | list[str] | None | UnsetType


def encode_path_segment(value: str, label: str = "path segment") -> str:
    trimmed = value.strip() if isinstance(value, str) else ""
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


class MealieClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._origin = _origin(httpx.URL(settings.mealie_base_url))

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
                await self._http.aclose()
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
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
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
