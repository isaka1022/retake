"""Publishing.

This is the only step that reaches outside the building, which is why nothing
gets here without a person having watched the reel and said yes.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path(
    os.environ.get("RETAKE_YOUTUBE_TOKEN", Path.home() / ".secrets/google/youtube/tokens-retake.json")
)

# Travel & Events. The films are location documentaries.
CATEGORY_ID = "19"


class NotConfigured(RuntimeError):
    pass


def configured() -> bool:
    return TOKEN_PATH.is_file()


def _credentials() -> Credentials:
    if not configured():
        raise NotConfigured(
            f"YouTube の認証情報がありません: {TOKEN_PATH}\n"
            "scripts/youtube_auth.py を実行してください"
        )
    data = json.loads(TOKEN_PATH.read_text())
    return Credentials(
        token=data.get("access_token") or data.get("token"),
        refresh_token=data["refresh_token"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def _upload(
    path: str, title: str, description: str, tags: list[str], privacy: str
) -> dict[str, Any]:
    youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:20],
                "categoryId": CATEGORY_ID,
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        },
        media_body=MediaFileUpload(path, chunksize=-1, resumable=True),
    )
    response = request.execute()
    return {
        "video_id": response["id"],
        "url": f"https://www.youtube.com/watch?v={response['id']}",
        "privacy": privacy,
    }


async def publish(
    path: Path | str,
    *,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy: str = "unlisted",
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _upload, str(path), title, description, tags or [], privacy
    )
