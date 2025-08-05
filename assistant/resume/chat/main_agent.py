from langgraph.runtime import get_runtime
from typing_extensions import TypedDict, Annotated, runtime
from langchain_core.messages import AnyMessage,ToolMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from assistant.resume.chat.tools import tools_education, tools_internship, get_resume
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import json
from models.resume_model import Education,ResumeLLMSchema
from langgraph.types import Command
from .handoff_tools import transfer_to_education_agent, transfer_to_internship_agent

# llm = init_chat_model("openai:gpt-4")




from langchain_google_genai import ChatGoogleGenerativeAI

# Create a Gemini Flash instance
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Use gemini-1.5-pro for higher reasoning
    temperature=0,             # Optional: control creativity
    max_output_tokens=1024     # Optional: control output length
)

# # llm_with_education_tools = llm.bind_tools(tools_education)

# # agent = create_react_agent(
# #     model="openai:gpt-4",
# #     tools=tools_education,
# #     prompt=prompt,
# #     context_schema=ContextSchema,
# #     state_schema=MessagesState,
# #     name="education_agent",
# # )

# class ContextSchema(TypedDict):
#     user_id: str
#     resume_id: str


# class GeneralState(TypedDict):
#     general_messages: Annotated[list[AnyMessage], add_messages]
#     resume_schema: ResumeLLMSchema
#     resume:ResumeLLMSchema


# # Subgraph
# def main_model(state: GeneralState):
#     runtime = get_runtime()  # No schema argument
#     user_id = runtime.context.get("user_id")
#     resume_id = runtime.context.get("resume_id")

#     # System instruction as a system message
#     system_message = SystemMessage(content=(
#         "## 🧠 Role\n"
#         "You are a concise, intelligent, and friendly assistant designed to **help users build their resume through natural conversation**. "
#         "You operate as part of a multi-step intelligent system that routes users to specialized modules like *education*, *internships*, or *projects*, depending on the context of the message.\n\n"

#         "## 🎯 Objective\n"
#         "Your primary goal is to **extract and clarify resume information from the user** in a human-like way. "
#         "You should never fabricate or assume content. Always guide the user in small steps to get accurate and meaningful inputs.\n\n"

#         "## 🧭 Flow & Routing\n"
#         "- Start the conversation with the user and understand their intent.\n"
#         "- Based on the user's message, the system will detect which resume section they're referring to (e.g., Education, Internship).\n"
#         "- Once detected, the conversation will be routed to a **specialized chatbot module** for that section ***AND YOU DON'T NEED TO RESPOND IN SUCH CASE***\n"
#         "- If tools (functions) are required, they will be invoked and results will be streamed back.\n"
#         "- After tool execution, control will return to the specialized section chatbot.\n\n"

#         "## 🛠️ Behavior Rules\n"
#         "- Speak in short, simple, friendly sentences.\n"
#         "- Ask **only one question at a time**.\n"
#         "- Avoid markdown or bullet points in *user-facing* responses.\n"
#         "- Never fabricate resume data.\n"
#         "- If the user's message isn’t clear, help them rephrase it.\n"
#         "- Focus only on clarifying user input; let the specialized modules handle the actual resume-building logic.\n\n"

#         "## 📌 Example Behavior\n"
#         "- ❌ Don't say: *I see you graduated from IIT, what was your CGPA?*\n"
#         "- ✅ Say: *Which institute did you graduate from?*\n\n"

#         "Keep it natural, efficient, and helpful."
#     ))

#     # Merge system message with conversation history
#     all_messages = [system_message, *state["general_messages"]]

#     # Invoke LLM
#     response = llm.invoke(all_messages)

#     print("Response from Main LLM:", response.content)

#     # Append response to conversation
#     return {"general_messages": [*state["general_messages"], response]}



# class MainState(TypedDict):
#     general_messages: Annotated[list[AnyMessage], add_messages]
    
    
# def main_model(state: MainState):
#     messages = state["general_messages"]
#     system_message = SystemMessage(content="""
#     You are the main resume assistant. 
#     Detect which section the user wants to update: education or internships.
#     If the user mentions education → call `transfer_to_education_agent`.
#     If the user mentions internships → call `transfer_to_internship_agent`.
#     Otherwise, just respond naturally.
#     """)
    
#     response = llm.bind_tools([
#         transfer_to_education_agent,
#         transfer_to_internship_agent
#     ]).invoke([system_message, *messages])

#     print("Main Agent Response:", response)

#     updated_messages = [*messages, response]

#     # Handle tool calls to avoid 400 error
#     if response.tool_calls:
#         for tool_call in response.tool_calls:
#            if tool_call["name"] == "transfer_to_education":
#             return Command(
#                 goto="education_agent",
#                 update={"general_messages": [*messages, response]}
#             )

#     return {"general_messages": updated_messages}



# # Build subgraph
# main_graph_builder = StateGraph(MainState)
# main_graph_builder.add_node("main_model", main_model)
# main_graph_builder.add_edge(START, "main_model")
# main_graph = main_graph_builder.compile()

prompt = f"""
You are the **Main Resume Assistant** in a multi-agent resume-building system.  
You are like an **elder brother or mentor**, guiding the user to create a strong, well-organized resume.  
You are the **entry point** for the user and your job is to **mentor, guide, and route**.

**Your Knowledge & Context:**  
- The overall resume is represented by the `ResumeLLMSchema`, which has sections like:  
  1. **Education** → handled by Education Agent  
  2. **Internships** → handled by Internship Agent  
  3. (Optional future) Projects, Skills, Certifications  
  4. **You should respond in short and concise sentences, don't ask a lot of questions in a single message.**.

**Resume Schema Context:**  
```json
{ json.dumps(ResumeLLMSchema.model_json_schema(), indent=2) }
```
"""


main_assistant = create_react_agent(
    name="main_assistant",
    model=llm,
    tools=[transfer_to_education_agent, transfer_to_internship_agent],
    prompt=prompt
)