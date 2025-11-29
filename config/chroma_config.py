import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from config.env_config import chroma_api_key, chroma_tenant_id, chroma_database





# embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")



chroma_client = chromadb.CloudClient(
  api_key=chroma_api_key,
  tenant=chroma_tenant_id,
  database=chroma_database
)
