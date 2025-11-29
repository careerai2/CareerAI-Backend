from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from ...llm_model import llm,SwarmResumeState
from .tools import tools
from utils.safe_trim_msg import safe_trim_messages
from ...utils.common_tools import extract_json_from_response,get_patch_field_and_index
from ...utils.apply_patches import apply_patches_global
import assistant.resume.chat.token_count as token_count
from .functions import new_query_pdf_knowledge_base
from ...utils.field_mapping import FieldMapping
# from .mappers import FIELD_MAPPING
from .prompts import POR_Prompts
from config.log_config import get_logger
from config.env_config import show_por_logs
from .routers import por_model_router
# from assistant.resume.chat.utils.query_vector_db import new_query_pdf_knowledge_base


# ---------------------------
# 2. LLM with Tools
# ---------------------------

MAX_TOKENS = 325



llm_por = llm.bind_tools(tools)  
llm_builder = llm  
llm_retriever = llm


logger = get_logger("POR_Agent")



default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")


instruction = {
    "role": "Write the exact position title. | Capitalize each word. | Example: **Event Coordinator.**",
    "role_description": "Limit to 1–2 lines max. | Clearly describe the purpose scope of the role. | Example: *Coordinated logistics and scheduling for technical workshops.*",
    "organization" : "Use the official registered name only. | Avoid abbreviations unless globally recognized (e.g., IEEE). | Apply Title Case. | Example: **Institute of Electrical and Electronics Engineers (IEEE).**",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jan 2024 – Apr 2024.*",
     "location": "Format: **City, Country.** | Example: *Bengaluru, India.*",
  }



MAX_TOKEN = 325    

# --------------------------- Main Model ----------------------------
async def por_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for Por assistant with immediate state updates."""
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    
    
    current_entries = state.get("resume_schema", {}).get("positions_of_responsibility", [])

    
    error_msg = state.get("por", {}).get("error_msg", None)
    

    if error_msg is not None:
        if show_por_logs:
            logger.warning(f"⚠️ POR patch failed with error: {error_msg}")
        
       

        # Give LLM a short controlled prompt to reply politely
        recovery_prompt = POR_Prompts.get_recovery_prompt(error_msg, state.get("por", {}).get("patches", []))   
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKEN)
        response = await llm_por.ainvoke([recovery_prompt], config)
        
        if show_por_logs:
            logger.info(f"por_model (error recovery) response:\n{response.content}")
        
        
        # Reset error so it doesn’t loop forever
        state["por"]["error_msg"] = None

        return {
            "messages": [response],
            "por": {"error_msg": None,}
            }

    try:
        system_prompt = POR_Prompts.get_main_prompt(current_entries, tailoring_keys)
 
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS) 
        response = await llm_por.ainvoke([system_prompt] + messages, config)
        

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        if show_por_logs:
            logger.info(f"\npor_model response:\n {response.content}")
            print(f"Por Model Token Usage:\n{response.usage_metadata}")
        
        return {"messages": [response]}
    except Exception as e:
        logger.error(f"Error in por_model: {e}")
        return {"messages": [AIMessage(content="Sorry! can you repeat")]}





# --------------------------- Query Generator Model ----------------------------
async def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    # current_entries = state.get("resume_schema", {}).get("positions_of_responsibility", [])
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("por", {}).get("patches", [])
   

    prompt = POR_Prompts.get_query_prompt(patches, tailoring_keys)

    try:

        # Call the retriever LLM
        response = await llm_retriever.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        if response.content.strip():
            state["por"]["generated_query"] = str(response.content)
        else:
            state["por"]["generated_query"] = ""

        if show_por_logs:
            logger.info(f"\nQuery Generator Model response:\n{response.content}")
            logger.info(f"Query Generator Model Token Usage:\n{response.usage_metadata}")


        return {"por": state["por"]}
    except Exception as e:
        logger.error(f"Error in query generator: {e}")
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}




# --------------------------- Retriever Node ----------------------------
async def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("por", {}).get("generated_query", [])
        patches = state.get("por", {}).get("patches", [])

        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            state["por"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

        # Collect all unique fields to avoid redundant fetches
        unique_fields = set()
        for patch in patches:
            _, patch_field, _ = get_patch_field_and_index(patch.get("path", ""))
            unique_fields.add(patch_field)
            
            
        if show_por_logs:
            logger.info(f"\n🧠 Unique fields to fetch: {unique_fields}\n")

        all_results = []
        section = "Position of Responsibility Document Formatting Guidelines"

        for field in unique_fields:
            # kb_field = FIELD_MAPPING.get(field)
            kb_field = FieldMapping.POR.get(field,None)
            if show_por_logs:
                logger.info(f"Fetching KB info for field: {field} -> KB field: {kb_field}\n")

            if field == "responsibilities":
                # Fetch action verbs
                action_verbs_info = new_query_pdf_knowledge_base(
                    query_text=str(query),
                    role=["por"],
                    section=section,
                    subsection="Action Verbs (to use in responsibilities)",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[Action Verbs] => {action_verbs_info}")

                # Fetch schema rules
                schema_info = new_query_pdf_knowledge_base(
                    query_text=str(query),
                    role=["por"],
                    section=section,
                    subsection="Schema Requirements & Formatting Rules",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[{field}] {schema_info}")

            else:
                retrieved_info = instruction.get(field, '')
                all_results.append(f"[{field}] {retrieved_info}")

        # Join and store results
        all_results_str = "\n".join(all_results)
        state["por"]["retrieved_info"] = all_results_str
        state["por"]["generated_query"] = ""  # clear after use

        if show_por_logs:
            logger.info(f"\n✅ Retrieved info saved: {all_results_str}")
        return {"por": state["por"]}

    except Exception as e:
        logger.error(f"Error in retriever: {e}")
        return {END: END}





# --------------------------- Builder Model ----------------------------
async def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine por patches using retrieved info."""
    try:
        
        retrieved_info = state.get("por", {}).get("retrieved_info", "")
        patches = state.get("por", {}).get("patches", [])


        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            return {
                "por": state["por"],
                "next_node": "save_entry_state"
            }

        prompt = POR_Prompts.get_builder_prompt(retrieved_info, patches)
        response = await llm_builder.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        # Extract refined patches from LLM output
        refined_patches = extract_json_from_response(response.content)

        if show_por_logs:
            logger.info(f"\n\n✅ Builder produced refined patches: {refined_patches}\n")
            logger.info(f"Builder_model token usage: {response.usage_metadata}\n")


        if refined_patches is not None and not isinstance(refined_patches, list) and len(refined_patches) > 0:
            state["por"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["por"]["patches"] = refined_patches

        return {
            "por": state["por"],
            "next_node": "save_entry_state"
            }

    except Exception as e:
        logger.error(f"Error in builder_model: {e}")
        return {"messages":default_msg,"next_node": END}




# --------------------------- Save Entry State Node ----------------------------
async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update por entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("por", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("por", {}).get("patches", [])


        result = await apply_patches_global(thread_id, patches,"positions_of_responsibility")
        
        print("Apply patches result:", result)
        
        if result and result.get("status") == "success":
            return {
                "messages": [AIMessage(content="Patches applied successfully.")],   
                "por":{
                    "patches": [],
                    "retrieved_info": "",
                    "generated_query": "",
                }
                }
        
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "por": {
                    "error_msg": error_msg,
                    "patches": [], 
                }
            }  
            
    except Exception as e:
        print("Error in save_entry_state:", e)
        return {"messages":AIMessage(content="Sorry,Can't process your request now"),"next_node": END}
    
    
   

# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
por_tools_node = ToolNode(tools)         # For por_model


# Nodes
workflow.add_node("por_model", por_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)



# Tool Nodes
workflow.add_node("tools_por", por_tools_node)




workflow.set_entry_point("por_model")



# Conditional routing
workflow.add_conditional_edges(
    "por_model",
    por_model_router,
    {
        "tools_por": "tools_por",          # <- per-model tool node
        # "retriever_model": "retriever_model",
        "por_model": "por_model",
        END: END
    }
)


# Edges
# workflow.add_edge("tools_por", "por_model")  # return to por
workflow.add_edge("query_generator_model", "retriever_node")  
workflow.add_edge("retriever_node","builder_model")   
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "por_model")




# Compile
position_of_responsibility_assistant = workflow.compile(name="Position_of_responsibility_assistant")
position_of_responsibility_assistant.name = "Position_of_responsibility_assistant"

