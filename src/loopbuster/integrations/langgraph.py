"""
LangGraph Integration for LoopBuster
"""
from typing import Any, Dict

def loopbuster_middleware(state: Dict[str, Any], buster_instance) -> Dict[str, Any]:
    # Extract recent action from state
    action = state.get("recent_action", "")
    if buster_instance.check_cycle(action):
        state["loop_detected"] = True
        state["intervention"] = buster_instance.get_suggestion()
    return state
