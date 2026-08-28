#!/bin/zsh
# Browser consent for the publishing channel. Pick the target channel when asked.
# Point RETAKE_YT_CLIENT at the OAuth client JSON downloaded from Google Cloud
# Console; the default matches a single client file kept outside the repo.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
CLIENT="${RETAKE_YT_CLIENT:-$(ls "$HOME"/.secrets/google/client_secret_*.json 2>/dev/null | head -1)}"
[ -n "$CLIENT" ] && [ -f "$CLIENT" ] || {
  echo "OAuth client JSON not found. Set RETAKE_YT_CLIENT to its path." >&2
  exit 1
}
PYTHONPATH=. python scripts/youtube_auth.py "$CLIENT"
