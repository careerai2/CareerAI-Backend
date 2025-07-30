from langchain.output_parsers import PydanticOutputParser
from validation.resume_validation import ResumeModel
from validation.new_resume_validation import ResumeRenderContext
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chat_models import init_chat_model
# from langchain.chains import 
from assistant.config import redis_client as r
import json


output_parser = PydanticOutputParser(pydantic_object=ResumeModel)
prompt = PromptTemplate(
    template="""
Please generate a resume summary in JSON format. Try to extract the most relevant information from the user's input.
The output should be a JSON object that matches the following format.

Use:
- `null` for any missing **scalar fields** (like strings or numbers)
- `[]` (empty arrays) for any missing **list fields** (like `skills`, `internships`, `education_entries`, etc.)

{format_instructions}

User's input: {user_input}
""".strip(),
    input_variables=["user_input"],
    partial_variables={"format_instructions": output_parser.get_format_instructions()}
)


# output_parser = PydanticOutputParser(pydantic_object=ResumeRenderContext)
# prompt = PromptTemplate(
#     template="""
# You are an expert resume assistant.

# Extract key resume details from the user's input and return a structured JSON object following the format below.
# Use **natural language sentence-style bullet points** only. 
# Do not use any markup language like Markdown or HTML.
# Each list should contain complete bullet-point sentences (not phrases, not formatted text).

# Use null for any missing values and empty arrays where applicable.

# Format:
# {format_instructions}

# User's input:
# {user_input}
# """.strip(),
#     input_variables=["user_input"],
#     partial_variables={"format_instructions": output_parser.get_format_instructions()}
# )


# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2, 
# )
llm = init_chat_model("openai:gpt-4.1")

chain= prompt | llm | output_parser 

async def parse_user_audio_input(user_input: str,user_id:str):
    """
    Parses the user audio input to generate a resume summary.
    
    Args:
        user_input (str): The user's audio input as text.
        
    Returns:
        ResumeModel: Parsed resume summary.
    """
    try:
        result = await chain.ainvoke({"user_input": user_input})
        
        r.set(f"user_resume:{user_id}", json.dumps(result.model_dump()))
        return result
    except Exception as e:
        print(f"Error in parsing user audio input: {e}")
        raise e
