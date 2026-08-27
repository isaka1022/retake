"""Retake — an AI film crew as an ADK graph workflow.

Each node is a member of the crew. The graph is the call sheet: who works when,
who waits on whom, and who gets to send a shot back.
"""

from __future__ import annotations

from google.adk import Workflow
from google.adk.workflow import START

from .nodes.camera import camera
from .nodes.editor import editor
from .nodes.producer import producer
from .nodes.storyboard import storyboard

root_agent = Workflow(
    name="retake",
    description=(
        "An AI film crew that plans, shoots, edits and reviews a short film, "
        "and sends its own work back for a retake when it is not good enough."
    ),
    edges=[
        (START, producer),
        (producer, storyboard),
        (storyboard, camera),
        (camera, editor),
    ],
)
