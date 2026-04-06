#agent.py
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .search_tools import search_data
import os

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



