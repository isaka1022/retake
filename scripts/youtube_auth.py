"""One-off browser consent for the publishing channel.

    python scripts/youtube_auth.py <path-to-client_secret.json>

Pick the channel you want to publish to when the browser asks.
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from retake.services.youtube import SCOPES, TOKEN_PATH


def main(client_secret: str) -> None:
    flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps(
            {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scope": " ".join(creds.scopes or SCOPES),
            },
            indent=2,
        )
    )
    TOKEN_PATH.chmod(0o600)
    print(f"saved: {TOKEN_PATH}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
