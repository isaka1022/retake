#!/bin/zsh
# Browser consent for the publishing channel. Pick the target channel when asked.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
CLIENT="$HOME/.secrets/google/client_secret_REDACTED.apps.googleusercontent.com.json"
[ -f "$CLIENT" ] || { echo "client secret not found: $CLIENT"; exit 1; }
PYTHONPATH=. python scripts/youtube_auth.py "$CLIENT"
