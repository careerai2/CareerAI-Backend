from pydantic import BaseModel, Field
from typing import Optional, Union, Literal
from utils.mapper import agent_map ,Fields,resume_section_map
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage,HumanMessage
from .llm_model import llm
from langchain_core.runnables import RunnableConfig
from textwrap import dedent
from .utils.common_tools import retrive_entry_from_resume,apply_section_patches,extract_json_from_response
import assistant.resume.chat.token_count as token_count


# KB to be changed currently internship set should be some global or change according to 
from assistant.resume.chat.internship_agent.functions import query_pdf_knowledge_base

class ask_agent_input(BaseModel):
    # sectionId: str
    selected_text:str
    field: Fields
    question: str
    entryIndex:int | None = None    
    

class agent_state(BaseModel):
    user_input: ask_agent_input 
    thread_id: str
    entry: Optional[dict] = None
    query: Optional[str] = None
    retrieved_content: Optional[str] = None
    patch: list[dict] = None
    updated_entry: Optional[dict] = None




# -------------------------------
# 2. Node definitions
# -------------------------------



# Node 1: Retrieve Entry (function)
async def retrieve_entry(state: agent_state, config: RunnableConfig):
    thread_id = state.thread_id
    user_input = state.user_input
    section = resume_section_map(user_input.field)
    if(section=="None"):
        # add router so that end occurs END
        return 
    entry = await retrive_entry_from_resume(thread_id, section, user_input.entryIndex)

    print("\n\n\nRetrieved entry",entry)
    return {"entry": entry}



async def query_generator(state: agent_state, config: RunnableConfig):
    highlighted_text = state.user_input.selected_text
    user_request = state.user_input.question
    entry = state.entry

    prompt = SystemMessage(content=dedent(f"""
        You are a semantic search query generator.

        Context (selected entry from resume): {highlighted_text}

        User Request: {user_request}

        Full Resume Entry: {entry}

        Task: 
        - Extract key action verbs, skills, technologies, or accomplishments from the context.
        - Combine them with the user's request to create a concise, **highly relevant search query**.
        - Keep it in 1–2 sentences.
        - Do not add explanations, filler text, or quotes—only the final query.

        Example:
        Context: "Developed RESTful APIs using Node.js and Express; integrated database with TypeORM."
        User Request: "update it to specific role"
        Output Query: "Node.js Express TypeORM developer API integration"

        Now generate the query for the above context and user request.
    """))

    response = llm.invoke([prompt, HumanMessage(content=user_request)], config=config)
    
    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    print("\nGenerator Query Metadata:", response.usage_metadata)

    print("Generated Query:", response.content)
    
    return {"query": response.content}





# Node 3: Retriever (function)
async def retriever(state:agent_state,config:RunnableConfig):
    query = state.query
    # Maybe extract last messages or relevant fields
    print("QUERY",query)
    
    relevant_content = query_pdf_knowledge_base(query_text=query)

    print("\n\relevant Content",relevant_content)
    return {"retrieved_content": relevant_content}


# Node 4: Patch Generator (LLM)
async def patch_generator(state: agent_state, config: RunnableConfig):
    content = state.retrieved_content
    entry = state.entry
    user_req = state.user_input.question

    prompt = SystemMessage(content=dedent(f"""
    You are a **Resume Patch Generator**.

    Your ONLY task is to output **valid JSON Patch operations (RFC 6902)**.  
    You MUST return one and only one operation **only for the selected part of the entry**.  
    Do not explain, comment, or add any text outside of the JSON Patch.  

    --- Rules ---
    • Always output a valid JSON array.  
    • Use `replace` for updating existing fields.  
    • Use `add` with `/internship_work_description_bullets/-` to append new bullets.  
    • Keep patches minimal — only change what is necessary.  
    • If no relevant retrieved content exists, still create a patch that fulfills the user request.  
    • Never output prose, reasoning, or anything outside JSON.  

    --- Example ---
      1. {{ "op": "replace", "path": "/company_name", "value": "Google" }},
      2. {{ "op": "add", "path": "/internship_work_description_bullets/-", "value": "Implemented ML pipeline" }}

    --- Retrieved Content ---
    {content}
    
    --- selected part of the entry(ONLY MODIFY THIS)** ---
    {state.user_input.selected_text}

    --- Current Entry ---
    {entry}
    """))


    response = llm.invoke([prompt, HumanMessage(content=user_req)], config=config)

    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    patch = extract_json_from_response(response.content)

    print("\nPatch Generator Metadata:", response.usage_metadata)
    print("Patch Generator", patch)
    
    if isinstance(patch, list):
        patch = patch[0]  # Wrap single dict in a list
        
    return {"patch": [patch]}



# Node 5: Apply Patch (function)
async def apply_patch(state: agent_state, config: RunnableConfig):
    
    patch = state.patch
    thread_id = state.thread_id
    section = resume_section_map(state.user_input.field)
    index = state.user_input.entryIndex
    await apply_section_patches(thread_id=thread_id, section=section, patches=patch, index=index)
    # Apply patch logic here
    print("Applying patch:", patch)
    



# -------------------------------
# 3. Create LangGraph nodes
# -------------------------------

# -------------------------------
# 4. Define graph edges (data flow)
# -------------------------------
graph = StateGraph(agent_state)

graph.add_node("query_generator", query_generator)
graph.add_node("retrieve_entry", retrieve_entry)
graph.add_node("retriever", retriever)
graph.add_node("patch_generator", patch_generator)
graph.add_node("apply_patch", apply_patch)



# Connect nodes
graph.add_edge("retrieve_entry", "query_generator")
graph.add_edge("query_generator", "retriever") 
graph.add_edge("retriever", "patch_generator")
graph.add_edge("patch_generator", "apply_patch")


graph.set_entry_point("retrieve_entry")


pipeline = graph.compile()


async def call_model(user_input: str,thread_id:str):
    try:
        print("\n\nUser Input",user_input,"\n\n")

        await pipeline.ainvoke({"user_input": user_input,"thread_id":thread_id})
    except Exception as e:
        print("Error during graph execution:", e)

