from langgraph.runtime import get_runtime
from typing_extensions import TypedDict, Annotated, runtime
from langchain_core.messages import AnyMessage,SystemMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from .handoff_tools import transfer_to_main_agent,transfer_to_education_agent
from .tools import internship_Tool
from models.resume_model import Internship


# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI(model="gpt-4.1")

from langchain_google_genai import ChatGoogleGenerativeAI

# Create a Gemini Flash instance
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Use gemini-1.5-pro for higher reasoning
    temperature=0,             # Optional: control creativity
    max_output_tokens=1024     # Optional: control output length
)



##### WILL LATER MADE A CUSTOM GRAPH for internship agent

# llm_with_internship_tools = llm.bind_tools(tools_internship)

# class InternshipState(TypedDict):
#     internship_messages: Annotated[list[AnyMessage], add_messages]

# def internship_model(state: InternshipState):
#     messages = state["internship_messages"]
#     system_message = SystemMessage(content="""
#     You are the internship assistant.
#     Collect internship experience.
#     If user starts talking about education → call `transfer_to_education_agent`.
#     """)
#     response = llm.bind_tools([transfer_to_main_agent,transfer_to_education_agent]) \
#                   .invoke([system_message, *messages])
#     print("Internship Agent Response:", response.content)
#     return {"internship_messages": [*messages, response]}

# internship_graph_builder = StateGraph(InternshipState)
# internship_graph_builder.add_node("internship_model", internship_model)
# internship_graph_builder.add_edge(START, "internship_model")
# internship_graph = internship_graph_builder.compile()

import json
prompt = f"""
You are the **Internship Assistant** for a Resume Builder application.  
You act as an **elder brother / mentor**, helping the user build a strong **Internship** section for their resume.  

---

### 🎯 Your Responsibilities:
1. **Guide the User**
   - Briefly explain what makes a strong internship entry.
   - Example tips:
     - "Include company name, role, duration, and location."
     - "Highlight at least 1-2 impactful tasks or achievements."
     - "Focus on contributions that show skills or measurable results."

2. **Collect & Organize Internship Info**
   - Follow the **Internship Schema** strictly.
   - If the user provides **partial info**, immediately create a **draft entry** using the `internship_tool`.
   - Continue to **update the same entry** as the user provides new info.

3. **Real-Time DB Updates via Tool**
   - **Always call the `internship_tool`** with JSON input strictly following its schema.
   - **Key Rule → Always include the `index` field**:
     - `null` when adding the first entry.
     - Integer (0,1,2,...) for updates of existing entries.
   - Never return a Python object; **return JSON strictly**.

4. **Conversation Style**
   - Keep responses concise.
   - Ask **one question at a time** to fill missing details.
   - Continue the conversation until the entry is complete.

---

### 📦 Internship Schema:
```json
{ json.dumps(Internship.model_json_schema(), indent=2) }

```
"""



internship_assistant = create_react_agent(
    name="internship_assistant",
    model=llm,
    tools=[transfer_to_main_agent, transfer_to_education_agent, internship_Tool],
    prompt=prompt,
)
