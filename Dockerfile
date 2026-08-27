FROM python:3.12-slim

# ffmpeg renders every cut; the CJK font is required for Japanese drawtext.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY retake/ ./retake/

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
