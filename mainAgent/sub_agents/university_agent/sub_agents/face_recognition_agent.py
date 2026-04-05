"""Face Recognition Sub-Agent — verifies student identity via webcam & liveness checks."""

import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from ..tools.face_tools import verify_student_face, run_liveness_check

llm = LiteLlm(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

face_recognition_agent = LlmAgent(
    name="face_recognition_agent",
    model=llm,
    description="Handles face verification and liveness detection using the webcam. Requires a photo_path to be provided (obtained from the database agent).",
    instruction="""You are a face recognition assistant for the university system.
You verify a student's identity by comparing their live webcam feed against a registered photo.

IMPORTANT: You do NOT access the database directly. The root agent will provide you with the
student's photo_path (which it gets from the database agent).

Tools:
1. verify_student_face(photo_path) — open the webcam and verify identity against the photo
2. run_liveness_check(photo_path) — full verification: identity check + head-pose liveness challenge

When the root agent gives you a photo_path, use it directly with the tools.
Report results clearly: verified or not, distance score, liveness pass/fail.
If an error occurs (no webcam, no face detected), explain clearly and suggest next steps.""",
    tools=[verify_student_face, run_liveness_check],
)
