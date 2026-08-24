# ============================================================
# Coordinator Agent — orchestration layer
# ============================================================
# Owns the domain rules: which persona and model a flow uses, and what a
# failed model call *means* for the user. It calls the LLM service for the
# mechanics but never re-implements them.

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from agents.task_graph import get_ready_tasks, mark_complete
from api.core.persona import (
    CANDY_FAILURE_LINE,
    CANDY_FALLBACK_MODEL,
    CANDY_MAX_TOKENS,
    CANDY_MODEL,
    CANDY_TEMPERATURE,
    dated_persona,
)
from api.core.specialist_deepseek import SpecialistDeepSeek
from api.core.specialist_llama import SpecialistLLaMA
from api.core.test_agent import TestAgent
from api.core import pending
from api.core.tools import available_tools, dispatch
from api.services import google_calendar
from api.services.litellm_router import complete_messages


def _spoken_time(iso: str) -> str:
    """Turn an ISO timestamp into something worth hearing out loud."""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return "as requested"
    # Strip the leading zero from the hour only. Lowercasing the whole string
    # to fix "03:00" would also flatten the weekday and month names.
    return dt.strftime("%A %d %B at %I:%M %p").replace(" at 0", " at ")

# Two is enough for "call a tool, then answer". A third hop only happens if
# the model chains calls, which none of Candy's tools require.
MAX_TOOL_HOPS = 4

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentReply:
    """
    What the route needs to build a response: the words to speak, plus
    whether they came from the model or from the failure path.
    """

    ok: bool
    message: str  # always safe to speak aloud
    model: str | None = None


class CoordinatorAgent:
    def __init__(self):
        # Dispatch table rather than an if/elif chain — adding a specialist
        # is now a one-line registration.
        self._specialists = {
            "Specialist-LLaMA": SpecialistLLaMA(),
            "Specialist-DeepSeek": SpecialistDeepSeek(),
            "TestAgent": TestAgent(),
        }

    def respond(self, user_text: str, session_id: str = "") -> AgentReply:
        """
        Answer the user's spoken text, using tools when the model asks for them.

        Holds no per-request state, so the module-level instance in the route
        is safe to share across concurrent requests (roadmap item 5).
        """
        # A staged calendar event is settled here, in code, before the model
        # is involved at all. Whether the user consented to a write is not a
        # judgement call worth delegating.
        staged = pending.get(session_id) if session_id else None
        if staged is not None:
            answer = pending.read_answer(user_text)
            if answer == "yes":
                pending.clear(session_id)
                return self._create_staged_event(staged)
            if answer == "no":
                pending.clear(session_id)
                return AgentReply(ok=True, message="Alright, I won't add it.")
            # Anything else is a new request, not consent — drop the proposal
            # so a stray "yeah" later can't resurrect it.
            pending.clear(session_id)

        now = datetime.now().astimezone()
        messages = [
            {"role": "system", "content": dated_persona(
                now.strftime("%A, %d %B %Y"), str(now.tzinfo))},
            {"role": "user", "content": user_text},
        ]
        offered = available_tools()

        # Bounded, because a model that keeps calling tools would otherwise
        # spin while someone waits for a spoken answer.
        for hop in range(MAX_TOOL_HOPS):
            result = complete_messages(
                messages=messages,
                model=CANDY_MODEL,
                fallback_model=CANDY_FALLBACK_MODEL,
                max_tokens=CANDY_MAX_TOKENS,
                temperature=CANDY_TEMPERATURE,
                tools=offered,
            )

            if not result.ok:
                # Classify here, not in the service: the operator gets the
                # detail in the logs, the user gets something Candy can say.
                log.error("Candy reply failed: %s", result.error)
                return AgentReply(ok=False, message=CANDY_FAILURE_LINE)

            if not result.tool_calls:
                return AgentReply(ok=True, message=result.text, model=result.model)

            messages.append(result.assistant_message)
            for call in result.tool_calls:
                log.info("tool %s(%s)", call["name"], call["arguments"])
                output = dispatch(call["name"], call["arguments"], session_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(output),
                })

        log.error("Tool loop hit %d hops without an answer", MAX_TOOL_HOPS)
        return AgentReply(ok=False, message=CANDY_FAILURE_LINE)

    def _create_staged_event(self, staged) -> AgentReply:
        """Write the event the user just approved, and say what happened."""
        payload = staged.payload
        result = google_calendar.create_event(
            summary=payload["summary"],
            start_iso=payload["start_iso"],
            end_iso=payload["end_iso"],
            location=payload.get("location", ""),
        )
        if not result.ok:
            log.error("Calendar write failed: %s", result.error)
            return AgentReply(
                ok=False,
                message="I couldn't add that to your calendar just then. Try again in a moment.",
            )

        start = _spoken_time(payload["start_iso"])
        return AgentReply(ok=True, message=f"Done — {payload['summary']} is on your calendar {start}.")

    def run_next_task(self, completed: set[str]):
        """
        Advance the build DAG by one ready task.

        `completed` is passed in rather than held on the instance — shared
        mutable state on a process-wide singleton is not safe once more than
        one caller exists.
        """
        ready = get_ready_tasks(completed)
        if not ready:
            return {"status": "done", "message": "All tasks completed."}

        task = ready[0]
        agent_name = task["agent"]
        specialist = self._specialists.get(agent_name)

        if specialist is None:
            return {"status": "error", "error": f"Unknown agent: {agent_name}"}

        result = specialist.execute(task)
        mark_complete(completed, task["id"])

        return {
            "status": "ok",
            "task_id": task["id"],
            "task_title": task["title"],
            "agent": agent_name,
            "result": result,
        }
