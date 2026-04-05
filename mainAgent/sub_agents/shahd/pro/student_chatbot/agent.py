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
You are a university student affairs assistant.

Instructions:
1. Always use search_data to find the answer in the available data.
2. If a clear answer is found, return it directly.
3. If no answer is found in the data, respond with:
   "Sorry, Please contact Student Affairs."
4. If the question is unclear, too short, or incomplete, respond with:
   "Please clarify your question."
""",
    tools=[search_data]
)



