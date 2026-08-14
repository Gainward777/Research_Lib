FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY scripts /app/scripts
RUN pip install --no-cache-dir .

RUN mkdir -p /data/library

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.getenv("PORT", "8000") + "/healthz")'

CMD ["sh", "-c", "exec uvicorn main:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
