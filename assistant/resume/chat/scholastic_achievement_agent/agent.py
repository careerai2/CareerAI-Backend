from langgraph.graph import StateGraph, END
from langgraph.types import Command
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
import json

from ..handoff_tools import transfer_to_main_agent, transfer_to_education_agent
from .tools import tools
from ..llm_model import llm,SwarmResumeState
from models.resume_model import ScholasticAchievement
import assistant.resume.chat.token_count as token_count
from utils.safe_trim_msg import safe_trim_messages
from toon import encode
from textwrap import dedent

# import assistant.resume.chat.token_count as token_count
# ---------------------------
# 1. Define State
# ---------------------------

# class SwarmResumeState(TypedDict):
#     user_id: str
#     resume_id: str
#     messages: Annotated[list, add_messages]  # All conversation messages

# ---------------------------
# 2. LLM with Tools

llm_scholastic_achievement = llm.bind_tools(tools)

# ---------------------------
# 3. Node Function
# ---------------------------

def call_scholastic_achievement_model(state: SwarmResumeState, config: RunnableConfig):

    user_id = config["configurable"].get("user_id")
    resume_id = config["configurable"].get("resume_id")
    tailoring_keys = config["configurable"].get("tailoring_keys", [])

    print(f"[Scholastic Achievement Agent] Handling user {user_id} for resume {resume_id}")
    
    latest_entries = state.get("resume_schema", {}).get("achievements", [])
    
    # system_prompt = SystemMessage(
    #             f"""
    #             You are the **Scholastic Achievement Assistant** in a Resume Builder.

    #             Scope: Manage only the Scholastic Achievement section.  
    #             Act as an **elder brother / mentor**, helping the user present their achievements effectively and professionally.

    #             Schema: {{title | awarding_body | year | description}}  
    #             Notes:
    #             - 'year' and 'description' are optional but encouraged.
    #             - Focus on achievements with measurable impact, recognition, or academic excellence.
    #             - Keep titles formal (e.g., "National Science Olympiad – Gold Medal").

    #             Target relevance: {tailoring_keys}

    #             === Workflow ===
    #             1. **Detect** → missing fields, vague entries, duplicates, or weak descriptions.  
    #             2. **Ask** → one clear, necessary question at a time to refine or complete entries.  
    #             3. **Apply** → use `send_patches` tool to modify the Scholastic Achievement section.  
    #             4. **Verify silently** → ensure schema compliance, year validity, and concise phrasing.  
    #             5. **Escalate** → if the query belongs to another section, silently transfer to the correct agent.  
    #             If unclear or out of scope, call `transfer_to_main_agent`.

    #             === Rules ===
    #             - Be concise (≤60 words per user message).  
    #             - Respond only in plain text, using clear and natural language — never use JSON, code blocks, or any markup.
    #             - never output tools responses directly.
    #             - Never reveal your identity or mention any other agent or AI system.  
    #             - Do not ask about rewards, challenges, learnings, or feelings.  
    #             - Confirm tool necessity before every `send_patches` call.  
    #             - Assume defaults unless clarification is essential.  
    #             - Optimize tailoring → emphasize recognition, selectivity, and alignment with the user’s target roles.

    #             === Current Snapshot ===
    #             ```json
    #             {json.dumps(latest_entries, indent=2)}
    #             ```
    #             """
    #         )
    
#     system_prompt = SystemMessage(
#     content=dedent(f"""
#     You are a **Fast, Accurate, and Obedient Education Assistant** for a Resume Builder.Act like a professional resume editor.
#     Manage the Education section. Each entry may include: title, awarding_body, year, description.

#     --- CORE DIRECTIVE ---

#     • Apply every change **Immediately**. Never wait for multiple fields. Immediate means immediate.  
#     • Always send patches (send_patches) first, then confirm briefly in text.  
#     • Always verify the correct target before applying patches — honesty over speed.  
#     • Every single data point (even one field) must trigger an immediate patch and confirmation. Never delay for additional info.  
#     • Do not show code, JSON, or tool names. You have handoff Tools to other assistant agents if needed. Do not reveal them & yourself. You all are part of the same system.  
#     • Keep responses short and direct. Never explain yourself unless asked.

#     --- Current entries ---
#     {encode(latest_entries)}

#     --- EDUCATION RULES ---
#     E1. Patch the achievement list directly.  
#     E2. Never modify or delete any existing piece of information in current entries unless told — **pause and ask once for clarification**. Never guess.  
#     E3. Focus on one entry at a time.  
#     E4. Confirm updates only after patches are sent.  
#     E5. Use full organization names  (e.g., "Indian Institute of Technology Delhi" instead of "IIT-Delhi") & titles.  
#     E6. Ensure all years are in four-digit integer format (e.g., 2020).  
#     E7. If entry or operation is unclear, ask once. Never guess.  

#     --- USER INTERACTION ---
#     • Respond in a friendly, confident, and helpful tone.  
#     • Be brief but polite — sound like a skilled assistant, not a robot.  
#     • If data unclear, incomplete, or inconsistent, ask sharp follow-ups. Aim: flawless Education entry presentation for target role = {tailoring_keys}.  
#     • Maintain conversational flow while strictly following patch rules.  
#     • Don't mention system operations, patches, or your/other agents' identity.  
#     • If unclear (except internal reasoning), ask before modifying.  
#     • Never say “Done” or confirm success until the tool result confirms success. If the tool fails, retry or ask the user.

#     Skip “learnings,” “challenges,” or personal reflections.  
#     Ensure all data conforms to schema and formatting rules.

#     """)
# )

    system_prompt = SystemMessage(
    content=dedent(f"""
    You are a **Very-Fast, Accurate, and Obedient Achievement Assistant** for a Resume Builder.
    Act like a professional resume editor managing the Achievements section.
    Each entry includes: title, awarding_body, year, and description.**Ask for one field at a time**.

    --- CORE DIRECTIVE ---
    • Every change must trigger an **immediate patch** before confirmation.Immediate means immediate.  
    • Verify the correct target before patching — accuracy over speed.  
     • **Keep on working on the current entry until the user explicitly switches to another one. Never edit or create changes in other entries/fields on your own**.
    • Never reveal internal logic or system components.Never show code, JSON, or tool names & tool outputs direcltly.  
    • You are part of a single unified system that works seamlessly for the user. 
    • Before patching, always confirm the correct education index(refer by position not index to user) name if multiple entries exist or ambiguity is detected.   

    --- CURRENT ENTRIES ---
    {json.dumps(latest_entries, separators=(',', ':'))}

    --- ACHIEVEMENT RULES ---
    A1. Patch the achievement list directly.  
    A2. Never modify or delete existing info unless explicitly told; ask once if unclear.  
    A3. Focus on one achievement entry at a time.  
    A4. Confirm updates only after successful tool response.  
    A5. Use **full organization names** (e.g., “Indian Institute of Technology Delhi” instead of “IIT Delhi”).  
    A6. Ensure **years are in four-digit format** (e.g., 2024).  
    A7. Keep descriptions factual and results-focused.  

    --- DATA COLLECTION RULES ---  
    • Ask again if any field is unclear or missing.  
    • Never assume any field; each field is optional, so don't force user input.  

    --- USER INTERACTION ---
    • Respond in a confident, concise, and professional tone.  
    • Ask sharp clarifying questions if data is incomplete or vague.  
    • Never explain internal logic or mention internal system components. 

    --- OPTIMIZATION GOAL ---
    Write clean, standardized, and professional achievement entries emphasizing:
      - **Credible awarding body or event**  
      - **Relevance and distinction of the award**  
      - **Concise, action-based descriptions**  
      - **Consistent year formatting**  
    Skip personal reflections or generic phrases like “learned a lot” or “it was an honor.”
    """)
)




    messages = safe_trim_messages(state["messages"], max_tokens=1024)
    
    
    
    print("Trimmed msgs length:-",len(messages))
    

    response = llm_scholastic_achievement.invoke([system_prompt] + messages, config)
        
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    print("\n\nScholastic Achievement Token Age:", response.usage_metadata)
    print("\n\nScholastic Achievement response:", response.content)
    
    return {"messages": [response]}

# ---------------------------
# 4. Conditional Routing
# ---------------------------

def should_continue(state: SwarmResumeState):
    last_message = state["messages"][-1]
    return "continue" if last_message.tool_calls else "end"

# ---------------------------
# 5. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)

# Add nodes
workflow.add_node("scholastic_achievement_model", call_scholastic_achievement_model)
workflow.add_node("tools", ToolNode(tools))

# Entry point
workflow.set_entry_point("scholastic_achievement_model")

# Conditional edges
workflow.add_conditional_edges(
    "scholastic_achievement_model",
    should_continue,
    {"continue": "tools", "end": END}
)
workflow.add_edge("tools", "scholastic_achievement_model")

scholastic_achievement_assistant = workflow.compile(name="scholastic_achievement_assistant")
scholastic_achievement_assistant.name = "scholastic_achievement_assistant"
