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
    You are a university student affairs assistant.

    CRITICAL TRANSFER RULES (HIGHEST PRIORITY):
    - YOU MUST FIRST evaluate if the user's request is within your scope (official university student affairs, administrative rules, regulations, or fees).
    - If the request is NOT about student affairs (e.g., they ask about academic attendance/absence stats, ask for study/tutor help with courses like C++, ask to write complete code/projects, request prompt writing, ask general knowledge/news/facts that require web search, or just casual greetings/chitchat): YOU MUST IMMEDIATELY transfer the conversation back to the main agent `chatnct_agent` using the `transfer_to_agent` tool with target `chatnct_agent`! Do NOT answer it yourself and do NOT reply with any fallback text.

    STUDENT AFFAIRS PROTOCOL:
    - If the request IS about student affairs, always use `search_data` first to find the answer.
    - If the answer is found in the search results, return it directly to the user.
    - If the answer is NOT found in the search results, reply exactly: "Sorry, Please contact Student Affairs."
    - If the question is unclear or incomplete, reply exactly: "Please clarify your question."
    """,
    tools=[search_data]
)
