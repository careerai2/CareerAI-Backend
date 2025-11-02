from pydantic import BaseModel, Field
from typing import Optional, Union, Literal
from utils.mapper import agent_map ,Fields,resume_section_map,Section_MAPPING,FIELD_MAPPING_Bullet,Sub_Section_MAPPING
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage,HumanMessage
from .llm_model import llm
from langchain_core.runnables import RunnableConfig
from textwrap import dedent
from .utils.common_tools import retrive_entry_from_resume,apply_section_patches,extract_json_from_response,send_bullet_response,get_resume_by_threadId
import assistant.resume.chat.token_count as token_count


# KB to be changed currently internship set should be some global or change according to 
from assistant.resume.chat.internship_agent.functions import new_query_pdf_knowledge_base

class ask_agent_input(BaseModel):
    # sectionId: str
    selected_text:str
    field: Fields
    question: str
    entryIndex:int | None = None    
    

class agent_state(BaseModel):
    user_input: ask_agent_input 
    thread_id: str
    user_id: str
    entry: Optional[dict] = None
    query: Optional[str] = None
    retrieved_content: Optional[str] = None
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
    

    prompt = f"""
        You are a semantic search query generator.

        Your job: Convert resume text + user request into a concise **search query**.
        
        --- Rules ---
        • Output ONLY a query-style phrase (NOT a full sentence).  
        • Use keywords: skills, technologies, action verbs, outcomes.  
        • Do NOT rephrase into prose or statements.  
        • Keep it short, 5–12 words max.  
        • Always merge context + user request meaningfully.  
        • No filler words, quotes, or explanations.  

        --- Context (selected resume text) ---
        {highlighted_text}

        --- User Request ---
        {user_request}

        --- Full Resume Entry ---
        {entry}

        --- Examples ---
        Context: "Developed RESTful APIs using Node.js and Express; integrated database with TypeORM."
        Request: "update it to specific role"
        ✅ Query: Node.js Express TypeORM API integration backend developer

        Context: "Led a team of 5 to build a ML pipeline for fraud detection."
        Request: "make it sound more leadership-focused"
        ✅ Query: machine learning fraud detection team leadership project management

        Now generate ONLY the query for the above context + request.
    """
    
    messages = [
    SystemMessage(content="You are a semantic search query generator."),
    HumanMessage(content=prompt)  # your full prompt goes here
]


    response = llm.invoke(messages, config=config)

    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

    print("Query Generator Token Usage:", response.usage_metadata)
    print("Generated Query:", response.content)

    return {"query": response.content.strip()}






# Node 3: Retriever (function)
async def retriever(state: agent_state, config: RunnableConfig):
    try:
        query = state.query
        user_input = state.user_input
        print("QUERY", query)
        field = resume_section_map(user_input.field)
        
        Section = Section_MAPPING.get(f"{field}")
        SubSection = Sub_Section_MAPPING.get(f"{field}")
        print("FIELD", field)
        print("Section =", Section)
        print("SubSection =", SubSection)
        print("Field =", FIELD_MAPPING_Bullet.get(f"{field}",None))

        relevant_content = new_query_pdf_knowledge_base(
            query_text=str(query),
            role=["internship"],
            section=Section,
            subsection=SubSection,
            field=FIELD_MAPPING_Bullet.get(f"{field}",None),
            n_results=5,
            debug=False
        )

        print("\n\nRelevant Content", relevant_content)
        return {"retrieved_content": relevant_content}
    except Exception as e:
        print("Error in retriever:", e)
        return {"retrieved_content": None}


# Node 4: Patch Generator (LLM)
async def response_generator(state: agent_state, config: RunnableConfig):
    content = state.retrieved_content
    entry = state.entry
    user_id = state.user_id
    user_req = state.user_input.question
    
    if state.user_input.field == Fields.Summary:
        content = "Focus on concise, impactful language that highlights key skills and experiences relevant to the target role."
        
        entry = get_resume_by_threadId(state.thread_id)


# The action verbs can be changed according to the section  of resume will be imported later for now only internship
    prompt_genaral = SystemMessage(content=dedent(f"""
        You are an **Enhancer Agent**.

        Your ONLY task is to produce an enhanced version of the Selected Bullet (given below) based on the user's request and the retrieved guidelines, so that it best fits within the context of the entry (Current Entry).

        ### Selected Bullet of the Entry **(Only return the Enhanced version of it)**
        {state.user_input.selected_text}
        
        Do **not** explain, justify, comment, or include any text outside the enhanced version itself.

        ---
        ### Rules
        • Always output only the enhanced text (no explanations or formatting).  
        • Never output prose, reasoning, or JSON.  
        • Maintain factual accuracy and consistent tone with the rest of the entry.  
        • Use concise, impactful language aligned with professional writing standards.
        
           ---
        ### Retrieved Guidelines
        {content}

        ###user Request
        {state.user_input.question}

        ### Current Entry
        {entry}
     
        """))

    prompt_for_summary = SystemMessage(content=dedent(f"""
    You are an **Enhancer Agent** specialized in professional resume writing.

    Your task is to craft a **powerful, concise, and professional summary paragraph (maximum 150 words)** that captures the essence of the candidate’s resume and aligns with the user’s request.

    Use the entire resume as context but **output only the enhanced summary** — written in a confident, impactful tone suited for top internship or job applications.

    ---

    ### Inputs
    **User’s Current Summary**
    {state.user_input.selected_text}

    **User’s Request**
    {state.user_input.question}

    **Retrieved Guidelines**
    {content}

    **Full Resume**
    {entry}

    ---

    ### Rules
    • Output only the enhanced **summary paragraph** — no lists, bullets, JSON, or extra text.  
    • Word limit: **≤150 words.**  
    • Keep all details factual; do not invent experiences or skills.  
    • Tone: strong, polished, and results-oriented.  
    • Style: clear, professional, and engaging; avoid repetition or fluff.  
    • Do not explain or justify your output.

    ---

    Now, generate the **enhanced 150-word summary paragraph** representing the candidate’s overall professional profile.
    """))



    
    prompt = prompt_genaral if state.user_input.field != Fields.Summary else prompt_for_summary
    
    print("\n\nPatch Generator Prompt:", prompt,"\n\n\n")

    response = llm.invoke([prompt, HumanMessage(content=user_req)], config=config)
    

    print("\nPatch Generator Metadata:", response.usage_metadata)
    print("Patch Generator", response)

    token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
    token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
    
    if(response.content):
        await send_bullet_response(user_id=user_id,res=response.content)
    else:
        await send_bullet_response(user_id=user_id,res="Sorry, I couldn't generate a response. Please try again.")

        





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
graph.add_node("response_generator", response_generator)




# Connect nodes
graph.add_edge("retrieve_entry", "query_generator")
graph.add_edge("query_generator", "retriever") 
graph.add_edge("retriever", "response_generator")


graph.set_entry_point("retrieve_entry")


pipeline = graph.compile()


async def call_model(user_input: str,thread_id:str,user_id:str):
    try:
        print("\n\nUser Input",user_input,"\n\n")

        await pipeline.ainvoke({"user_input": user_input,"thread_id":thread_id,"user_id":user_id}, config=RunnableConfig(max_retries=1))
    except Exception as e:
        print("Error during graph execution:", e)

