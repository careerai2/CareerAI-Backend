from langgraph_swarm import create_handoff_tool
from typing import Annotated
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState


transfer_to_main_agent = create_handoff_tool(
    agent_name="main_assistant",
    description="Transfer user to the main assistant for general queries.",
)

transfer_to_education_agent = create_handoff_tool(
    agent_name="education_assistant",
    description="Transfer user to the education assistant to collect education details and manage it in resume."
)

transfer_to_internship_agent = create_handoff_tool(
    agent_name="internship_assistant",
    description="Transfer user to the internship assistant to collect internship details and manage it in resume."
)

transfer_to_workex_agent = create_handoff_tool(
    agent_name="workex_assistant",
    description="Transfer user to the work experience assistant to collect work experience details and manage it in resume."
)

transfer_to_por_agent = create_handoff_tool(
    agent_name="Position_of_responsibility_assistant",
    description="Transfer user to the Position of Responsibility assistant to collect Position of Responsibility details and manage it in resume."
)


transfer_to_scholastic_achievement_agent = create_handoff_tool(
    agent_name="scholastic_achievement_assistant",
    description="Transfer user to the scholastic achievement assistant to collect scholastic achievement details and manage it in resume."
)


transfer_to_extra_curricular_agent = create_handoff_tool(
    agent_name="extra_curricular_assistant",
    description="Transfer user to the extra-curricular assistant to collect extra-curricular details and manage it in resume."
)

transfer_to_acads_agent = create_handoff_tool(
    agent_name="acads_assistant",
    description="Transfer user to the acad project assistant to collect acad project details and manage it in resume."
)


transfer_to_certification_assistant_agent = create_handoff_tool(
    agent_name="certification_assistant",
    description="Transfer user to the Certifications assistant to collect Certification details details and manage it in resume."
)



# # Code for custome handoff tool
# def education_handoff_tool(*, agent_name: str, name: str | None, description: str | None) -> BaseTool:

#     @tool(name, description=description)
#     def handoff_to_agent(
#         # you can add additional tool call arguments for the LLM to populate
#         # for example, you can ask the LLM to populate a task description for the next agent
#         task_description: Annotated[str, "Detailed description of what the next agent should do, including all of the relevant context."],
#         # you can inject the state of the agent that is calling the tool
#         state: Annotated[dict, InjectedState],
#         tool_call_id: Annotated[str, InjectedToolCallId],
#     ):
#         tool_message = ToolMessage(
#             content=f"Successfully transferred to {agent_name}",
#             name=name,
#             tool_call_id=tool_call_id,
#         )
#         message_key = {
#             "main_assistant": "general_messages",
#             "education_assistant": "education_messages",
#             "internship_assistant": "internship_messages",
#         }.get(agent_name, "general_messages")
        
#         # you can use a different messages state key here, if your agent uses a different schema
#         # e.g., "alice_messages" instead of "messages"
#         messages = state["messages"]
#         return Command(
#             goto=agent_name,
#             graph=Command.PARENT,
#             # NOTE: this is a state update that will be applied to the swarm multi-agent graph (i.e., the PARENT graph)
#             update={
#                 "messages": messages + [tool_message],
#                 "active_agent": agent_name,
#                 # optionally pass the task description to the next agent
#                 "task_description": task_description,
#             },
#         )

#     return handoff_to_agent