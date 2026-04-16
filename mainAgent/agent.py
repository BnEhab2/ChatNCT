"""
agent.py - AI Agent Configuration (The Brain)

This file sets up the main AI agent (called "ChatNCT" or "Jennifer") that
students interact with through the chat interface.

The agent uses GPT-4o-mini as its language model and has 5 specialized
"sub-agents" that handle different types of requests:

  - prompt_wizard    : Helps write professional AI prompts (CO-STAR framework)
  - study_agent      : Summarizes lectures and creates quizzes (uses RAG)
  - student_chatbot  : Answers questions about student affairs (uses FAISS)
  - vibe_coder_agent : Generates code and builds projects (powered by Gemini)
  - search_agent     : Answers general knowledge questions (uses Google Search)

The main agent automatically decides which sub-agent to use based on the
student's question. This "routing" happens invisibly - the student just
sees one unified chatbot.
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Import each sub-agent from its respective module
from .sub_agents.Lex.agent import root_agent as prompt_wizard
from .sub_agents.marwan.study_agent.agent import root_agent as study_agent
from .sub_agents.Mixxx.search_agent.agent import root_agent as search_agent
from .sub_agents.shahd.pro.student_chatbot.agent import root_agent as student_chatbot
from .sub_agents.Mixxx.vibe_coder.agent import vibe_coder_agent
import os

# ── Language Model Setup ──────────────────────────────────────────────
# LiteLlm is a wrapper that lets us use different AI models (OpenAI, Gemini, etc.)
# We're using GPT-4o-mini here for a good balance of speed and quality.
llm = LiteLlm(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# ── Main Agent Definition ─────────────────────────────────────────────
# This is the "root" agent that receives every student message first.
# It decides whether to answer directly or pass the request to a sub-agent.
root_agent = LlmAgent(
    name="chatnct_agent",
    model=llm,
    description="ChatNCT — University AI Assistant",
    instruction="""
        You are a smart, chill assistant who talks like a helpful friend.
        Style:
        - Sound natural, casual, and human, Egyptian Gen Z.
        - Be a bit conversational (like you're talking to a friend), not formal.
        - Keep answers short and to the point.
        - Explain simply, step-by-step only when needed.
        - It's okay to add light humor or personality when appropriate.
        - Don't be overly polite or robotic.
        - If the user is wrong, correct them in a relaxed, friendly way.
        - If something is unclear, ask a quick, casual question.
        Important:
        - Never say you are an AI.
        - Never mention routing or sub-agents.
        - Don't sound like customer support.
        Routing (internal only):
        - Prompt writing → prompt_wizard
        - Study topics → study_agent
        - Student affairs → student_chatbot
        - Coding → vibe_coder_agent
        - General knowledge → search_agent
    """,
    # List of sub-agents this agent can delegate to
    sub_agents=[prompt_wizard, study_agent, student_chatbot, vibe_coder_agent, search_agent],
)