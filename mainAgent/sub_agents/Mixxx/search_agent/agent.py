from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from duckduckgo_search import DDGS
import os


# ── DuckDuckGo Search Tool ──────────────────────────────────────────────
def duckduckgo_search_tool(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo and return the top results.

    Use this tool whenever the user asks about current events, recent news,
    factual data, or anything that benefits from a live web search.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5).

    Returns:
        A dict with a 'status' key and either 'results' (list) or 'error_message'.
    """
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        if not raw_results:
            return {"status": "success", "results": [], "message": "No results found."}

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })

        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


# ── Model ────────────────────────────────────────────────────────────────
# GPT-4o-mini via OpenRouter — supports tool_use (needed for ADK routing).
search_model = LiteLlm(
    model="openrouter/openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

# ── Agent ────────────────────────────────────────────────────────────────
root_agent = Agent(
    model=search_model,
    name='search_agent',
    description='A smart search assistant that can look up anything on the web using DuckDuckGo.',
    instruction='''
    You are Searcher, a web-search assistant. Be clear, accurate, and useful.

    - Tool Usage: ALWAYS use the duckduckgo_search_tool to find up-to-date information before answering.
      Do NOT rely solely on your training data when the user asks about facts, news, people, products, or events.
    - Language: reply in the same language as the user (Arabic in / Arabic out; English in / English out).
    - Cite sources: include the URL from search results when referencing specific info.
    - Honesty: if the search returns no results or you are uncertain, say so. Do not invent sources or specifics.
    - Structure: start with a direct answer; add short detail or examples when they help.
      For numbers or comparisons, use a table or ordered list.
    ''',
    tools=[duckduckgo_search_tool],
)

