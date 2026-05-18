import os
from pathlib import Path
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .tools import search_data
from dotenv import load_dotenv

# Load .env from project root in a location-independent way.
_ROOT_DIR = Path(__file__).resolve().parents[3]
_env_path = _ROOT_DIR / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

llm = LiteLlm(
    model="openrouter/openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

root_agent = LlmAgent(
    name="student_chatbot",
    model=llm,
    description="University Student Affairs Chatbot",
    instruction="""
    You are a university student affairs assistant. Always use search_data first. If the answer is found, return it directly. If not found, reply exactly: "Sorry, Please contact Student Affairs." If the question is unclear or incomplete, reply exactly: "Please clarify your question."
    """,
    tools=[search_data]
)



