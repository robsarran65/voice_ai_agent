class SpecialistDeepSeek:
    def execute(self, task):
        return {
            "status": "ok",
            "task": task["title"],
            "message": f"DeepSeek specialist completed: {task['title']}",
        }
