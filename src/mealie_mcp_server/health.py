"""Process health, without exposing configuration or querying Mealie."""

from starlette.requests import Request
from starlette.responses import JSONResponse


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def readiness(request: Request) -> JSONResponse:
    ready = bool(getattr(request.app.state, "ready", False))
    return JSONResponse(
        {"status": "ok" if ready else "starting"}, status_code=200 if ready else 503
    )
