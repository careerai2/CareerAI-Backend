from langgraph.types import Command,Send
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from ..llm_model import SwarmResumeState,InternshipState
from redis_config import redis_client as r 
from langchain_core.runnables import RunnableConfig
from models.resume_model import Internship
import json 
from typing import Literal


@tool("transfer_to_enhancer_pipeline", description="once after updateing the entry pass on to this pipeline so that it can enhance and add it to the resume")
def transfer_to_enhancer_pipeline(
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config:RunnableConfig
) -> Command[Literal["update_entry_model"]]:
    try:
        tool_message = ToolMessage(
            content="Successfully transferred to transfer_to_enhancer_pipeline",
            name="handoff_to_enhancer_pipeline",
            tool_call_id=tool_call_id,
        )
        
        
        # print("handoff tool:",state["internship"])
        print("Transferring to enhancer_pipeline")

        return Command(
            goto="retriever_model",
            update={"messages": state["messages"] + [tool_message]},
        )
    except Exception as e:
        # Optionally, you can log the error or handle it as needed
        print(f"Error in handoff tool: {e}")
        return 




@tool("transfer_to_update_internship_agent", description="This model can update existing internship entries based on user inputs by chatting with the user")
def transfer_to_update_internship_agent(
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config: RunnableConfig
) -> Command[Literal["update_entry_model"]]:
    try:
        tool_message = ToolMessage(
            content="Successfully transferred to internship_model",
            name="handoff_to_internship_model",
            tool_call_id=tool_call_id,
        )

        thread_id = config.get("metadata", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required in metadata")

        # Persist for later session recovery
        r.set(
            f"state:{thread_id}:internship",
            json.dumps({
                "entry": Internship().model_dump(),
                "retrived_info": "",
                "active_agent": "update_internship_agent",
            })
        )

        print("Transferring to update_internship_model")
        
        state["internship"] = {
            "entry": Internship().model_dump(),
            "retrived_info": "",
            "active_agent": "update_internship_agent",
        }
        
        print("State after setting internship:", state["internship"])

        # Update graph state directly
        return Command(
            goto="update_entry_model",
            update={
                "messages": state["messages"] + [tool_message],
                "internship": {
                    "entry": Internship().model_dump(),
                    "retrived_info": "",
                    "active_agent": "update_internship_agent",
                },
            },
        )
    except Exception as e:
        print(f"Error in handoff tool: {e}")
        return




@tool("transfer_to_add_internship_agent", description="This model can create new internship entries based on user inputs")
def transfer_to_add_internship_agent(
    state: Annotated[SwarmResumeState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    config:RunnableConfig
) -> Command[Literal["internship_model"]] :
    try:
        tool_message = ToolMessage(
            content="Successfully transferred to internship_model",
            name="handoff_to_internship_model",
            tool_call_id=tool_call_id,
        )
        thread_id = config.get("metadata", {}).get("thread_id")

        
        if not thread_id:
            raise ValueError("thread_id is required in metadata")
        
        
        
        
        r.set(f"state:{thread_id}:internship", json.dumps({"entry":Internship().model_dump(),"retrived_info":"","active_agent":"add_internship_agent"}))   
        
        print("Transferring to internship model")
        
        state["internship"] = {
            "entry": Internship().model_dump(),
            "retrived_info": "",
            "active_agent": "add_internship_agent",
        }
        
        
        print("State after setting internship:", state["internship"])
        
        
        return Command(
            goto="internship_model",
            update={"messages": state["messages"] + [tool_message],       
            "internship": {
            "entry": Internship().model_dump(),
            "retrived_info": "",
            "active_agent": "add_internship_agent",
        }
                    }
        )
    except Exception as e:
        # Optionally, you can log the error or handle it as needed
        print(f"Error in handoff tool: {e}")
        return 
