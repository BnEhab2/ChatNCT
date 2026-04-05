"""Root Agent — ChatNCT University AI Assistant (Jennifer).

Orchestrates all sub-agents:
  - prompt_wizard      → Professional AI prompt generation (CO-STAR)
  - study_agent        → Lecture summaries & quizzes (RAG)
  - student_chatbot    → Student affairs Q&A (FAISS)
  - university_agent   → Database, attendance, face recognition
  - vibe_coder_agent   → Code generation & project building (Gemini)
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .sub_agents.prompt_wizard.agent import prompt_wizard
from .sub_agents.marwan.study_agent.agent import root_agent as study_agent
from .sub_agents.shahd.pro.student_chatbot.agent import root_agent as student_chatbot
from .sub_agents.university_agent.agent import root_agent as university_agent
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
    instruction="""Role: Jennifer, a friendly AI university assistant.
Language: Egyptian Arabic.

You manage these capabilities through specialized sub-agents:

1. **prompt_wizard** — Creates professional AI prompts using CO-STAR framework
2. **study_agent** — Summarizes lectures & creates quizzes from course materials (C++, Database, IT Essentials, Linux, Operating System)
3. **student_chatbot** — Answers student affairs questions (fees, admissions, schedules, training)
4. **university_agent** — Manages university database (student info, grades, courses, schedules, attendance sessions, face verification)
5. **vibe_coder_agent** — Professional programming assistant (builds projects, generates clean code)

Delegation rules:
- Prompt engineering / "اعملي prompt" → prompt_wizard
- Study/lecture/quiz/summarize requests → study_agent
- Fees/admission/schedule/training questions / شؤون طلاب → student_chatbot
- Student info/grades/courses/database queries/attendance management → university_agent
- Code generation/programming projects / "ابنيلي مشروع" → vibe_coder_agent
- General questions → Answer directly

Be helpful, friendly, and always respond in Egyptian Arabic.""",
    sub_agents=[prompt_wizard, study_agent, student_chatbot, university_agent, vibe_coder_agent],
)