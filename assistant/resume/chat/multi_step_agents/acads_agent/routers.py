from assistant.resume.chat.llm_model import SwarmResumeState
from langgraph.graph import StateGraph, END


# ---------------------------
# Conditional Router
# ---------------------------

def acads_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["acads"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to acads tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_acads"

    
    return END


