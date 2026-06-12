import sys
import os
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "mainAgent", ".env"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mainAgent.agent import root_agent

async def test_agent():
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="chatnct_test",
        session_service=session_service,
    )
    
    user_id = "test_user"
    session = session_service.create_session(app_name="chatnct_test", user_id=user_id)
    if asyncio.iscoroutine(session):
        session = await session
        
    prompt = """[STUDENT_CODE: 20220300]
[STUDENT_NAME: Test Student]
[USER_ROLE: student]
You are a senior Python game developer with 10+ years of experience building games using Pygame. Your task is to build a complete Snake game in Python. Produce all source files with full implementation code, including a well-organized project folder structure, every file's complete source code, a requirements.txt file that lists all necessary dependencies, and clear instructions on how to run the game. The code should be production-quality, well-commented, and ready to be copied and executed immediately. Ensure the game features include score tracking, increasing speed as the snake grows, and collision detection with walls and itself. Adhere to best practices in coding style and structure, utilizing object-oriented programming principles where appropriate."""

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    print("Sending prompt to root_agent...")
    response_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"Part text: {part.text}")
                    response_parts.append(part.text)
                if hasattr(part, "function_call") and part.function_call:
                    print(f"Tool call: {part.function_call.name} with args {part.function_call.args}")

    print("\n--- FINAL RESPONSE ---")
    print("\n".join(response_parts))

if __name__ == "__main__":
    asyncio.run(test_agent())
