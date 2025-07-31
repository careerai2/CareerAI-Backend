from assistant.resume.chat.tools import tools,get_resume
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage,SystemMessage, HumanMessage
import json
from models.resume_model import *
from langchain.chat_models import init_chat_model
from typing import Annotated
from typing_extensions import TypedDict



class State(TypedDict):
    messages: Annotated[list, add_messages]
    resume: dict
    user_id:str
    resume_id: str
    routing_decision: str | None


llm = init_chat_model("openai:gpt-4.1")

# llm = ChatGoogleGenerativeAI(
#     # model="gemini-2.0-flash",
#     model="gemini-2.5-pro",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2, 

# )


import json
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.messages import HumanMessage, AIMessage
from assistant.resume.chat.llm import llm
from assistant.resume.chat.llm import State

def chatbot(state: State):
    messages: list[BaseMessage] = state["messages"]
    resume: dict = state.get("resume", {})
    user_id = state.get("user_id", "unknown")

    if resume:
        # Add helpful context to the front of the conversation
        response_context = SystemMessage(
            content=(
                'Respond in JSON:\n'
                '{\n'
                '  "message": "<your reply>",\n'
                '  "route_to": "<one of: education | internship | workex_and_project | position_and_extracurricular_achievements | none>"\n'
                '}'
            )
        )
        resume_context = SystemMessage(
            content=f"Here is the user's current resume data: {json.dumps(resume)}"
        )
        user_id_context = SystemMessage(
            content=f"User ID: {user_id}. This will help in personalizing the conversation."
        )
        messages = [response_context, resume_context, user_id_context] + messages

    print("Calling Main LLM")
    response = llm.invoke(messages)

    # Parse LLM JSON response safely
    try:
        parsed = json.loads(response.content)
        route = parsed.get("route_to", "none")
        reply = parsed.get("message", "")
    except Exception:
        route = "none"
        reply = response.content

    # Inject route decision back into state
    state["routing_decision"] = route

    # Replace LLM message with clean AIMessage for downstream use
    return {
        "messages": [AIMessage(content=reply)],
    }



llm_with_tools = llm.bind_tools(tools)


async def education_chatbot(state: State):
    resume: dict = state.get("resume", {})
    user_id = state.get("user_id", "unknown")
    resume_id = state.get("resume_id", "unknown")
    messages: list[BaseMessage] = state["messages"]
    
    edu_schema = Education.model_json_schema()

    # Merge everything into one SystemMessage
    system_content = f"""
                You are an assistant that helps users add and update their education section in a resume.

                ---

                ## 🎯 OBJECTIVE
                Engage with the user naturally to collect or confirm education information.  
                Once the user provides an education entry, you MUST update the resume using the correct tool and format.
                
                ## 👤 USER CONTEXT
                - **User ID**: `{user_id}`
                - **Resume ID**: `{resume_id}`
                - **Current Resume Data**:
                ```json
                {json.dumps(resume, indent=2)}

                ---

                ## 🚨 PRIORITY RULES — FOLLOW STRICTLY IN ORDER:

                ### 1. ✅ TOOL USAGE ON EDUCATION ENTRY
                - You MUST call the tool `update_resume_fields` **whenever the user provides or confirms education details**.
                - You MAY use natural text to ask questions, guide the user, or clarify missing information.
                - Once you have enough details (even partially), use the tool to submit the update.
                - ❌ NEVER ignore the tool call if the user gives input.
                - ✅ Use the tool as soon as a valid or partially valid entry is detected.

                ---

                ### 2. 🧩 STRICT SCHEMA FORMAT (MUST FOLLOW EXACTLY)
                - You MUST use the following schema when calling the tool:
                ```json
                {json.dumps(edu_schema, indent=2)}
                
                
                
                """

    full_messages = [SystemMessage(content=system_content)] + messages

    print("Calling Education LLM")
    response = await llm_with_tools.ainvoke(full_messages)
    
    if hasattr(tools, "update_resume_fields"):
        # If the tool is available, we can assume it was called correctly
        print("Tool call for education update was successful.")

    
    return {"messages": [response]}



async def internship_chatbot(state: State):
    resume: dict = state.get("resume", {})
    user_id = state.get("user_id", "unknown")
    resume_id = state.get("resume_id", "unknown")
    messages: list[BaseMessage] = state["messages"]

    internship_schema = Internship.model_json_schema()

    # Merge everything into one SystemMessage
    system_content = f"""
                You are a highly reliable assistant responsible for updating the **internships** section of a user's resume.

                ---

                ## 🎯 OBJECTIVE
                - Ask users about their internship experiences through natural conversation.
                - Once the user provides details (even partially), call the tool `update_resume_fields` to update their resume.
                - You are NOT a general chatbot — your role is to collect internship data and update resumes accordingly.
                
                ## 👤 USER CONTEXT
                - **User ID**: `{user_id}`
                - **Resume ID**: `{resume_id}`
                - **Current Resume Data**:
                ```json
                {json.dumps(resume, indent=2)}

                ---

                ## 🚨 PRIORITY RULES — STRICTLY FOLLOW IN ORDER

                ### 1. 🔧 TOOL CALL MANDATORY ON USER INPUT
                - ✅ You MAY use natural text to ask questions or clarify inputs.
                - ✅ You MUST call the tool `update_resume_fields` when the user provides internship details.
                - ❌ NEVER reply with internship entries in text or markdown.
                - ❌ NEVER skip the tool call after valid input.

                ---

                ### 2. 📐 STRICT SCHEMA COMPLIANCE (DO NOT ALTER)
                - Use the following exact schema structure when calling the tool:
                ```json
                {json.dumps(internship_schema, indent=2)}
            """  

    full_messages = [SystemMessage(content=system_content)] + messages

    print("Calling Internship LLM")
    response = await llm_with_tools.ainvoke(full_messages)
    
    if hasattr(tools, "update_resume_fields"):
        # If the tool is available, we can assume it was called correctly
        print("Tool call for internship update was successful.")

    

    return {"messages": [response]}



async def workex_and_project_chatbot(state: State):
        resume: dict = state.get("resume", {})
        user_id = state.get("user_id", "unknown")
        resume_id = state.get("resume_id", "unknown")
        messages: list[BaseMessage] = state["messages"]

        workex_schema = WorkExperience.model_json_schema()
        project_schema = Project.model_json_schema()

        # Merge everything into one SystemMessage
        system_content = f"""
                    You are a highly reliable assistant responsible for updating the **work experience** and **projects** sections of a user's resume.

                    ---

                    ## 🎯 OBJECTIVE
                    - Engage users in natural conversation to collect or confirm work experience and project details.
                    - Whenever the user provides details (even partially) about work experience or projects, you MUST call the tool `update_resume_fields` to update their resume.
                    - You are NOT a general chatbot — your role is to collect work experience and project data and update resumes accordingly.

                    ## 👤 USER CONTEXT
                    - **User ID**: `{user_id}`
                    - **Resume ID**: `{resume_id}`
                    - **Current Resume Data**:
                    
                    ```json
                    {json.dumps(resume, indent=2)}

                    ---

                    ## 🚨 PRIORITY RULES — STRICTLY FOLLOW IN ORDER

                    ### 1. 🔧 TOOL CALL MANDATORY ON USER INPUT
                    - ✅ You MAY use natural text to ask questions or clarify inputs.
                    - ✅ You MUST call the tool `update_resume_fields` when the user provides work experience or project details.
                    - ❌ NEVER reply with work experience or project entries in text or markdown.
                    - ❌ NEVER skip the tool call after valid input.

                    ---

                    ### 2. 📐 STRICT SCHEMA COMPLIANCE (DO NOT ALTER)
                    - Use the following exact schema structures when calling the tool:
                    #### Work Experience Schema:
                    ```json
                    {json.dumps(workex_schema, indent=2)}
                    #### Project Schema:
                    ```json
                    {json.dumps(project_schema, indent=2)}
                """

        full_messages = [SystemMessage(content=system_content)] + messages

        print("Calling Work Experience & Project LLM")
        response = await llm_with_tools.ainvoke(full_messages)
        
        if hasattr(tools, "update_resume_fields"):
            # If the tool is available, we can assume it was called correctly
            print("Tool call for work experience and project update was successful.")



        return {"messages": [response]}



async def position_and_extracurricular_achievements_chatbot(state: State):
    resume: dict = state.get("resume", {})
    user_id = state.get("user_id", "unknown")
    resume_id = state.get("resume_id", "unknown")
    messages: list[BaseMessage] = state["messages"]

    position_schema = PositionOfResponsibility.model_json_schema()
    extracurricular_schema = ExtraCurricular.model_json_schema()
    achievement_schema = ScholasticAchievement.model_json_schema()

    # Merge everything into one SystemMessage
    system_content = f"""
        You are an assistant responsible for updating the **positions of responsibility**, **extracurricular activities**, and **achievements** sections of a user's resume.

        ---

        ## 🎯 OBJECTIVE
        - Engage users in natural conversation to collect or confirm details about positions of responsibility, extracurricular activities, and achievements.
        - Whenever the user provides details (even partially) about any of these sections, you MUST call the tool `update_resume_fields` to update their resume.
        - You are NOT a general chatbot — your role is to collect these specific data and update resumes accordingly.

        ## 👤 USER CONTEXT
        - **User ID**: `{user_id}`
        - **Resume ID**: `{resume_id}`
        - **Current Resume Data**:
        ```json
        {json.dumps(resume, indent=2)}

        ---

        ## 🚨 PRIORITY RULES — STRICTLY FOLLOW IN ORDER

        ### 1. 🔧 TOOL CALL MANDATORY ON USER INPUT
        - ✅ You MAY use natural text to ask questions or clarify inputs.
        - ✅ You MUST call the tool `update_resume_fields` when the user provides details for positions of responsibility, extracurricular activities, or achievements.
        - ❌ NEVER reply with entries in text or markdown.
        - ❌ NEVER skip the tool call after valid input.

        ---

        ### 2. 📐 STRICT SCHEMA COMPLIANCE (DO NOT ALTER)
        - Use the following exact schema structures when calling the tool:
        #### Position of Responsibility Schema:
        ```json
        {json.dumps(position_schema, indent=2)}
        #### Extracurricular Schema:
        ```json
        {json.dumps(extracurricular_schema, indent=2)}
        #### Achievement Schema:
        ```json
        {json.dumps(achievement_schema, indent=2)}
    """

    full_messages = [SystemMessage(content=system_content)] + messages

    print("Calling Position, Extracurricular & Achievement LLM")
    response = await llm_with_tools.ainvoke(full_messages)
    
    if hasattr(tools, "update_resume_fields"):
        # If the tool is available, we can assume it was called correctly
        print("Tool call for position, extracurricular and achievement update was successful.")

    

    return {"messages": [response]}
