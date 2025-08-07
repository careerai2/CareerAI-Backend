from langchain_openai import ChatOpenAI


# llm = ChatOpenAI(model="gpt-4.1")

from langchain_google_genai import ChatGoogleGenerativeAI

# Create a Gemini Flash instance
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # ✅ Correct model name
    temperature=0,
    max_output_tokens=1024
)


from typing_extensions import TypedDict, Annotated
from models.resume_model import ResumeLLMSchema
from langchain_core.messages import AnyMessage, SystemMessage,HumanMessage,AIMessage
from langgraph_swarm import SwarmState
from langgraph.graph import StateGraph, MessagesState, START,END,add_messages

class SwarmResumeState(SwarmState):
    messages: Annotated[list[AnyMessage], add_messages]
    resume_schema: ResumeLLMSchema
    user_id: str
    resume_id: str
