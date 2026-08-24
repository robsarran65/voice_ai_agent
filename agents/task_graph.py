# ============================================================
# Simple DAG for Coordinator Agent
# ============================================================

TASK_GRAPH = [
    {
        "id": "A1",
        "title": "Produce architecture diagram",
        "agent": "Specialist-LLaMA",
        "depends_on": [],
    },
    {
        "id": "A2",
        "title": "List components",
        "agent": "Specialist-LLaMA",
        "depends_on": ["A1"],
    },
    {
        "id": "B1",
        "title": "Build mic capture",
        "agent": "Specialist-DeepSeek",
        "depends_on": ["A2"],
    },
    {
        "id": "B2",
        "title": "Build STT",
        "agent": "Specialist-DeepSeek",
        "depends_on": ["B1"],
    },
    {
        "id": "B3",
        "title": "Build TTS",
        "agent": "Specialist-DeepSeek",
        "depends_on": ["B2"],
    },
    {
        "id": "C1",
        "title": "Build FastAPI structure",
        "agent": "Specialist-LLaMA",
        "depends_on": ["B3"],
    },
    {
        "id": "C2",
        "title": "Build voice-chat route",
        "agent": "Specialist-LLaMA",
        "depends_on": ["C1"],
    },
    {"id": "D1", "title": "Run tests", "agent": "TestAgent", "depends_on": ["C2"]},
]

def get_ready_tasks(completed):
    ready = []
    for task in TASK_GRAPH:
        if task["id"] not in completed:
            if all(dep in completed for dep in task["depends_on"]):
                ready.append(task)
    return ready


def mark_complete(completed, task_id):
    completed.add(task_id)
