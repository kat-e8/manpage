FROM python:3.12-slim

# Otherwise stdout is fully buffered when not attached to a TTY, and
# `docker logs` shows nothing until the buffer happens to flush -- verified
# against this container: sync succeeded (608 rows written, confirmed via
# sync_runs) while `docker logs` showed zero output the whole time.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest.py watcher.py ./

CMD ["python", "watcher.py"]
