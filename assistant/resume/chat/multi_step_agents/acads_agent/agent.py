
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from config.log_config import get_logger
from config.env_config import show_acads_logs,MAX_TOKEN
from utils.safe_trim_msg import safe_trim_messages
import assistant.resume.chat.token_count as token_count

from ...utils.common_tools import extract_json_from_response,get_patch_field_and_index
from ...utils.apply_patches import apply_patches_global
from ...llm_model import llm,SwarmResumeState
from ...utils.field_mapping import ACADS_FIELD_MAPPING

from .tools import tools,transfer_tools
from .prompts import Acads_Prompts
from .routers import acads_model_router 
from .functions import new_query_pdf_knowledge_base
# from assistant.resume.chat.utils.query_vector_db im/port new_query_pdf_knowledge_base



# ---------------------------
# 2. LLM with Tools
# ---------------------------

llm_tools = [*tools, *transfer_tools]

llm_acads = llm.bind_tools(llm_tools)
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed


default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")

logger = get_logger("Acads_Agent")



instruction = {
    "project_name": "Use a concise, descriptive title. | Apply Title Case. | Limit to 3–6 words. | Example: **Automated Traffic Analysis System.**",
    "project_description": "- Limit to 1–2 lines max. | Clearly explain the project purpose, scope, or problem addressed. | Avoid vague or marketing-like statements. | Example: *Developed a machine learning model to predict traffic congestion using real-time sensor data.*  ",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jan 2024 – Apr 2024.*",
  }





# --------------------------- Main Model ---------------------------
async def acads_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for Por assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("academic_projects", [])
    
    error_msg = state.get("acads", {}).get("error_msg", None)
    
    if error_msg:
        logger.error(f"⚠️ Internship patch failed with error: {error_msg}")

        recovery_prompt = Acads_Prompts.get_recovery_prompt(error_msg,state["acads"].get("patches", []))
        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        
        response = await llm_acads.ainvoke([recovery_prompt], config)
        
        if show_acads_logs:
            logger.info(f"Acad_model (error recovery) response: {response.content}")
            
         # Reset error so it doesn’t loop forever
        state["acads"]["error_msg"] = None

        return {
            "messages": [response],
            "acads": {
                    "error_msg": None,
                }
            }
    
    try:
 
        prompt = Acads_Prompts.get_main_prompt(current_entries,tailoring_keys)
        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)

        response = llm_acads.invoke([prompt] + messages, config)
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        if show_acads_logs:
            logger.info(f"Acad_model response:\n {response.content}\n\n")
            logger.info(f"Acad_model Token Usage:\n {response.usage_metadata}")
 
        
        
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error in acads_model:\n {e}")
        return {"messages": [AIMessage(content="Sorry! can you repeat")],"next_node": END}





# -------------------------- Query Generator Model --------------------------
async def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("academic_projects", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("acads", {}).get("patches", [])
   

    prompt = Acads_Prompts.get_query_prompt(patches,tailoring_keys)

 

    try:

        # Call the retriever LLM
        response = await llm_retriever.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        if response.content.strip():
            state["acads"]["generated_query"] = str(response.content)
        else:
            state["acads"]["generated_query"] = ""
            
        if show_acads_logs:
            logger.info(f"Query generated:\n {response.content}\n")
            logger.info(f"Query generator Token Usage: \n {response.usage_metadata}")

    except Exception as e:
        logger.error(f"Error in query generator : {e}")
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}





# ------------------------- Knowledge Base Retriever Node ---------------------------
async def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("acads", {}).get("generated_query", [])
        patches = state.get("acads", {}).get("patches", [])
        
        # print("Por in retriver node",state["acads"])
        
        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            print("No query generated, skipping retrieval.")
            state["acads"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

        # Collect all unique fields to avoid redundant fetches
        unique_fields = set()
        for patch in patches:
            _, patch_field, _ = get_patch_field_and_index(patch.get("path", ""))
            unique_fields.add(patch_field)
            
        if show_acads_logs:
            logger.info(f"\n🔍 Unique fields to retrieve: {unique_fields}\n")

        all_results = []
        
        retrieved_info = None

        # Loop over each patch
        for i, field in enumerate(unique_fields):
            
            kb_field = ACADS_FIELD_MAPPING.get(field,None)

            if show_acads_logs:
                 logger.info(f"\n🔍 Patch {i+1}: field={field}, KB field={kb_field}")

            
            retrieved_info = None  # initialize here to avoid UnboundLocalError

            if field == "description_bullets" and kb_field is not None:
                
                section = "Academic Project Document Formatting Guidelines"
                
                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(query),  # query string
                    logger=logger,
                    # collection_name="acads_guide_doc",
                    role=["acads"],
                    section=section,
                    subsection="Action Verbs (to use in work descriptions)",
                    field=kb_field,
                    n_results=5,
                    debug=show_acads_logs
                )
                all_results.append(f"[Action Verbs] => {retrieved_info}")

                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(query),  # use patch value as query
                    role=["acads"],
                    section=section,
                    subsection="Schema Requirements & Formatting Rules",
                    field=kb_field,
                    n_results=5,
                    debug=show_acads_logs
                )
                all_results.append(f"[{patch_field}] {retrieved_info}")

            else:
                retrieved_info = instruction.get(patch_field, '')
                all_results.append(f"[{patch_field}] {retrieved_info}")

            logger.info(f"Retriever returned {retrieved_info} results for patch {i+1}.\n")


        all_results = "\n".join(all_results)
        
        # Save everything back
        state["acads"]["retrieved_info"] = all_results
        # state["acads"]["last_query"] = queries
        state["acads"]["generated_query"] = ""  # clear after use

        if show_acads_logs:
            logger.info(f"\n✅ Retrieved info saved: {all_results} \n\n")
            
    except Exception as e:
        logger.error(f"Error in retriever: {e}")
        # they are not working have to use conditional router
        return Command(
            goto="acads_model",          # returns control to the same node that called this tool
            update={
                "messages": [AIMessage(content=f"Error while applying patches due to the error {e}.Don't show the user this msg directly handle user accordingly")],   # required for _validate_tool_command
            },
        )





# --------------------------- Builder Model --------------------------
async def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine acads patches using retrieved info."""
    try:
        
        
        retrieved_info = state.get("acads", {}).get("retrieved_info", "")
        patches = state.get("acads", {}).get("patches", [])
        

        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            logger.warning("No retrieved info available, skipping building.")
            return 

        prompt = Acads_Prompts.get_builder_prompt(retrieved_info,patches)

            
        response = await llm_builder.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        # Extract refined patches from LLM output
        refined_patches = extract_json_from_response(response.content)
        
        if show_acads_logs:
            logger.info(f"\n\nBuilder produced refined patches:\n {refined_patches}\n")
            logger.info(f"Builder_model token usage:\n {response.usage_metadata}\n")

        # Replace patches in state
        if refined_patches is not None and not isinstance(refined_patches, list) and len(refined_patches) > 0:
            state["acads"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["acads"]["patches"] = refined_patches

    except Exception as e:
        logger.error(f"Error in builder_model: {e}")
        return Command(
            goto="acads_model",          # returns control to the same node that called this tool
            update={
                "messages": [AIMessage(content=f"Error while applying patches due to the error {e}.Don't show the user this msg directly handle user accordingly")],   # required for _validate_tool_command
            },
        )





# --------------------------- Save Entry Node ---------------------------
async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update acads entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("acads", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("acads", {}).get("patches", [])
        

        result = await apply_patches_global(thread_id, patches,"academic_projects")

        if show_acads_logs:
            logger.info(f"\nApply patches result : {result}\n")
        
        if result and result.get("status") == "success":           
            return {
                "messages": [AIMessage(content="Patches applied successfully.")],   
                "acads":{
                    "error_msg": None,
                    "patches": [],
                }
            }
        
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return Command(
                goto="acads_model",
                update={
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                }
            )

    except Exception as e:
        logger.error(f"Error in save_entry_state: {e}")
        return Command(
            goto="acads_model",          # returns control to the same node that called this tool
            update={
                "messages": [AIMessage(content=f"Error while applying patches due to the error {e}.Don't show the user this msg directly handle user accordingly")],   # required for _validate_tool_command
            },
        )
    


# ---------------------------
# 6. Create Graph
# ---------------------------
workflow = StateGraph(SwarmResumeState)

# Tool nodes for each model
acads_tools_node = ToolNode(llm_tools)         # For acads_model

# Nodes
workflow.add_node("acads_model", acads_model)  
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)

# Tool Nodes
workflow.add_node("tools_acads", acads_tools_node)

workflow.set_entry_point("acads_model")

# Conditional routing
workflow.add_conditional_edges(
    "acads_model",
    acads_model_router,
    {
        "tools_acads": "tools_acads",         
        END: END
    }
)

# Edges
# workflow.add_edge("tools_acads", "acads_model")  # return to acads
workflow.add_edge("query_generator_model", "retriever_node")  
workflow.add_edge("retriever_node","builder_model") 
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "acads_model")

# Compile
acads_assistant = workflow.compile(name="acads_assistant")
acads_assistant.name = "acads_assistant"

