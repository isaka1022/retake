#!/bin/zsh
# Builds the ffmpeg-bearing container on Cloud Build and rolls it out.
set -e
cd "$(dirname "$0")/.."
gcloud run deploy retake --source . \
  --project=retake-agentic-2608 --region=us-central1 \
  --allow-unauthenticated \
  --memory=8Gi --cpu=4 --timeout=3600 \
  --min-instances=1 --max-instances=1 --no-cpu-throttling \
  --set-env-vars=RETAKE_BUCKET=retake-artifacts-2608 \
  --set-secrets=GOOGLE_API_KEY=gemini-api-key:latest
