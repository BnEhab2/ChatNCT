from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
import os
from .tools import generate_project_blueprint, generate_code_files, debug_code_issue

vibe_coder_model = LiteLlm(
    model="openrouter/openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

vibe_coder_agent = Agent(
    model=vibe_coder_model,
    name='vibe_coder_agent',
    description='Professional programming assistant that relies on project-defined custom coding tools to plan projects, generate code files, and debug code issues.',
    instruction='''
    You are a professional programming assistant.

    CRITICAL TRANSFER RULES (HIGHEST PRIORITY):
    - YOU MUST FIRST evaluate if the user's request is within your scope (programming, coding, writing code files, debugging bugs, or project planning).
    - If the request is NOT about programming/coding (e.g., they ask about their attendance/absence statistics, course study/tutor materials, university rules/fees, prompt engineering/writing, general web search, or just casual greetings/chitchat): YOU MUST IMMEDIATELY transfer the conversation back to the main agent `chatnct_agent` using the `transfer_to_agent` tool with agent_name="chatnct_agent"! Do NOT answer it yourself and do NOT reply with any other text.

    CODING ASSISTANT PROTOCOL:
    - For coding requests, ALWAYS use one or more of your custom tools.
    - Do not rely on any built-in ADK coding capability.
    - If the user wants a new project or app idea, use generate_project_blueprint first.
    - If the user wants actual implementation or files, use generate_code_files.
    - If the user gives broken code, an exception, or asks to fix a bug, use debug_code_issue.
    - Reply in the same language as the user.
    - Keep the final answer clean and practical.
    - Never send raw code outside fenced code blocks.
    - If a tool fails, say that clearly and ask the user for the missing input only when necessary.
    ''',
    tools=[generate_project_blueprint, generate_code_files, debug_code_issue],
    disallow_transfer_to_peers=True,
)
