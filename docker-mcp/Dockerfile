FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

# docker_executor.py / python-on-whales shell out to `docker` on PATH -- this
# server manages containers on the *host* Docker daemon (docker-outside-of-
# docker), not a daemon of its own, so only the CLI binary is needed here.
# Copied from the official CLI image rather than pulled via apt so the image
# doesn't need Docker's apt/gpg repo just for one binary.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

# openssh-client: docker_executor.py / python-on-whales pass docker_host
# straight to the `docker` CLI's -H flag, which shells out to a system `ssh`
# for ssh:// targets (remote engines, e.g. other tailnet nodes) -- not needed
# for the local socket-mounted default engine, only for per-call overrides.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Private key and known_hosts are bind-mounted in by docker-compose.yml (host
# secrets, never baked into the image) -- this config just tells ssh where to
# find them. StrictHostKeyChecking is deliberately "yes": known_hosts is
# pre-populated from the host's own already-verified entries, not built up
# via trust-on-first-connect inside the container.
RUN mkdir -p /root/.ssh/control && chmod 700 /root/.ssh /root/.ssh/control
COPY ssh_config /root/.ssh/config
RUN chmod 600 /root/.ssh/config

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8008
CMD ["docker-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8008"]
