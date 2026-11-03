# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.14-slim-bookworm@sha256:9974e24551f9e7ca172cf284d85b8ab3e031d22d945f7026ede7a8279118c9f1
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.9.9@sha256:f6e3549ed287fee0ddde2460a2a74a2d74366f84b04aaa34c1f19fec40da8652
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy TZ=UTC
COPY --from=uv /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libicu72 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS development
RUN apt-get update \
    && apt-get install --yes --no-install-recommends bash ca-certificates curl git jq sudo tzdata g++ pkg-config libicu-dev \
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

FROM base AS builder
RUN apt-get update \
    && apt-get install --yes --no-install-recommends g++ pkg-config libicu-dev \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1
WORKDIR /build
ARG TARGETARCH
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-runtime-${TARGETARCH} uv sync --frozen --no-dev --no-install-project
COPY README.md LICENSE ./
COPY src/mealie_mcp_server ./src/mealie_mcp_server
COPY skills ./skills
RUN uv build --wheel --out-dir /dist \
    && uv pip install --python /opt/venv/bin/python --no-deps /dist/*.whl \
    && uv pip check --python /opt/venv/bin/python

FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates tzdata libicu72 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 mcp \
    && useradd --uid 10001 --gid mcp --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin mcp
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/LICENSE /licenses/mealie-mcp-server/LICENSE
RUN python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip /root/.cache
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=UTC HOME=/nonexistent
WORKDIR /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK NONE
ENTRYPOINT ["/opt/venv/bin/mealie-mcp-server"]
CMD []
ARG VCS_REF=unknown
# x-release-please-start-version
LABEL org.opencontainers.image.title="Mealie MCP server" \
      org.opencontainers.image.description="Python MCP server for Mealie: stdio and authenticated Streamable HTTP" \
      org.opencontainers.image.version="0.3.0" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/brunofelixns/mealie-mcp-server" \
      org.opencontainers.image.revision="${VCS_REF}"
# x-release-please-end
