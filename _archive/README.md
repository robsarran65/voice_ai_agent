# Archived scaffolding

Nothing in here was reachable from the live request path
(`POST /voice-chat/` -> `CoordinatorAgent.respond` -> `run_llm`).

It was written ahead of having any caller, which is the "over-abstraction"
anti-pattern in the service-layer skill: extracting logic used by zero or one
caller. On top of that, four of these modules could not even be imported —
`langgraph`, `langfuse`, `psycopg2`, and `redis` are not in `requirements.txt`,
so any `import` of them would have raised `ImportError`.

Kept (not deleted) because the roadmap plans to rebuild this functionality
properly. Treat these as reference sketches, not working code.

| File | Why archived |
|---|---|
| `task_graph.root-duplicate.py` | Second, divergent copy of `TASK_GRAPH` (dict-shaped, with `phase`/`status`). Zero importers — `api/core/coordinator_agent.py` imports the list-shaped `agents/task_graph.py`. Two sources of truth meant a fix to one would never reach the other. |
| `services/langgraph_workflow.py` | No callers. All three nodes were placeholders returning f-strings; its `retrieve_context` never called the real one in `retrieval.py`. Needs `langgraph` (not installed). |
| `services/retrieval.py` | No callers. `store_document` routed an `INSERT` through `query()`, which never commits — it silently stored nothing. Embeddings were a fake `[float(len(text))] * 10`. Also imported `run_llm` without using it. |
| `services/postgres_client.py` | Only caller was `retrieval.py` (itself dead). Leaked connections — `conn.close()` sat inside the `try` after `fetchall()`, so any exception skipped it. No pooling, one connect per call. `execute()` had zero callers while the one INSERT used `query()`. Needs `psycopg2` (not installed). |
| `services/redis_client.py` | No callers. Silent no-op whenever the client failed to init. Needs `redis` (not installed). |
| `services/langfuse_logger.py` | No callers. Needs `langfuse` (not installed). |

## Before restoring any of these

Per the skill's migration checklist, do it in this order:

1. Write the flow in the action (route/coordinator) first, so the behavior is clear.
2. Only once a **second** caller needs the same mechanic, extract it to a service.
3. Give it explicit parameters and a structured return — no hidden globals, no
   swallowed errors, no reaching into the database from the service.
4. Add the dependency to `requirements.txt` in the same change.
