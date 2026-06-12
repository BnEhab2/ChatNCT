import sys
import os
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "mainAgent", ".env"))

from server import _run_agent

async def test_agent():
    user_id = "test_user_2"
    prompt = """You are a senior Python game developer with 10+ years of experience building games using Pygame. Your task is to build a complete Snake game in Python. Produce all source files with full implementation code, including a well-organized project folder structure, every file's complete source code, a requirements.txt file that lists all necessary dependencies, and clear instructions on how to run the game. The code should be production-quality, well-commented, and ready to be copied and executed immediately. Ensure the game features include score tracking, increasing speed as the snake grows, and collision detection with walls and itself. Adhere to best practices in coding style and structure, utilizing object-oriented programming principles where appropriate."""

    print("Running _run_agent...")
    # Wrap in try-except to catch any errors
    try:
        response = await _run_agent(user_id, prompt)
        print("\n--- RESPONSE ---")
        # Write response to file to avoid console encoding issues
        with open("scratch/agent_direct_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
        print("Success! Response written to scratch/agent_direct_response.txt")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
