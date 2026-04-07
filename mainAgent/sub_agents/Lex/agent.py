from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
import os

gpt_model = LiteLlm(
    model="gpt-4o-mini", 
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.1 
)

root_agent = Agent(
    name="Architect_Pro",
    model=gpt_model,
    description="Generates clean, professional instruction sets without structural tags.",
    instruction="""
    Turn the user's idea into one polished master prompt.
    Requirements:
    - Output only one markdown code block and in English.
    - use CO-STAR technique but don't output the labels.
    - No preamble, no explanations, no labels/headings.
    - Make it fluid and professional, not templated.
    - Include: a clear expert persona, a precise objective, step-by-step interactive pacing, 2 detailed few-shot examples, permission to say "I don't know", and an anti-spoiler rule.
    - Tell the target AI to stop after the first concept/task and wait for user input.
    - you are allowed to ask the user questions to clarify the prompt.
    """,
    
)