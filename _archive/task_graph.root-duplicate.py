# ============================================================
# Agent-Team Task Graph (DAG)
# Voice AI Customer Support Agent (Low/No-Cost Edition)
# ============================================================

TASK_GRAPH = {
    # --------------------------------------------------------
    # PHASE 1 — Architecture & Design
    # --------------------------------------------------------
    "architecture_diagram": {
        "id": "A1",
        "title": "Produce architecture diagram",
        "phase": "Architecture",
        "depends_on": [],
        "agent": "Coordinator",
        "status": "pending",
    },
    "component_list": {
        "id": "A2",
        "title": "Produce component list",
        "phase": "Architecture",
        "depends_on": ["A1"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 2 — Frontend Voice Interface
    # --------------------------------------------------------
    "mic_capture": {
        "id": "B1",
        "title": "Implement Chrome microphone capture",
        "phase": "Frontend",
        "depends_on": ["A2"],
        "agent": "Specialist-DeepSeek",
        "status": "pending",
    },
    "chrome_stt": {
        "id": "B2",
        "title": "Implement Chrome STT (webkitSpeechRecognition)",
        "phase": "Frontend",
        "depends_on": ["B1"],
        "agent": "Specialist-DeepSeek",
        "status": "pending",
    },
    "chrome_tts": {
        "id": "B3",
        "title": "Implement Chrome TTS (speechSynthesis)",
        "phase": "Frontend",
        "depends_on": ["B2"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    "frontend_ws_client": {
        "id": "B4",
        "title": "Implement WebSocket/HTTP client",
        "phase": "Frontend",
        "depends_on": ["B3"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 3 — FastAPI Backend
    # --------------------------------------------------------
    "fastapi_structure": {
        "id": "C1",
        "title": "Create FastAPI project structure",
        "phase": "Backend",
        "depends_on": ["B4"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    "pydantic_models": {
        "id": "C2",
        "title": "Add Pydantic request/response models",
        "phase": "Backend",
        "depends_on": ["C1"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    "uvicorn_config": {
        "id": "C3",
        "title": "Add Uvicorn server config",
        "phase": "Backend",
        "depends_on": ["C2"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 4 — Agent Workflow (LangGraph)
    # --------------------------------------------------------
    "langgraph_workflow": {
        "id": "D1",
        "title": "Build LangGraph workflow",
        "phase": "Agent",
        "depends_on": ["C3"],
        "agent": "Coordinator",
        "status": "pending",
    },
    "litellm_routing": {
        "id": "D2",
        "title": "Add LiteLLM routing",
        "phase": "Agent",
        "depends_on": ["D1"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    "redis_memory": {
        "id": "D3",
        "title": "Add Redis session memory",
        "phase": "Agent",
        "depends_on": ["D2"],
        "agent": "Specialist-DeepSeek",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 5 — Data Layer (Postgres + pgvector)
    # --------------------------------------------------------
    "postgres_setup": {
        "id": "E1",
        "title": "Set up Postgres + pgvector",
        "phase": "Data",
        "depends_on": ["D3"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    "ingestion_pipeline": {
        "id": "E2",
        "title": "Build ingestion pipeline",
        "phase": "Data",
        "depends_on": ["E1"],
        "agent": "Specialist-DeepSeek",
        "status": "pending",
    },
    "retrieval_pipeline": {
        "id": "E3",
        "title": "Build retrieval pipeline",
        "phase": "Data",
        "depends_on": ["E2"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 6 — Observability & Testing
    # --------------------------------------------------------
    "langfuse_tracing": {
        "id": "F1",
        "title": "Add Langfuse tracing",
        "phase": "Observability",
        "depends_on": ["E3"],
        "agent": "Coordinator",
        "status": "pending",
    },
    "ai_evals": {
        "id": "F2",
        "title": "Add AI evals",
        "phase": "Observability",
        "depends_on": ["F1"],
        "agent": "TestAgent",
        "status": "pending",
    },
    "pytest_tests": {
        "id": "F3",
        "title": "Add Pytest tests",
        "phase": "CI",
        "depends_on": ["F2"],
        "agent": "TestAgent",
        "status": "pending",
    },
    "uv_ruff_ci": {
        "id": "F4",
        "title": "Add uv + Ruff CI",
        "phase": "CI",
        "depends_on": ["F3"],
        "agent": "Specialist-LLaMA",
        "status": "pending",
    },
    # --------------------------------------------------------
    # PHASE 7 — Deployment
    # --------------------------------------------------------
    "deploy_backend": {
        "id": "G1",
        "title": "Deploy backend (Render)",
        "phase": "Deployment",
        "depends_on": ["F4"],
        "agent": "Coordinator",
        "status": "pending",
    },
    "deploy_frontend": {
        "id": "G2",
        "title": "Deploy frontend (Vercel)",
        "phase": "Deployment",
        "depends_on": ["G1"],
        "agent": "Coordinator",
        "status": "pending",
    },
}


def get_ready_tasks():
    """Return tasks with no unmet dependencies."""
    ready = []
    for task_id, task in TASK_GRAPH.items():
        deps = task["depends_on"]
        if all(TASK_GRAPH[d]["status"] == "complete" for d in deps):
            if task["status"] == "pending":
                ready.append(task)
    return ready


def mark_complete(task_id):
    """Mark a task as complete."""
    TASK_GRAPH[task_id]["status"] = "complete"
