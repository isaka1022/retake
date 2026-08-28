"""Cloud Run entrypoint.

Uses a hand-written container rather than `adk deploy cloud_run` because the
generated image has no ffmpeg, and because it strips the dev server the crew's
trace view depends on.
"""

import mimetypes
import os
from pathlib import Path
from types import SimpleNamespace

import graphviz

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from google.adk import Workflow
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils import graph_visualization

from retake.services import storage

PIPELINE_HTML = Path(__file__).resolve().parent / "retake" / "static" / "pipeline.html"


class _PipelineDigraph(graphviz.Digraph):
    """Lay the crew out left to right. ADK's workflow renderer omits rankdir,
    so a ten-node pipeline stacks into a column that reads as a log."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph_attr["rankdir"] = "LR"


graph_visualization.graphviz = SimpleNamespace(Digraph=_PipelineDigraph)

# ADK 2.8.0 reads `agent._graph` when drawing the graph for a single event,
# but Workflow exposes it as `graph`, so every per-event graph returns 500.
if not hasattr(Workflow, "_graph"):
    Workflow._graph = property(lambda self: self.graph)

# Without a backing store ADK keeps sessions in memory on Cloud Run, so a
# restart loses any reel waiting at the screening gate.
SESSION_URI = os.environ.get("RETAKE_SESSION_URI") or None

app = get_fast_api_app(
    agents_dir=str(Path(__file__).resolve().parent),
    session_service_uri=SESSION_URI,
    web=True,
)


@app.get("/artifacts/{key:path}")
async def artifact(key: str) -> StreamingResponse:
    """Serve rendered output. The app owns access rather than a public bucket."""
    if ".." in key:
        raise HTTPException(status_code=400, detail="bad key")
    if await storage.size(key) is None:
        raise HTTPException(status_code=404, detail="not found")
    # Deliberately no Content-Length: it forces a buffered response, and Cloud
    # Run rejects one over 32MB even though the app returned it fine.
    return StreamingResponse(
        storage.stream(key),
        media_type=mimetypes.guess_type(key)[0] or "application/octet-stream",
    )


@app.get("/pipeline")
async def pipeline() -> FileResponse:
    """Live pipeline monitor. Polls ADK's public session REST endpoints from
    the browser rather than touching any ADK internals."""
    return FileResponse(PIPELINE_HTML, media_type="text/html")
