from langgraph.runtime import get_runtime
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from assistant.resume.chat.tools import education_Tool, get_resume
from .handoff_tools import transfer_to_main_agent, transfer_to_internship_agent
import json
from models.resume_model import Education
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI


# llm = ChatOpenAI(model="gpt-4.1")

from langchain_google_genai import ChatGoogleGenerativeAI

# Create a Gemini Flash instance
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Use gemini-1.5-pro for higher reasoning
    temperature=0,             # Optional: control creativity
    max_output_tokens=1024     # Optional: control output length
)



# # ----------------- STATE -----------------
# class EducationState(TypedDict):
#     education_messages: Annotated[list[AnyMessage], add_messages]

# # ----------------- NODE FUNCTION -----------------
# def education_model(state: EducationState):
#     runtime = get_runtime()
#     user_id = runtime.context.get("user_id")
#     resume_id = runtime.context.get("resume_id")
    
#     resume = get_resume(user_id, resume_id)
#     edu_schema = Education.model_json_schema()

#     # System message
#     system_prompt = SystemMessage(
#         content=f"""
# You are an assistant that helps users add and update their education section in a resume.

# ## 🎯 Objective
# Engage with the user naturally to collect or confirm education information.
# Once the user provides an education entry, you MUST update the resume using the correct tool and format.

# ## 👤 User Context
# - User ID: {user_id}
# - Resume ID: {resume_id}
# - Current Resume Data:
# {json.dumps(resume, indent=2)}

# ---

# ## 🚨 Priority Rules
# 1. ✅ TOOL USAGE ON EDUCATION ENTRY
# - Call `update_resume_fields` whenever the user provides education details.
# - Ask natural follow-up questions if info is missing.
# - Submit even partial entries via the tool.

# 2. 🧩 Strict Schema Format
# Use the following schema for tool calls:
# {json.dumps(edu_schema, indent=2)}
# """
#     )

#     # Merge system + conversation messages
#     all_messages = [system_prompt, *state["education_messages"]]

#     # Invoke LLM with tools
#     response = llm_with_education_tools.invoke(all_messages)
#     print("Response from Education LLM:", response)

#     # Return updated message history
#     return {"education_messages": [*state["education_messages"], response]}

# # ----------------- SUBGRAPH -----------------
# subgraph_builder = StateGraph(EducationState)
# subgraph_builder.add_node("education_model", education_model)
# subgraph_builder.add_edge(START, "education_model")

# subgraph = subgraph_builder.compile()


# class EducationState(TypedDict):
#     education_messages: Annotated[list[AnyMessage], add_messages]

# def education_model(state: EducationState):
#     messages = state["education_messages"]
#     system_message = SystemMessage(content="""
#     You are the education assistant. 
#     Collect the user's education details naturally.
#     If user starts talking about internships → call `transfer_to_internship_agent`.
#     """)
#     print("Education Messages :----------------------------------")
    
#     response = llm.bind_tools([transfer_to_internship_agent,transfer_to_main_agent]) \
#                   .invoke([system_message, *messages])
#     print("Education Agent Response:", response.content)
#     return {"education_messages": [*messages, response]}

# edu_graph_builder = StateGraph(EducationState)
# edu_graph_builder.add_node("education_model", education_model)
# edu_graph_builder.add_edge(START, "education_model")
# education_graph = edu_graph_builder.compile()

import json
prompt = f"""
You are the **Education Assistant** for a Resume Builder application.  
You act as an **elder brother / mentor**, helping the user build a strong **Education** section for their resume.  

---

### 🎯 Your Responsibilities:
1. **Guide the User**
   - Explain briefly what makes a good education entry.
   - Examples of tips:
     - "Include degree, institute, and start & end years."
     - "Adding CGPA or % strengthens the entry."
     - "Mention key achievements, awards, or notable coursework."

2. **Collect & Organize Educational Info**
   - Follow the **Education Schema** strictly.
   - If the user provides **partial info**, create a **draft entry immediately** using the `education_tool`.
   - Continue to **update the same entry** as the user provides new info.

3. **Real-Time DB Updates via Tool**
   - **Always call the `education_tool`** with JSON input strictly following its schema.
   - **Key Rule → Always include the `index` field**:
     - `null` when adding the first entry.
     - Integer (0,1,2,...) for updates of existing entries.
   - Never return a Python object; **return JSON strictly**.

4. **Conversation Style**
   - Be concise.
   - Ask **one question at a time** to fill missing info.

---

### 📦 Education Schema:
```json
{ json.dumps(Education.model_json_schema(), indent=2) }

```
"""


education_assistant = create_react_agent(
    name="education_assistant",
    model=llm,
    tools=[transfer_to_internship_agent, transfer_to_main_agent, education_Tool],
    prompt=prompt,
)
