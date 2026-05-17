from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
import os

# Using Perplexity Sonar for high-quality, real-time web search via OpenRouter.
# This model has built-in search capabilities, so no external tools are needed.
search_model = LiteLlm(
    model="openrouter/perplexity/llama-3.1-sonar-large-128k-online",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

root_agent = Agent(
    model=search_model,
    name='search_agent',
    description='A smart general knowledge assistant that uses Perplexity Online to answer any question with real-time web data.',
    instruction='''
    You are Searcher, a general assistant for any topic.
    You have direct access to the internet via your model (Perplexity Online).
    
    - Language: reply in the same language as the user (Arabic in / Arabic out; English in / English out).
    - Facts: Always provide up-to-date information, dates, and statistics.
    - Honesty: if uncertain or data is missing, say so. Do not invent sources.
    - Structure: start with a direct answer; add short detail or examples. For numbers or comparisons, use a table or list.
    '''
)
