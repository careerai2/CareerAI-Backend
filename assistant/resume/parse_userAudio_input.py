from langchain.output_parsers import PydanticOutputParser
from models.resume_model import ResumeLLMSchema
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

# Define the parser
output_parser = PydanticOutputParser(pydantic_object=ResumeLLMSchema)

# Create format instructions from the parser
format_instructions = output_parser.get_format_instructions()

# Updated strict prompt
prompt = PromptTemplate(
    template="""
You are given resume text from a user.  
Your task is to extract **all possible details** and place them into the correct fields of the JSON schema provided.  
This includes:
- Education details (degree, branch, institute, years, CGPA)
- Work and leadership experience
- Skills and technologies
- Achievements, awards, certifications
- Extracurriculars
- Languages
- Contact information if present

**Rules:**
- Use `null` for scalar fields if unknown.
- Use `[]` for lists if empty.
- Keep formatting EXACTLY as per the schema.
- Do **not** include any extra text outside the JSON.
- Do **not** wrap JSON in triple backticks.
- Ensure all nested objects have the correct keys even if values are null/empty.
- After extracting fields, generate a 2–4 sentence professional `summary` that captures the overall profile without repeating every detail.

{format_instructions}

User's resume text:
{user_input}
""",
    input_variables=["user_input"],
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

async def parse_user_audio_input(user_input: str, user_id: str):
    """
    Parses the user audio input to generate a structured resume JSON.
    """
    try:
        result = await chain.ainvoke({"user_input": user_input})
        return result
    except Exception as e:
        print("LLM raw output caused error, check prompt and schema alignment.",e)
        raise e
