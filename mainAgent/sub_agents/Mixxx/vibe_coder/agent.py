from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
import os

gemini_model = LiteLlm(
    model="openrouter/google/gemini-3-flash-lite",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

vibe_coder_agent = Agent(
    model=gemini_model,
    name='vibe_coder_agent',
    description='Professional programming assistant for building software projects, generating clean code, and creating complete applications. Use this agent when the user asks to build, create, or generate any code, website, or software project.',
    instruction='''
    You are a professional programming assistant.
    Always format responses with a project structure section followed by separate file sections.
    Put every code snippet inside triple backticks with the correct language label.
    Never send code as plain text.
    Never mix explanation with code in the same block.
    Use clear section titles and spacing, keep output clean and copy-ready.
    add helpful code comments when useful.
    '''
    )