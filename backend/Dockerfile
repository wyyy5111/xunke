FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
# Keep the official Python Package Index as the portable default while allowing
# offline/competition environments to inject an approved mirror at build time:
#   PIP_INDEX_URL=https://... docker compose build backend
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --upgrade pip \
    && python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY backend/app ./app
COPY demo_data ./demo_data

RUN groupadd --system xunkeflow \
    && useradd --system --gid xunkeflow --home-dir /app xunkeflow \
    && mkdir -p /app/data/uploads /app/data/chunks \
    && chown -R xunkeflow:xunkeflow /app/data \
    && chmod -R a-w /app/app /app/demo_data

USER xunkeflow

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
