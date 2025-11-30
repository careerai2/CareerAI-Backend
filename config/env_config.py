import os
from dotenv import load_dotenv

load_dotenv()

# Development or Production Environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Development")



# postgress database url
DATABASE_URL = os.environ.get("DATABASE_URL")  or "postgresql+asyncpg://postgres:keshav123@localhost:5432/CareerAI"

# MongoDB configuration
MONGODB_URL = os.environ.get("MONGODB_URL") or "mongodb://localhost:27017"
MONGODB_DB_NAME = os.environ.get("MONGO_DB_NAME", "Career_AI_db")




# redis configuration
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))  # cast to int
redis_username = os.environ.get('REDIS_USERNAME', 'default')
redis_password = os.environ.get('REDIS_PASSWORD', '')



# chroma configuration
chroma_api_key = os.environ.get('CHROMA_API_KEY')
chroma_tenant_id = os.environ.get('CHROMA_TENANT_ID')
chroma_database = os.environ.get('CHROMA_DATABASE', 'Career AI')












# Agent Logging Configurations
show_internship_logs = os.environ.get("SHOW_INTERNSHIP_LOGS", "False").lower() == "true"
show_acads_logs = os.environ.get("SHOW_ACADS_LOGS", "False").lower() == "true"
show_workex_logs = os.environ.get("SHOW_WORKEX_LOGS", "False").lower() == "true"
show_por_logs = os.environ.get("SHOW_POR_LOGS", "False").lower() == "true"
show_certification_logs = os.environ.get("SHOW_CERTIFICATIONS_LOGS", "False").lower() == "true"
show_scholastic_achievement_logs = os.environ.get("SHOW_SCHOLASTIC_ACHIEVEMENT_LOGS", "False").lower() == "true"
show_extra_curricular_logs = os.environ.get("SHOW_EXTRA_CURRICULAR_LOGS", "False").lower() == "true"
show_education_logs = os.environ.get("SHOW_EDUCATION_LOGS", "False").lower() == "true"
show_bullet_logs = os.environ.get("SHOW_BULLET_LOGS", "False").lower() == "true" 

MAX_TOKEN = int(os.environ.get("MAX_TOKEN", 325))

# Resume Download API URL
resume_download_url = os.environ.get("Resume_Download_API_URL", "http://localhost:9000/download-resume")