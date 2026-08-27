"""Gemini calls, kept free of any ADK import.

Every crew member that has to think talks to Gemini through here, so the graph
can be debugged separately from the model layer.
"""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

MODEL = os.environ.get("RETAKE_MODEL", "gemini-3.5-flash")

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


async def structured(
    prompt: str,
    schema: dict[str, Any],
    *,
    system: str | None = None,
    model: str | None = None,
) -> Any:
    """Ask for JSON matching `schema` and return it parsed."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        system_instruction=system,
    )
    resp = await client().aio.models.generate_content(
        model=model or MODEL, contents=prompt, config=config
    )
    return json.loads(resp.text)


async def text(prompt: str, *, system: str | None = None, model: str | None = None) -> str:
    resp = await client().aio.models.generate_content(
        model=model or MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    return (resp.text or "").strip()


async def structured_video(
    video: bytes,
    prompt: str,
    schema: dict[str, Any],
    *,
    system: str | None = None,
    model: str | None = None,
) -> Any:
    """Let a crew member actually watch a cut rather than read a description."""
    resp = await client().aio.models.generate_content(
        model=model or MODEL,
        contents=types.Content(
            role="user",
            parts=[
                types.Part(inline_data=types.Blob(data=video, mime_type="video/mp4")),
                types.Part(text=prompt),
            ],
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system,
        ),
    )
    return json.loads(resp.text)
