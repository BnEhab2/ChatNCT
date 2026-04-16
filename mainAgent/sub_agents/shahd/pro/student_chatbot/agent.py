import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .search_tools import search_data
from dotenv import load_dotenv

# Load .env from project root
_ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
_env_path = os.path.join(_ROOT_DIR, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)
else:
    load_dotenv()

llm = LiteLlm(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY")
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



