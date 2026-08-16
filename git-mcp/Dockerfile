FROM python:3.11-slim

# No local git binary needed -- every operation goes over ssh to a target
# host, which has its own git already (this container never runs git
# directly against its own filesystem). openssh-client is the ssh transport;
# gcc is needed to build wheels for this image's own dependencies; curl is
# for the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Private key and known_hosts are bind-mounted in by docker-compose.yml
# (host secrets, never baked into the image) -- this config just tells ssh
# where to find them. StrictHostKeyChecking is deliberately "yes": known_hosts
# is pre-populated from the host's own already-verified entries, not built up
# via trust-on-first-connect inside the container.
RUN mkdir -p /root/.ssh/control && chmod 700 /root/.ssh /root/.ssh/control
COPY ssh_config /root/.ssh/config
RUN chmod 600 /root/.ssh/config

WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
COPY *.py ./

# src/ must be copied in before this -- hatchling's editable-install build
# scans the source tree to auto-detect the package (by directory name
# matching the project name), and fails metadata generation if src/ isn't
# there yet.
RUN pip install --no-cache-dir -e .

EXPOSE 8010

# No -f: streamable-http's /mcp route 406s a plain GET (it needs an
# `Accept: application/json, text/event-stream` header per the MCP spec) --
# -f would turn that expected 4xx into a permanent healthcheck failure. Any
# HTTP response at all proves the process is alive and routing.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sS -o /dev/null -H "Accept: application/json, text/event-stream" http://localhost:8010/mcp || exit 1

CMD ["python", "mcp_server.py", "--host", "0.0.0.0", "--port", "8010"]
