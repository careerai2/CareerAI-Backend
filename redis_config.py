import redis
import os
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb

redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
redis_username = os.environ.get('REDIS_USERNAME', 'default')
redis_password = os.environ.get('REDIS_PASSWORD', '')

redis_client = redis.Redis(
    host=redis_host,
    port=redis_port,
    decode_responses=True,
    username=redis_username,
    password=redis_password
)



# embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

# chroma_db_port = os.environ.get('CHROMA_DB_PORT', '8000')
# chroma_db_host = os.environ.get('CHROMA_DB_HOST', 'localhost')

# chroma_client = chromadb.HttpClient(host=chroma_db_host, port=chroma_db_port)

# db = Chroma(
#     client=chroma_client,
#     collection_name="resumes",
#     embedding_function=embeddings
# )

# collection = chroma_client.get_collection(name="resume_guidelines")