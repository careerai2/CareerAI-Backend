from langchain.output_parsers import PydanticOutputParser
from models.resume_model import ResumeLLMSchema
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import List 


class Schema(BaseModel):
    summary: str | None
    skills: List[str]


# Define the parser
output_parser = PydanticOutputParser(pydantic_object=Schema)

# Create format instructions from the parser
format_instructions = output_parser.get_format_instructions()


prompt = PromptTemplate(
    template="""
You are given a user's resume as JSON, which may include "summary" and "skills", plus tailoring keys specifying target roles.

Your task:
1. Generate a professional, tailored summary (4 to 8 sentences) highlighting strengths relevant to the target roles.
2. Provide up to 10 top skills, combining existing and inferred relevant skills, sorted by relevance, no duplicates.

Important:
- If the current summary is already strong and tailored, return `"summary": null`.
- If the skills list is sufficient, return `"skills": []`.

{format_instructions}

Return ONLY the full updated JSON with these two fields changed:
- `"summary"`: updated summary string or null
- `"skills"`: updated skills list or empty list

Rules:
- Use `null` for missing/unknown fields (except summary as above).
- Use empty lists `[]` where appropriate.
- Do NOT add any extra text, only JSON.
- Preserve all other original fields unchanged.

Tailoring keys: {tailoring_keys}

User's resume JSON:
{current_resume}
""",
    input_variables=["current_resume", "tailoring_keys"],
    partial_variables={"format_instructions": format_instructions}
)

# Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_output_tokens=2048
)

# Create chain
chain = prompt | llm | output_parser

async def update_summary_and_skills(current_resume, tailoring_keys):
    """
    Call LLM with system instructions to update summary and skills,
    """
    try:
        result = await chain.ainvoke({"current_resume": current_resume, "tailoring_keys": tailoring_keys})

        print("LLM raw output:", result)
        return result
    except Exception as e:
        print("LLM raw output caused error, check prompt and schema alignment.")
        raise e
