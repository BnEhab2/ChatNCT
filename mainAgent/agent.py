"""Root Agent — ChatNCT University AI Assistant (Jennifer).

Orchestrates all sub-agents:
  - prompt_wizard      → Professional AI prompt generation (CO-STAR)
  - study_agent        → Lecture summaries & quizzes (RAG)
  - student_chatbot    → Student affairs Q&A (FAISS)
  - vibe_coder_agent   → Code generation & project building (Gemini)
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .sub_agents.Lex.agent import root_agent as prompt_wizard
from .sub_agents.marwan.study_agent.agent import root_agent as study_agent
from .sub_agents.shahd.pro.student_chatbot.agent import root_agent as student_chatbot
from .sub_agents.Mixxx.vibe_coder.agent import vibe_coder_agent
import os

llm = LiteLlm(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
)

root_agent = LlmAgent(
    name="chatnct_agent",
    model=llm,
    description="ChatNCT — University AI Assistant",
    instruction="""You are a smart, friendly assistant who always replies in natural Egyptian Arabic. Speak like a casual Gen Z Egyptian: direct, confident, helpful, simple, and human. Use light Egyptian slang naturally, mix English tech terms when needed, keep answers short by default, and explain clearly step by step when needed. Avoid formal, robotic, or academic tone. Never say you are an AI.
    Route requests silently:
    - Prompt writing/improving/system prompts -> prompt_wizard
    - Study, lectures, summaries, quizzes, revision, C++, Database, IT, Linux, OS -> study_agent
    - Fees, admissions, schedules, training, student affairs -> student_chatbot
    - Coding, debugging, projects, software building -> vibe_coder_agent
    - Otherwise answer directly.
    If unclear, ask a short clarifying question.""",
    sub_agents=[prompt_wizard, study_agent, student_chatbot, vibe_coder_agent],
)