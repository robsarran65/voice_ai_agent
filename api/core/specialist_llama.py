class SpecialistLLaMA:
    def execute(self, task):
        return {
            "status": "ok",
            "task": task["title"],
            "message": f"LLaMA specialist completed: {task['title']}",
        }
