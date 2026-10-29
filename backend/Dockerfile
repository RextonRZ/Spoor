FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --extra postgres

ENV DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "spoor.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
