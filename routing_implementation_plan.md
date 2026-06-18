# Implementation Plan — ADK Routing & Session Improvements

This plan addresses the routing issues and blockers identified in the project's AI agent tree and session management.

## User Review Required

> [!IMPORTANT]
> **Database-backed Isolated Sessions**: We will change the backend to map the PostgreSQL `chat_session_id` directly to the ADK `session_id`. This isolates chat histories per conversation and prevents cross-session context pollution.
>
> **SqliteSessionService Integration**: We will replace the in-memory session service with `SqliteSessionService` pointing to a local file (`sessions.db`). This ensures conversation memory is persisted across server restarts.

## Proposed Changes

---

### AI Agent Configuration

#### [MODIFY] [agent.py](file:///c:/Users/HooooBaaaa/cursor/Gradproject/mainAgent/agent.py)
* Update all prompt instructions in the root agent to refer to `'vibe_coder_agent'` instead of `'coding_agent'` to prevent routing confusion.
* Set `disallow_transfer_to_peers=True` on all sub-agents to enforce the clean **Hub-and-Spoke** routing model (sub-agents only transfer to parent, parent routes to sub-agents).

#### [MODIFY] [sub-agents prompts](file:///c:/Users/HooooBaaaa/cursor/Gradproject/mainAgent/sub_agents/)
* Update the transfer instructions in each sub-agent (e.g. `study_agent`, `academic_analyzer`, `student_chatbot`, `search_agent`, `vibe_coder`) to refer to `agent_name="chatnct_agent"` instead of `target="chatnct_agent"`.

---

### Backend Server & Session Logic

#### [MODIFY] [server.py](file:///c:/Users/HooooBaaaa/cursor/Gradproject/server.py)
* Replace `InMemorySessionService` with `SqliteSessionService(db_path="sessions.db")` for both main and prompt wizards.
* Pass `chat_session_id` from the HTTP request into `_run_agent` and `_stream_agent`, using it as the ADK `session_id`.
* Generate a fresh unique session ID (UUID) for each `_run_prompt_wizard` invocation to prevent prompt history pollution.
* Fix the status message logger in `server.py` line 469 to read `agent_name` instead of `target_agent_name`.

## Verification Plan

### Automated Verification
* Run the test routing script `test_routing.py` to ensure:
  1. Messages are routed to the correct agent.
  2. Sub-agents successfully transfer back to the root agent.
  3. Context is isolated across sessions.

### Manual Verification
* Start the Flask server, create different sessions in the UI (e.g., C++ and Database), and verify that they maintain independent memories.
