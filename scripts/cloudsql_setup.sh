#!/bin/zsh
# Database, user and connection secret for session persistence.
# The password is generated here, stored in Secret Manager and never printed.
set -e
P=retake-agentic-2608
REGION=us-central1
INSTANCE=retake-sessions
DB=adk
DBUSER=retake
CONN="$P:$REGION:$INSTANCE"

gcloud sql databases create "$DB" --instance="$INSTANCE" --project=$P 2>/dev/null \
  || echo "database already exists"

# Hex only: the password goes into a URI and would otherwise need escaping.
PW=$(openssl rand -hex 24)
gcloud sql users create "$DBUSER" --instance="$INSTANCE" --password="$PW" --project=$P 2>/dev/null \
  || gcloud sql users set-password "$DBUSER" --instance="$INSTANCE" --password="$PW" --project=$P

# ADK builds an async engine, so the driver has to be an async one.
URI="postgresql+asyncpg://$DBUSER:$PW@/$DB?host=/cloudsql/$CONN"
printf '%s' "$URI" | gcloud secrets create session-uri --data-file=- --project=$P 2>/dev/null \
  || printf '%s' "$URI" | gcloud secrets versions add session-uri --data-file=- --project=$P >/dev/null

NUM=$(gcloud projects describe $P --format='value(projectNumber)')
SA="${NUM}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding session-uri \
  --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor --project=$P >/dev/null
gcloud projects add-iam-policy-binding $P \
  --member="serviceAccount:$SA" --role=roles/cloudsql.client >/dev/null

echo "cloudsql ok  instance=$CONN  db=$DB  user=$DBUSER"
