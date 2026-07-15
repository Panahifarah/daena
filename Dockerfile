FROM python:3.13-slim AS builder

RUN pip install uv --no-cache-dir

WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-dev --frozen

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    liblmdb0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r daena && useradd -r -g daena -d /var/lib/daena daena

COPY --from=builder /app /app
COPY src/ /app/src/
COPY proto/ /app/proto/

ENV PATH="/app/.venv/bin:$PATH" \
    DAENA_CONFIG_PATH=/etc/daena/daena.yaml

EXPOSE 8642

USER daena
ENTRYPOINT ["daena-serve"]
