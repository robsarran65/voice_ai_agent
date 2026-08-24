# ============================================================
# Coordinator Agent — orchestration layer
# ============================================================
# Owns the domain rules: which persona and model a flow uses, and what a
# failed model call *means* for the user. It calls the LLM service for the
# mechanics but never re-implements them.

import logging
from dataclasses import dataclass

from agents.task_graph import get_ready_tasks, mark_complete
from api.core.persona import (
    CANDY_FAILURE_LINE,
    CANDY_FALLBACK_MODEL,
    CANDY_MAX_TOKENS,
    CANDY_MODEL,
    CANDY_PERSONA,
    CANDY_TEMPERATURE,
)
from api.core.specialist_deepseek import SpecialistDeepSeek
from api.core.specialist_llama import SpecialistLLaMA
from api.core.test_agent import TestAgent
from api.services.litellm_router import complete_chat

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

    def respond(self, user_text: str) -> AgentReply:
        """
        Answer the user's spoken text.

        Holds no per-request state, so the module-level instance in the route
        is safe to share across concurrent requests (roadmap item 5).
        """
        result = complete_chat(
            system_prompt=CANDY_PERSONA,
            user_text=user_text,
            model=CANDY_MODEL,
            fallback_model=CANDY_FALLBACK_MODEL,
            max_tokens=CANDY_MAX_TOKENS,
            temperature=CANDY_TEMPERATURE,
        )

        if not result.ok:
            # Classify here, not in the service: the operator gets the detail
            # in the logs, the user gets something Candy can say out loud.
            log.error("Candy reply failed: %s", result.error)
            return AgentReply(ok=False, message=CANDY_FAILURE_LINE)

        return AgentReply(ok=True, message=result.text, model=result.model)

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
