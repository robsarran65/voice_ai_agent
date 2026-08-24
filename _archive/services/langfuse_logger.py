# ============================================================
# Langfuse Logger
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================

import os
from langfuse import Langfuse

# ------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------
LANGFUSE_API_KEY = os.getenv("LANGFUSE_API_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ------------------------------------------------------------
# Initialize Langfuse Client
# ------------------------------------------------------------
try:
    lf = Langfuse(
        api_key=LANGFUSE_API_KEY, secret_key=LANGFUSE_SECRET_KEY, host=LANGFUSE_HOST
    )
except Exception as e:
    print(f"Langfuse initialization error: {e}")
    lf = None


# ------------------------------------------------------------
# Unified Logging Function
# ------------------------------------------------------------
def log_event(
    name: str,
    input_data: dict | str = None,
    output_data: dict | str = None,
    metadata: dict = None,
    level: str = "info",
):
    """
    Unified logging function for all agent events.
    Used by LangGraph nodes, LLM calls, retrieval, and agents.
    """

    if lf is None:
        return

    try:
        lf.trace(
            name=name,
            input=input_data,
            output=output_data,
            metadata=metadata or {},
            level=level,
        )
    except Exception as e:
        print(f"Langfuse logging error: {e}")


# ------------------------------------------------------------
# Specialized Logging Helpers
# ------------------------------------------------------------
def log_llm_call(prompt: str, response: str, model: str):
    log_event(
        name="llm_call",
        input_data={"prompt": prompt, "model": model},
        output_data={"response": response},
        metadata={"type": "llm"},
    )


def log_retrieval(query: str, results: list):
    log_event(
        name="retrieval",
        input_data={"query": query},
        output_data={"results": results},
        metadata={"type": "retrieval"},
    )


def log_agent_step(agent_name: str, task_title: str, result: str):
    log_event(
        name="agent_step",
        input_data={"agent": agent_name, "task": task_title},
        output_data={"result": result},
        metadata={"type": "agent"},
    )


def log_error(error_message: str, context: dict = None):
    log_event(
        name="error",
        input_data=context or {},
        output_data={"error": error_message},
        metadata={"type": "error"},
        level="error",
    )
