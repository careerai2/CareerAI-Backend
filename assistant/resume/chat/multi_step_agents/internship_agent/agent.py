from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from ...llm_model import llm,SwarmResumeState
from .tools import tools
from utils.safe_trim_msg import safe_trim_messages
from ...utils.common_tools import extract_json_from_response,get_patch_field_and_index
from ...utils.apply_patches import apply_patches_global
import assistant.resume.chat.token_count as token_count
from .functions import new_query_pdf_knowledge_base
from .functions import new_query_pdf_knowledge_base
# from assistant.resume.chat.utils.query_vector_db import new_query_pdf_knowledge_base
from ...utils.field_mapping import FieldMapping
from config.log_config import get_logger
from config.env_config import show_internship_logs
from .prompts import Internship_Prompts

# ---------------------------
# 2. LLM with Tools
# ---------------------------


llm_internship = llm.bind_tools(tools)
llm_error_handler = llm.bind_tools(tools)  # tool can be added if needed
llm_builder = llm  # tool can be added if needed
llm_retriever = llm # tool can be added if needed




default_msg = AIMessage(content="Sorry, I couldn't process that. Could you please retry?")




instruction = {
    "company_name": "Use official registered name only. | Avoid abbreviations unless globally recognized (e.g., IBM). | Apply Title Case. | Example: **Google LLC.**",
    "location": "Format: **City, Country.** | Example: *Bengaluru, India.*",
    "designation": "Write the exact internship title. | Capitalize each word. | Example: **Software Engineering Intern.**",
    "duration": "Format: **MMM YYYY – MMM YYYY** (or *Present* if ongoing). | Example: *Jun 2024 – Aug 2024.*",
  }


MAX_TOKENS = 350


logger = get_logger("Internship")






# ---------------------------- Main Model ---------------------------
async def internship_model(state: SwarmResumeState, config: RunnableConfig):
    """Main chat loop for internship assistant with immediate state updates."""
    
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    current_entries = state.get("resume_schema", {}).get("internships", [])
    

    error_msg = state.get("internship", {}).get("error_msg", None)
    
    
    
    if error_msg and show_internship_logs:
        logger.error(f"⚠️ Internship patch failed with error: {error_msg}")
        
        recovery_prompt = Internship_Prompts.get_recovery_prompt(error_msg,state["internship"]["patches"])
        
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        # Make it human-like using the same LLM pipeline
        response = await llm_internship.ainvoke([recovery_prompt], config)
        
        if show_internship_logs:
            logger.info(f"""internship_model (error recovery) response :\n\n {response.content}""")
        
        # Reset error so it doesn’t loop forever
        state["internship"]["error_msg"] = None

        return {
            "messages": [response],
            "internship": {
                    "error_msg": None,
                }
            }
 


    try:
        
        system_prompt = Internship_Prompts.get_main_prompt(current_entries,tailoring_keys=tailoring_keys)
        messages = safe_trim_messages(state["messages"], max_tokens=MAX_TOKENS)
        response = await llm_internship.ainvoke([system_prompt] + messages, config)

        # Update token counters
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        
        if show_internship_logs:
            
            logger.info(f"""Internship_Model response :\n {response.content}\n\n""")
            logger.info(f"Internship Token Usage: {response.usage_metadata}\n\n")

        
        return {
            "messages": [response],
            "internship": state.get("internship", {})
            }
    except Exception as e:
        logger.error(f"Error in internship_model: {e}")
        return {"messages": [AIMessage(content="Sorry! can you repeat")],"next_node": END}





# ----------------------------- Query generator Model ------------------------------ 
async def query_generator_model(state: SwarmResumeState, config: RunnableConfig):
    """Fetch relevant info from knowledge base."""
    
    tailoring_keys = config["configurable"].get("tailoring_keys", [])
    patches = state.get("internship", {}).get("patches", [])
   

    prompt = Internship_Prompts.get_query_prompt(patches=patches,tailoring_keys=tailoring_keys)

    try:

        response = await llm_retriever.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)
        
        


        if response.content.strip():
            state["internship"]["generated_query"] = str(response.content)
        else:
            state["internship"]["generated_query"] = ""
            logger.info("Retriever returned empty info")

        if show_internship_logs:
            
            logger.info(f"""Query generated response :\n\n {response.content}\n\n""")
            logger.info(f"Query generator Token Usage: {response.usage_metadata}\n\n")

        return {"next_node": END}
    except Exception as e:
        logger.error("Error in query generator:", e)
        
        return {"messages":AIMessage(content="Unable to make changes  due to {e}")}





# ----------------------------- Knowledge Base Retriever Node ---------------------------
async def retriever_node(state: SwarmResumeState, config: RunnableConfig):
    try:
        query = state.get("internship", {}).get("generated_query", [])
        patches = state.get("internship", {}).get("patches", [])

        if not query or (isinstance(query, str) and query.strip() in ("None", "")):
            logger.info("No query generated, skipping retrieval.")
            state["internship"]["retrieved_info"] = []
            return {"next_node": "builder_model"}

        all_results = []

        # Loop over each patch
        for i, patch in enumerate(patches):
            patch_path = patch.get("path", "")
            patch_value = patch.get("value", "")
            index, patch_field,append = get_patch_field_and_index(patch_path)
            kb_field = FieldMapping.INTERNSHIP.get(patch_field, None)

            if show_internship_logs:
                logger.info(f"\n🔍 Patch {i+1}: internship index={index}, field={patch_field}, KB field={kb_field}")

            section = "Internship Document Formatting Guidelines"
            
            retrieved_info = None  # initialize here to avoid UnboundLocalError

            if patch_field == "internship_work_description_bullets" and kb_field:
                retrieved_info = await new_query_pdf_knowledge_base(
                    query_text=str(query),  # query string
                    role=["internship"],
                    section=section,
                    subsection="Action Verbs (to use in work descriptions)",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[Action Verbs] => {retrieved_info}")

                retrieved_info = new_query_pdf_knowledge_base(
                    query_text=str(patch_value),  # use patch value as query
                    role=["internship"],
                    section=section,
                    subsection="Schema Requirements & Formatting Rules",
                    field=kb_field,
                    n_results=5,
                    debug=False
                )
                all_results.append(f"[{patch_field}] {retrieved_info}")

            else:
                retrieved_info = instruction.get(patch_field, '')
                all_results.append(f"[{patch_field}] {retrieved_info}")
            
            if show_internship_logs:
                logger.info(f"Retriever returned {retrieved_info} results for patch {i+1}.\n")



        all_results_str = "\n".join(all_results)
        state["internship"]["retrieved_info"] = all_results_str
        state["internship"]["generated_query"] = ""  # clear after use
        
        if show_internship_logs:
            logger.info(f"\n✅ Retrieved info saved: {all_results_str} \n\n")

        return {"next_node": "builder_model"}

    except Exception as e:
        logger.error(f"Error in retriever: {e}")
        return {END: END}





# -------------------------------- Builder Model  ---------------------------------
async def builder_model(state: SwarmResumeState, config: RunnableConfig):
    """Refine internship patches using retrieved info."""
    try:
        
        retrieved_info = state.get("internship", {}).get("retrieved_info", "")
        patches = state.get("internship", {}).get("patches", [])




        if not retrieved_info or retrieved_info.strip() in ("None", ""):
            if show_internship_logs:
                logger.info("No retrieved info available, skipping building.")
            state["messages"].append(SystemMessage(content="No retrieved info available, skipping building."))
            return

        prompt = Internship_Prompts.get_builder_prompt(retrieved_info,patches)
        
        response = await llm_builder.ainvoke(prompt, config)
        
        token_count.total_Input_Tokens += response.usage_metadata.get("input_tokens", 0)
        token_count.total_Output_Tokens += response.usage_metadata.get("output_tokens", 0)

        

        # Extract refined patches from LLM output
        refined_patches = extract_json_from_response(response.content)
        
        if show_internship_logs:
    
            logger.info(f"""Builder response :\n\n {response.content}\n\n""")
            logger.info(f"Builder Token Usage: {response.usage_metadata}\n\n")



        if refined_patches is not None and not isinstance(refined_patches, list):
            state["internship"]["patches"] = [refined_patches]
        elif refined_patches is not None :    
            state["internship"]["patches"] = refined_patches
        
        return {
            "internship": state.get("internship", {})
        }

    except Exception as e:
        logger.error(f"Error in builder_model: {e}")
        return {"messages":AIMessage(content=f"Unable to Make changes due to {e}")}




# ----------------------- Save Entry Node ------------------------
async def save_entry_state(state: SwarmResumeState, config: RunnableConfig):
    """Parse LLM response and update internship entry state."""
    try:

        # print("Internship State in save_entry_state:", state.get("internship", {}))
        thread_id = config["configurable"]["thread_id"]
        patches = state.get("internship", {}).get("patches", [])


        patch_field = [patch["path"] for patch in patches if "path" in patch]

        result = await apply_patches_global(thread_id, patches,"internships")
        # result = await apply_patches(thread_id, patches)
        
        logger.info(f"Apply patches result: {result}")
        
        if result and result.get("status") == "success":
            logger.info("Entry state updated successfully in Redis.")
            state["internship"]["save_node_response"] = f"patches applied successfully on fields {', '.join(patch_field)}."
            
         
            return{
                "next_node": "end_node",
            }
        elif result and result.get("status") == "error":
            error_msg = result.get("message", "Unknown error during patch application.")
            
            return {
                "messages": [AIMessage(content=f"Failed to apply patches: {error_msg},Pathces: {patches}")],
                "next_node": "internship_model",
                "internship": {
                    "error_msg": error_msg,
                }
            }

    except Exception as e:
        logger.exception(f"Error in save_entry_state: {e}")
        return {"messages":AIMessage(content=f"Unable to make changes due to {e}"),"next_node": "internship_model"}
    
    
    
    
# ---------------------------
# 5. Conditional Router
# ---------------------------

def internship_model_router(state: SwarmResumeState):
    last_message = state["messages"][-1]
    # patches = state["internship"]["patches"]
    
    # print("\n\nPatches in Router:-", patches)

    # 1. Go to internship tools if a tool was called
    if getattr(last_message, "tool_calls", None):
        return "tools_internship"


    return END





# ---------------------------
# 6. Create Graph
# ---------------------------

workflow = StateGraph(SwarmResumeState)


# Tool nodes for each model
internship_tools_node = ToolNode(tools)         # For internship_model


# Nodes
workflow.add_node("internship_model", internship_model)
workflow.add_node("query_generator_model", query_generator_model)
workflow.add_node("retriever_node", retriever_node)
workflow.add_node("builder_model", builder_model)
workflow.add_node("save_entry_state", save_entry_state)



# Tool Nodes
workflow.add_node("tools_internship", internship_tools_node)




workflow.set_entry_point("internship_model")



# Conditional routing
workflow.add_conditional_edges(
    "internship_model",
    internship_model_router,
    {
        "tools_internship": "tools_internship",          
        "internship_model": "internship_model",
        END: END
    }
)



# Edges
workflow.add_edge("query_generator_model", "retriever_node")  # return to retriever
workflow.add_edge("retriever_node","builder_model")   # return to builder
workflow.add_edge("builder_model", "save_entry_state")
workflow.add_edge("save_entry_state", "internship_model") 



# Compile
internship_assistant = workflow.compile(name="internship_assistant")
internship_assistant.name = "internship_assistant"
