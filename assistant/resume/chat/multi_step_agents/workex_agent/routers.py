from assistant.resume.chat.llm_model import SwarmResumeState
from langgraph.graph import StateGraph, END



# ---------------------------
# Conditional Router
# ---------------------------

def workex_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["workex"]["patches"]
    

    # 1. Go to workex tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_workex"

    
    return END
