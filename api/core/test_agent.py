class TestAgent:
    def execute(self, task):
        return {
            "status": "ok",
            "task": task["title"],
            "message": f"TestAgent validated: {task['title']}",
        }
