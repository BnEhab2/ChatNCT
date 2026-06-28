"""
Custom coding tools for the vibe_coder agent.

These tools are implemented locally by the project team and do not depend on
ADK built-in coding tools. Each tool uses the project's allowed OpenRouter
configuration to generate structured outputs for programming tasks.
"""


import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "mainAgent" / ".env")


OPENROUTER_MODEL = os.getenv("VIBE_CODER_MODEL", "openai/gpt-4o-mini")


def _validate_text(value: str, field_name: str) -> dict[str, str] | None:
    """Return an error payload when a required string input is empty."""
    if not value or not str(value).strip():
        return {"status": "error", "error_message": f"{field_name} is required."}
    return None


def _get_client() -> OpenAI:
    """Create an OpenAI-compatible client pointed at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def _run_code_prompt(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call the allowed code model and normalize the response payload."""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            return {"status": "error", "error_message": "The coding model returned an empty response."}

        return {"status": "success", "result": content}
    except Exception as exc:
        return {"status": "error", "error_message": str(exc)}


def generate_project_blueprint(requirement: str, stack: str = "") -> dict[str, Any]:
    """Create a project plan and file/folder structure for a coding request."""
    err = _validate_text(requirement, "requirement")
    if err:
        return err

    stack_line = f"Preferred stack: {stack.strip()}" if stack.strip() else "Preferred stack: choose a sensible default."
    return _run_code_prompt(
        system_prompt=(
            "You are a senior software architect. "
            "Return a concise implementation blueprint for a software request. "
            "Always include these sections in order: "
            "1) Project Overview "
            "2) Tech Stack "
            "3) Folder Structure "
            "4) Build Steps "
            "5) Notes. "
            "Keep the output practical and copy-ready."
        ),
        user_prompt=f"Requirement: {requirement.strip()}\n{stack_line}",
    )


def generate_code_files(requirement: str, stack: str = "") -> dict[str, Any]:
    """Generate code for the requested project in a multi-file format."""
    err = _validate_text(requirement, "requirement")
    if err:
        return err

    stack_line = f"Target stack: {stack.strip()}" if stack.strip() else "Target stack: choose the most suitable one."
    return _run_code_prompt(
        system_prompt=(
            "You are a professional software engineer. "
            "Generate clean, working code for the requested task. "
            "Always format the answer using this structure only: "
            "Project Structure, then one section per file. "
            "Every file section must start with 'File: <path>' and then a fenced code block. "
            "Never place code outside fenced blocks. "
            "Keep explanations minimal."
        ),
        user_prompt=f"Build this software request:\n{requirement.strip()}\n\n{stack_line}",
    )


def debug_code_issue(code: str, error_message: str = "", context: str = "") -> dict[str, Any]:
    """Analyze broken code and return a fix-oriented debugging response."""
    err = _validate_text(code, "code")
    if err:
        return err

    return _run_code_prompt(
        system_prompt=(
            "You are a senior debugging assistant. "
            "Analyze the code and explain the root cause before proposing the fix. "
            "Always include these sections in order: "
            "Problem, Root Cause, Fix, Updated Code. "
            "Put all code inside fenced code blocks."
        ),
        user_prompt=(
            f"Code:\n{code.strip()}\n\n"
            f"Error message:\n{error_message.strip() or 'No explicit error message provided.'}\n\n"
            f"Extra context:\n{context.strip() or 'No extra context provided.'}"
        ),
    )
