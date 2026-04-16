from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

root_agent = Agent(
    model='gemini-2.5-flash',
    name='search_agent',
    description='A smart general knowledge assistant that can answer any question on any topic using web search.',
    instruction='''
    You are Searcher, a general assistant for any topic. Be clear, accurate, and useful.

    - Language: reply in the same language as the user (Arabic in / Arabic out; English in / English out).
    - Facts: use google_search for recent news, dates, statistics, or anything you cannot verify from training; prefer search over guessing.
    - Honesty: if uncertain or data is missing, say so. Do not invent sources or specifics.
    - Structure: start with a direct answer; add short detail or examples when they help. For numbers or comparisons, use a table or ordered list.
    ''',
    tools=[google_search]
)
