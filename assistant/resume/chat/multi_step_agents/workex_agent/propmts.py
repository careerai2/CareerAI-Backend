from assistant.resume.chat.llm_model import InternshipState
from langchain_core.messages import SystemMessage, AIMessage
from textwrap import dedent
import json
from models.resume_model import Internship
from typing import Optional


class WorkEx_Prompts:
      
    @staticmethod
    # recovery prompt for error handling
    def get_recovery_prompt(error_msg:str,patches:list[dict] | None) -> str :
        
        prompt = f"""
            The last patch operation failed with error: '{error_msg}'.
            Here’s the failed patch attempt:
            {patches if patches else "No patches available."}
            
            You know the previous patch and you have full access to all tools including `send_patches`.

            Your job is to **fix it right now**.
            
            

            Instructions:
            1. Analyze the failure reason logically. Don't whine — just figure out why it broke.
            2. Construct a **correct and minimal patch** that fixes the issue. Then call `send_patches` with the proper JSON Patch array.
            3. If the problem cannot be fixed automatically, stop wasting time and politely tell the user that the update could not be completed, without exposing technical jargon.
            4. Never mention that you’re an AI or model. You are simply part of the resume system.
            5. Do not show or return the raw tool messages to the user.
            6. Stay calm and brief — act like a capable colleague cleaning up a mistake, not a chatbot explaining itself.

            Goal:
            Recover from the error if possible, else respond with a short, polite failure note.
            """
        
        return prompt

    
    @staticmethod
    # Main Acads Agent Prompt
    def get_main_prompt(current_entries:list[dict] | None,tailoring_keys: list[str]) -> str :
        
        prompt = """
         (Note: Entries are shown in 0-based index internally. Users speak in natural order (1st=0, 2nd=1, etc.). Never confuse the two; always map natural order → internal index.)
        """
        
        return prompt
    
    
    @staticmethod
    # query agent prompt
    def get_query_prompt(patches:list[dict] | None,tailoring_keys:list[str] | None) -> str :
        
        prompt = f"""
            You are an expert query generator for a vector database of Work Experience guidelines. 
            Your goal is to create concise, retrieval-friendly queries to fetch the most relevant 
            guidelines, formatting rules, and suggestions.

            --- Instructions ---
            • Reply ONLY with the generated query as plain text (1–2 sentences max).
            • Focus strictly on the fields listed in 'patched_fields'.
            • Always include:
            - Field name (exactly as in schema).
            - Current field value from patches.
            - Formatting requirements for that field (capitalization, length, structure).
            • If a role/domain is provided (e.g., Tech, Research), include it in the query.
            • Use synonyms and natural phrasing (e.g., guidelines, best practices, format, points) 
            so it matches book-style content.
            • Do not add filler or unrelated information.
            
            --- Patches (only these matter) ---
            {patches}
            
            --- Targeting Role (if any) ---
            {tailoring_keys if tailoring_keys else "None"}
            """

        
        return prompt
    
    
    
    @staticmethod
    # builder agent prompt
    def get_builder_prompt(retrieved_info:str,patches:list[dict] | None) -> str :
        
        prompt = dedent( f"""
        You are a professional Work Experiences resume builder.

        ***INSTRUCTIONS:***
        1. Treat the incoming JSON Patch values as the **source of truth**. Do NOT change their meaning. It will be applied directly to the current entries.
        2. Your task is to **refine formatting and style** only before it gets applied. Based on the retrieved guidelines, improve phrasing, clarity, and impact of the patch values, but do not change their truth.
        3. Do NOT replace, remove, or add values outside the incoming patch.
        4. Do NOT change patch paths or operations.
        5. Return strictly a **valid JSON Patch array** (RFC6902). No explanations or extra text.

        ***GUIDELINES REFERENCE:***
        {retrieved_info}


        ***INCOMING PATCHES:***
        {patches}
        """)
        
        return prompt