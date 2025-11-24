from time import *

SYS_TIME = HH_MM()

# This is the schedule manager for the system. It handles scheduling tasks and managing time-based events, and it logs programs and their execution times.

class ScheduleManager:
    def __init__(self):
        self.scheduled_tasks = []

    def schedule_task(self, task, execution_time):
        """Schedule a new task to be executed at a specific time."""
        self.scheduled_tasks.append((task, execution_time))

    def get_scheduled_tasks(self):
        """Retrieve the list of scheduled tasks."""
        return self.scheduled_tasks



