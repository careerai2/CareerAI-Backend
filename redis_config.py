import redis
import os
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb
# from langchain.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


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
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


chroma_api_key = os.environ.get('CHROMA_API_KEY')
chroma_tenant_id = os.environ.get('CHROMA_TENANT_ID')
chroma_database = os.environ.get('CHROMA_DATABASE', 'Career AI')

chroma_client = chromadb.CloudClient(
  api_key=chroma_api_key,
  tenant=chroma_tenant_id,
  database=chroma_database
)
