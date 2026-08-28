"""Run the crew from the command line: python scripts/run_local.py "<brief>" """

import asyncio
import sys
import time

from google.adk.runners import InMemoryRunner
from google.genai import types

from retake.agent import root_agent


async def main(brief: str) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="retake")
    session = await runner.session_service.create_session(
        app_name="retake", user_id="local"
    )
    started = time.monotonic()
    async for event in runner.run_async(
        user_id="local",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=brief)]),
    ):
        who = event.author
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    print(f"[{time.monotonic()-started:6.1f}s] {who}: {p.text[:400]}")
                elif p.inline_data:
                    print(
                        f"[{time.monotonic()-started:6.1f}s] {who}: "
                        f"<{p.inline_data.mime_type} {len(p.inline_data.data)} bytes>"
                    )
        if event.error_message:
            print(f"[ERROR] {who}: {event.error_message}")

    final = await runner.session_service.get_session(
        app_name="retake", user_id="local", session_id=session.id
    )
    print("\n=== director's notes ===")
    for r in final.state.get("review_log", []):
        print(f"  take {r['take']}  score {r['score']}  -> {r['verdict']}"
              f"  (accepted={r['accepted']})"
              f"  retakes {r['retakes']}")
        print(f"    {r['comment']}")
    print("\n=== delivery ===")
    print(final.state.get("delivery"))
    print("failed cuts:", final.state.get("failed_cuts"))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "A 30-second film on sacred water sites"))
