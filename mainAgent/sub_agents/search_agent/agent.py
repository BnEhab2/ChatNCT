import os

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools import duckduckgo_search_tool


search_model = LiteLlm(
    model="openrouter/openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)


root_agent = Agent(
    model=search_model,
    name="search_agent",
    description="A smart search assistant that can look up anything on the web using DuckDuckGo.",
    instruction="""
    You are Searcher, a web-search assistant. Be clear, accurate, and useful.

    - Tool Usage: ALWAYS use the duckduckgo_search_tool to find up-to-date information before answering.
      Do NOT rely solely on your training data when the user asks about facts, news, people, products, or events.
    - Language: reply in the same language as the user (Arabic in / Arabic out; English in / English out).
    - Cite sources: include the URL from search results when referencing specific info.
    - Honesty: if the search returns no results or you are uncertain, say so. Do not invent sources or specifics.
    - Structure: start with a direct answer; add short detail or examples when they help.
      For numbers or comparisons, use a table or ordered list.
    """,
    tools=[duckduckgo_search_tool],
)
