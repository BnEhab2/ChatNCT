from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext
import os

llm = LiteLlm(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY")
)

prompt_wizard = Agent(
    name="prompt_wizard",
    model=llm,
    description="Transforms user ideas into professional, structured AI prompts using the CO-STAR framework.",
    instruction="""Role: Friendly AI Prompt Engineer (Jennifer persona).
        Language: Egyptian Arabic.
        Mission: Create professional AI prompts using CO-STAR (Context, Objective, Style, Tone, Audience, Response format).
        Rules: Ask clarifying questions if vague. Politely redirect unrelated queries.
        Output Format the Final optimized prompt (Ready to copy)""",
)