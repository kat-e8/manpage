FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

# docker_executor.py / python-on-whales shell out to `docker` on PATH -- this
# server manages containers on the *host* Docker daemon (docker-outside-of-
# docker), not a daemon of its own, so only the CLI binary is needed here.
# Copied from the official CLI image rather than pulled via apt so the image
# doesn't need Docker's apt/gpg repo just for one binary.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8008
CMD ["docker-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8008"]
