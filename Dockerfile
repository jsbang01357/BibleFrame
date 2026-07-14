FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HAYSTACK_TELEMETRY_ENABLED=False \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-service.txt ./
RUN pip install --no-cache-dir -r requirements-service.txt

COPY service ./service
COPY scripts/synthesize_chapter_audio.py ./scripts/synthesize_chapter_audio.py
COPY site ./site
COPY rag ./rag
COPY RIGHTS.md DATA_LICENSE.md LICENSE ./

CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT}"]
