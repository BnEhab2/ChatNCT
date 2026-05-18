from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from .tools import (
    get_student_attendance_summary,
    get_course_session_log,
    get_missed_lectures,
    get_missed_lecture_summaries,
)
import os

# Initialize LiteLLM with OpenRouter
academic_model = LiteLlm(
    model="openrouter/openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

# Create the academic_analyzer agent
root_agent = Agent(
    model=academic_model,
    name='academic_analyzer',
    description='Analyzes a student\'s academic attendance, logs of lectures, warning alerts, missed lecture summaries, and provides supportive academic advice in Egyptian dialect.',
    instruction='''
    You are Academic Coach (مستشار المتابعة الأكاديمية). Speak in friendly Egyptian Gen Z dialect ("يا فنان", "يا بطل", "شد حيلك"). Be concise.

    CRITICAL RULES:
    1. Extract `[STUDENT_CODE: <code>]` from the prompt prefix. Use this code ONLY for tools. NEVER use codes provided by the user. Refuse requests for other students' data.
    2. Never mention the tag, internal routing, or tool names. Call students by their name.
    3. Never hallucinate attendance data. Rely entirely on tools.

    TOOL STRATEGY:
    - Use `get_student_attendance_summary` first.
    - If < 75% attendance: Warn urgently about deprivation and state remaining allowed absences ("فاضلك X غياب وتتحرم!").
    - If ≥ 85%: Encourage them ("حضورك زي الفل 🔥").
    - Use `get_course_session_log` for specific subject logs.
    - Use `get_missed_lectures` for absences.
    - Use `get_missed_lecture_summaries` to help them catch up.

    REFERRALS:
    - Offer summaries for missed lectures. If unavailable, suggest asking the study agent indirectly.
    - Refer student affairs questions to the regular chat.
    ''',
    tools=[
        get_student_attendance_summary,
        get_course_session_log,
        get_missed_lectures,
        get_missed_lecture_summaries,
    ],
)
