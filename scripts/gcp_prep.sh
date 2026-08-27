#!/bin/zsh
# One-time GCP setup. The API key is piped from the environment and never printed.
set -e
P=retake-agentic-2608
B=retake-artifacts-2608
REGION=us-central1

if [ -z "$GOOGLE_API_KEY" ]; then echo "GOOGLE_API_KEY is not set"; exit 1; fi

gcloud storage buckets create "gs://$B" --location=$REGION --project=$P 2>/dev/null \
  || echo "bucket already exists"

NUM=$(gcloud projects describe $P --format='value(projectNumber)')
SA="${NUM}-compute@developer.gserviceaccount.com"

printf '%s' "$GOOGLE_API_KEY" | gcloud secrets create gemini-api-key --data-file=- --project=$P 2>/dev/null \
  || printf '%s' "$GOOGLE_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project=$P >/dev/null

gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor --project=$P >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$B" \
  --member="serviceAccount:$SA" --role=roles/storage.objectAdmin >/dev/null

echo "prep ok  bucket=$B  sa=$SA"
