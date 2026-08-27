"""Retake — an AI film crew as an ADK graph workflow.

Each node is a member of the crew and the graph is the call sheet: who works
when, who waits on whom, and who gets to send a shot back.
"""

from __future__ import annotations

from google.adk import Workflow
from google.adk.workflow import START

from .nodes.camera import camera
from .nodes.delivery import abandoned, delivery
from .nodes.director import director
from .nodes.editor import editor
from .nodes.producer import producer
from .nodes.rights import rights_check
from .nodes.screening import screening
from .nodes.storyboard import storyboard

root_agent = Workflow(
    name="retake",
    description=(
        "An AI film crew that plans, shoots, edits and reviews a short film, "
        "and sends its own work back for a retake when it is not good enough."
    ),
    # Rights clearance sits ahead of the shoot rather than beside it: the retake
    # cycle re-enters at the camera, and a join waiting on a branch that no
    # longer runs would stall the graph without raising anything.
    edges=[
        (START, producer),
        (producer, storyboard),
        (storyboard, rights_check),
        (rights_check, camera),
        (camera, editor),
        (editor, director),
        (director, {"RETAKE": camera, "OK": screening}),
        (screening, {"PUBLISH": delivery, "RETAKE": camera, "ABANDON": abandoned}),
    ],
)
