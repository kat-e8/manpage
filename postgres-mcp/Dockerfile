FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
COPY *.py ./

# src/ must be copied in before this -- hatchling's editable-install build
# scans the source tree to auto-detect the package (by directory name
# matching the project name), and fails metadata generation if src/ isn't
# there yet.
RUN pip install --no-cache-dir -e .

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# No -f: streamable-http's /mcp route 406s a plain GET (it needs an
# `Accept: application/json, text/event-stream` header per the MCP spec,
# and a bare GET still isn't a full protocol handshake) -- -f would turn
# that expected 4xx into a permanent healthcheck failure. Any HTTP response
# at all proves the process is alive and routing, which is all this checks.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sS -o /dev/null -H "Accept: application/json, text/event-stream" http://localhost:8000/mcp || exit 1

CMD ["python", "mcp_server.py", "--host", "0.0.0.0", "--port", "8000"]
