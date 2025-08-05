from langchain.output_parsers import PydanticOutputParser
from models.resume_model import ResumeLLMSchema
from validation.new_resume_validation import ResumeRenderContext
from langchain.prompts import PromptTemplate
from langchain.chat_models import init_chat_model


output_parser = PydanticOutputParser(pydantic_object=ResumeLLMSchema)
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


# llm = init_chat_model("openai:gpt-4.1")


from langchain_google_genai import ChatGoogleGenerativeAI

# Create a Gemini Flash instance
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",  # Use gemini-1.5-pro for higher reasoning
    temperature=0,             # Optional: control creativity
    max_output_tokens=1024     # Optional: control output length
)

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
        return result
    except Exception as e:
        print(f"Error in parsing user audio input: {e}")
        raise e
