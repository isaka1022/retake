"""Drive the screening gate end to end: run until it interrupts, then answer.

Usage: python scripts/test_hitl.py "<brief>" [publish|retake|abandon]
"""

import asyncio
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from retake.agent import root_agent

REQUEST_INPUT = "adk_request_input"


def find_request(event) -> tuple[str, str] | None:
    if not (event.content and event.content.parts):
        return None
    for p in event.content.parts:
        fc = p.function_call
        if fc and fc.name == REQUEST_INPUT:
            return fc.id, (fc.args or {}).get("message", "")
    return None


async def main(brief: str, decision: str) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="retake")
    session = await runner.session_service.create_session(
        app_name="retake", user_id="local"
    )
    kwargs = dict(user_id="local", session_id=session.id)

    pending = None
    async for event in runner.run_async(
        **kwargs, new_message=types.Content(role="user", parts=[types.Part(text=brief)])
    ):
        found = find_request(event)
        if found:
            pending = found
        if event.error_message:
            print("[ERROR]", event.author, event.error_message)

    if not pending:
        print("Did not stop at screening (no interrupt was raised)")
        return

    interrupt_id, message = pending
    print("=== stopped at screening ===")
    print(message)
    print(f"\n--- human decision: {decision} ---\n")

    reply = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=interrupt_id,
                    name=REQUEST_INPUT,
                    response={"decision": decision, "note": "Screening result"},
                )
            )
        ],
    )
    async for event in runner.run_async(**kwargs, new_message=reply):
        if event.error_message:
            print("[ERROR]", event.author, event.error_message)

    final = await runner.session_service.get_session(
        app_name="retake", user_id="local", session_id=session.id
    )
    print("Decision after resume:", final.state.get("screening"))
    print("delivery:", final.state.get("delivery"))


if __name__ == "__main__":
    asyncio.run(
        main(
            sys.argv[1] if len(sys.argv) > 1 else "A 30-second film on sacred water and waterfall sites",
            sys.argv[2] if len(sys.argv) > 2 else "publish",
        )
    )
