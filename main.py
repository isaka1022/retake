"""Cloud Run entrypoint.

Uses a hand-written container rather than `adk deploy cloud_run` because the
generated image has no ffmpeg, and because it strips the dev server the crew's
trace view depends on.
"""

import mimetypes
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from google.adk.cli.fast_api import get_fast_api_app

from retake.services import storage

app = get_fast_api_app(
    agents_dir=str(Path(__file__).resolve().parent),
    web=True,
)


@app.get("/artifacts/{key:path}")
async def artifact(key: str) -> StreamingResponse:
    """Serve rendered output. The app owns access rather than a public bucket."""
    if ".." in key:
        raise HTTPException(status_code=400, detail="bad key")
    length = await storage.size(key)
    if length is None:
        raise HTTPException(status_code=404, detail="not found")
    return StreamingResponse(
        storage.stream(key),
        media_type=mimetypes.guess_type(key)[0] or "application/octet-stream",
        headers={"Content-Length": str(length)},
    )
