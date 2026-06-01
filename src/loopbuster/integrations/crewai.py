"""
CrewAI Integration for LoopBuster
"""
class LoopBusterCallback:
    def __init__(self, buster_instance):
        self.buster = buster_instance
        
    def on_task_start(self, task):
        pass
        
    def on_step(self, step_info):
        if self.buster.check_cycle(str(step_info)):
            raise InterruptedError("LoopBuster Intervention: " + self.buster.get_suggestion())
