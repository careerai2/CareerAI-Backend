from langchain_openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# llm = ChatOpenAI(model="gpt-4.1")

# # Create a Gemini Flash instance
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    # model="gemini-2.5-flash",  # 
    # model="gemini-2.5-flash-lite-preview-09-2025",  # 
    model="gemini-2.5-flash-lite",  # 
    temperature=0,
    max_output_tokens=1024
)




# from langchain_openai import ChatOpenAI

# llm = ChatOpenAI(
#     model="gpt-5-nano",   # ✅ or "gpt-5-nano" if your account has access
#     # temperature=0,
#     max_tokens=1024
# )


from typing_extensions import TypedDict, Annotated
from models.resume_model import ResumeLLMSchema
from langchain_core.messages import AnyMessage, SystemMessage,HumanMessage,AIMessage
from langgraph_swarm import SwarmState
from langgraph.graph import StateGraph, MessagesState, START,END,add_messages

from models.resume_model import Internship

from typing import Optional,Union,Literal
from pydantic import BaseModel,Field

class InternshipState(BaseModel):
    generated_query: Optional[str] = None
    save_node_response: Optional[str] = None
    retrieved_info: Optional[str] = None
    index: Optional[int] = None
    patches: Optional[list[dict]] = Field(default_factory=list)
   
class WorkexState(BaseModel):
    generated_query: Optional[str] = None
    save_node_response: Optional[str] = None
    retrieved_info: Optional[str] = None
    index: Optional[int] = None
    patches: Optional[list[dict]] = Field(default_factory=list)
   



class SwarmResumeState(SwarmState):
    messages: Annotated[list[AnyMessage], add_messages]
    resume_schema: ResumeLLMSchema
    internship: InternshipState
    workex: WorkexState 
