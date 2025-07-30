from fastapi import WebSocket
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage,SystemMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver 
from assistant.resume.chat.tools import tools,get_resume
from assistant.resume.chat.llm import State,llm
from langgraph.prebuilt import ToolNode,tools_condition
from assistant.resume.chat.llm import chatbot,education_chatbot,internship_chatbot,workex_and_project_chatbot,position_and_extracurricular_achievements_chatbot
from assistant.config import redis_client as r
import json
import re



memory = InMemorySaver()
# from langgraph.checkpoint.redis import RedisSaver,AsyncRedisSaver



def detect_section(text: str) -> str:
    """
    Lightweight and reliable section classifier using regex for MVP.
    Supports: education, internship, workex_and_project, position_and_extracurricular_achievements
    """
    text = text.lower()

    section_patterns = {
        "education": [
            r"\beducat", r"\bcollege\b", r"\buniversity\b", r"\bcgpa\b", r"\bsgpa\b",
            r"\bdegree\b", r"\b\d{4}\b", r"\b(b\.?tech|m\.?tech|bachelor|master|phd)\b",
            r"\bstud(y|ied|ying)\b", r"\bgraduat(ed|ion)\b", r"\bcourse\b", r"\bbranch\b",
        ],
        "internship": [
            r"\bintern(ship|ed|ing)?\b", r"\btraining\b", r"\bsummer\b", r"\bwinter\b",
            r"\bindustrial\b", r"\bstipend\b",
        ],
        "workex_and_project": [
            r"\bwork\b", r"\bexperience\b", r"\b(project|projects)\b",
            r"\bdevelop(ed|ing)?\b", r"\bbuilt\b", r"\bcreated\b", r"\bteam\b",
            r"\bresponsib(le|ility|ilities)\b", r"\btools?\b",
        ],
        "position_and_extracurricular_achievements": [
            r"\bposition\b", r"\bleader(ship)?\b", r"\bco-?ordinator\b", r"\bhead\b",
            r"\bextra(curricular)?\b", r"\bclub\b", r"\bevent\b", r"\borganize(d|r)?\b",
            r"\bachiev(ement|e)?\b", r"\bwon\b", r"\bcompetition\b", r"\bvolunteer\b",
        ],
    }

    for section, patterns in section_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return section

    return "default"

def chatbot_router(state: State) -> str:
    try:
        last_message = state["messages"][-1].content
    except Exception:
        return END

    section = detect_section(last_message)
    state["last_section"] = section

    route = {
        "education": "education_chatbot",
        "internship": "internship_chatbot",
        "workex_and_project": "workex_and_project_chatbot",
        "position_and_extracurricular_achievements": "position_and_extracurricular_achievements_chatbot"
    }.get(section, END)

    print(f"[ROUTER] Detected Section: {section} → Routing to: {route}")
    return route




def return_to_last_section(state: State) -> str:
    return {
        "education": "education_chatbot",
        "internship": "internship_chatbot",
        "workex_and_project": "workex_and_project_chatbot",
        "position_and_extracurricular_achievements": "position_and_extracurricular_achievements_chatbot"
    }.get(state.get("last_section", ""), END)




graph_builder = StateGraph(State)

tool_node = ToolNode(tools)
# Add nodes
graph_builder.add_node("chatbot", chatbot)  # sync
graph_builder.add_node("education_chatbot", education_chatbot) 
graph_builder.add_node("internship_chatbot", internship_chatbot)   
graph_builder.add_node("workex_and_project_chatbot", workex_and_project_chatbot)
graph_builder.add_node("position_and_extracurricular_achievements_chatbot", position_and_extracurricular_achievements_chatbot)


graph_builder.add_node("tools", tool_node)  # async-aware tool node

# Conditional routing from chatbot -> education_chatbot or others
graph_builder.add_conditional_edges("chatbot", chatbot_router)

# Now connect the education_chatbot to tools node conditionally
graph_builder.add_conditional_edges("education_chatbot", tools_condition)
graph_builder.add_conditional_edges("internship_chatbot", tools_condition)
graph_builder.add_conditional_edges("workex_and_project_chatbot", tools_condition)
graph_builder.add_conditional_edges("position_and_extracurricular_achievements_chatbot", tools_condition)

# Tool node always routes back to last used section after execution
graph_builder.add_conditional_edges("tools", return_to_last_section)

# Start from chatbot
graph_builder.add_edge(START, "chatbot")


graph = graph_builder.compile(checkpointer=memory)


async def stream_graph_to_websocket(user_input: str, thread_id: str, websocket: WebSocket, user_id: str):
    """
    Streams LangGraph outputs to the client via WebSocket.
    """
    # checkpointer = await AsyncRedisSaver.from_conn_string(REDIS_URI)

    config = {"configurable": {"thread_id": thread_id}}  # to add checkpointing support

    initial_state = {
    "messages": [
        SystemMessage(content=(
        "## 🧠 Role\n"
        "You are a concise, intelligent, and friendly assistant designed to **help users build their resume through natural conversation**. "
        "You operate as part of a multi-step intelligent system that routes users to specialized modules like *education*, *internships*, or *projects*, depending on the context of the message.\n\n"

        "## 🎯 Objective\n"
        "Your primary goal is to **extract and clarify resume information from the user** in a human-like way. "
        "You should never fabricate or assume content. Always guide the user in small steps to get accurate and meaningful inputs.\n\n"

        "## 🧭 Flow & Routing\n"
        "- Start the conversation with the user and understand their intent.\n"
        "- Based on the user's message, the system will detect which resume section they're referring to (e.g., Education, Internship).\n"
        "- Once detected, the conversation will be routed to a **specialized chatbot module** for that section ***AND U DON'T NEED TO RESPOND IN SUCH CASE****\n"
        "- If tools (functions) are required, they will be invoked and results will be streamed back.\n"
        "- After tool execution, control will return to the specialized section chatbot.\n\n"

        "## 🛠️ Behavior Rules\n"
        "- Speak in short, simple, friendly sentences.\n"
        "- Ask **only one question at a time**.\n"
        "- Avoid markdown or bullet points in *user-facing* responses.\n"
        "- Never fabricate resume data.\n"
        "- If the user's message isn’t clear, help them rephrase it.\n"
        "- Focus only on clarifying user input; let the specialized modules handle the actual resume-building logic.\n\n"

        "## 📌 Example Behavior\n"
        "- ❌ Don't say: *I see you graduated from IIT, what was your CGPA?*\n"
        "- ✅ Say: *Which institute did you graduate from?*\n\n"

        "Keep it natural, efficient, and helpful."
    )),
        HumanMessage(content=user_input)
    ],
    "resume": get_resume(user_id),
    "user_id": user_id
}




    async for event in graph.astream(initial_state, config=config):
        for value in event.values():
            content = value["messages"][-1].content
            if content and len(content) > 0:
                await websocket.send_json({"type": "message", "message": content})
