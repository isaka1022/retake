#!/bin/zsh
# Builds the ffmpeg-bearing container on Cloud Build and rolls it out.
set -e
cd "$(dirname "$0")/.."
gcloud run deploy retake --source . \
  --project=retake-agentic-2608 --region=us-central1 \
  --allow-unauthenticated \
  --memory=8Gi --cpu=4 --timeout=3600 \
  --min-instances=1 --max-instances=1 --no-cpu-throttling \
  --add-cloudsql-instances=retake-agentic-2608:us-central1:retake-sessions \
  --set-env-vars=RETAKE_BUCKET=retake-artifacts-2608,RETAKE_PUBLIC_URL=https://retake-4lycxzkhja-uc.a.run.app \
  --set-secrets=GOOGLE_API_KEY=gemini-api-key:latest,RETAKE_SESSION_URI=session-uri:latest
