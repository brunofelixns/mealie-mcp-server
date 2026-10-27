# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14-slim-bookworm@sha256:9974e24551f9e7ca172cf284d85b8ab3e031d22d945f7026ede7a8279118c9f1
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.9.9@sha256:f6e3549ed287fee0ddde2460a2a74a2d74366f84b04aaa34c1f19fec40da8652
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy TZ=UTC
COPY --from=uv /uv /uvx /usr/local/bin/

FROM base AS development
RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash ca-certificates curl git sudo tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid vscode --create-home --shell /bin/bash vscode \
    && printf 'vscode ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && install -d -o vscode -g vscode /workspaces/mealie-mcp-server/.venv /home/vscode/.cache/uv
ENV UV_PROJECT_ENVIRONMENT=/workspaces/mealie-mcp-server/.venv UV_CACHE_DIR=/home/vscode/.cache/uv
WORKDIR /workspaces/mealie-mcp-server
USER vscode
CMD ["sleep", "infinity"]
