# ============================================================
# LangGraph Workflow Skeleton
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================

from langgraph.graph import StateGraph, END
from typing import TypedDict


# ------------------------------------------------------------
# Shared State Definition
# ------------------------------------------------------------
class AgentState(TypedDict):
    user_text: str
    retrieved_context: str
    agent_response: str


# ------------------------------------------------------------
# Node 1 — Input Node
# ------------------------------------------------------------
def receive_input(state: AgentState):
    """
    First node: receives user text from FastAPI.
    """
    user_text = state["user_text"]
    return {"user_text": user_text}


# ------------------------------------------------------------
# Node 2 — Retrieval Node (pgvector placeholder)
# ------------------------------------------------------------
def retrieve_context(state: AgentState):
    """
    Placeholder retrieval node.
    Later you will integrate pgvector + Postgres.
    """
    user_text = state["user_text"]

    # Placeholder: no DB yet
    context = f"(no retrieval yet) Relevant info for: {user_text}"

    return {"retrieved_context": context}


# ------------------------------------------------------------
# Node 3 — Reasoning Node (LLM placeholder)
# ------------------------------------------------------------
def generate_response(state: AgentState):
    """
    Placeholder reasoning node.
    Later you will integrate LiteLLM routing.
    """
    user_text = state["user_text"]
    context = state["retrieved_context"]

    # Placeholder agent response
    response = f"Agent response based on: '{user_text}' with context: '{context}'"

    return {"agent_response": response}


# ------------------------------------------------------------
# Build the Graph
# ------------------------------------------------------------
def build_workflow():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("receive_input", receive_input)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_response", generate_response)

    # Define edges
    workflow.set_entry_point("receive_input")
    workflow.add_edge("receive_input", "retrieve_context")
    workflow.add_edge("retrieve_context", "generate_response")
    workflow.add_edge("generate_response", END)

    return workflow.compile()


# ------------------------------------------------------------
# Singleton workflow instance
# ------------------------------------------------------------
workflow = build_workflow()


# ------------------------------------------------------------
# Public API for FastAPI route
# ------------------------------------------------------------
def run_agent(user_text: str) -> str:
    """
    Called by FastAPI route.
    Executes the LangGraph workflow.
    """
    initial_state = {"user_text": user_text}
    final_state = workflow.invoke(initial_state)
    return final_state["agent_response"]
