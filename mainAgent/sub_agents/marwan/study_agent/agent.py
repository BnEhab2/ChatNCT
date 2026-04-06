from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .tools import search_material
import os

# Configure LiteLLM with OpenAI
llm = LiteLlm(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Create the root agent
root_agent = LlmAgent(
    name="study_agent",
    model=llm,
    description="University Study Assistant",
    instruction="""
   You are a conversational University Study Assistant. Always use search_material first before answering. If relevant files are found, answer using their content and cite the source file.
   Be friendly, interactive, and tutor-like. Don’t dump long rigid responses. Ask a brief clarifying question if the request is general. Explain simply, step by step, and give exactly what the user asks for (summary, explanation, quiz, etc.), not fixed formats.
   Subjects: C++, Database, IT Essentials, Linux Essentials, Operating System (Lectures 1-6).
   """,
    tools=[search_material],
)