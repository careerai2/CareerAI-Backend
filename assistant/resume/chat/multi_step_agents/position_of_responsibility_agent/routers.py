from assistant.resume.chat.llm_model import SwarmResumeState
from langgraph.graph import StateGraph, END



    
# ---------------------------
# Conditional Routers
# ---------------------------

# Router for POR Model
def por_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["por"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to por tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_por"

    
    return END


# Router for Query Generator Model


# Router for Retriver Model

# Router for Builder Model




