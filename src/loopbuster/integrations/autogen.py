"""
AutoGen Integration for LoopBuster
"""
def apply_loopbuster(agent, buster_instance):
    original_generate = agent.generate_reply
    
    def wrapped_generate(*args, **kwargs):
        # Inspect context
        context = kwargs.get('messages', [])
        if context and buster_instance.check_cycle(str(context[-1])):
            return True, "LoopBuster Intervention: " + buster_instance.get_suggestion()
        return original_generate(*args, **kwargs)
        
    agent.generate_reply = wrapped_generate
