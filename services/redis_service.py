import json
from config.log_config import get_logger

logger = get_logger("Redis_Service")

class RedisService:
    def __init__(self, redis_client):
        self.r = redis_client

    @staticmethod
    def generate_key(user_id: str, resume_id: str) -> str:
        return f"resume:{user_id}:{resume_id}"
    
    @staticmethod
    def generate_key_by_threadId(thread_id: str) -> str:
        return f"resume:{thread_id}"
    
    # Fetch resume data for a given user_id and resume_id
    def get_resume(self,user_id: str, resume_id: str) -> dict:
        try:
            key = self.generate_key(user_id, resume_id)
            data = self.r.get(key)
            return json.loads(data) if data else {}
        except Exception as e:
            return {}

    # Get resume by thread ID
    def get_resume_by_threadId(self,thread_id: str) -> dict | None: 
        try:
            key = self.generate_key_by_threadId(thread_id)
            data = self.r.get(key)
            
            logger.debug(f"Fetching resume with thread_id {thread_id}, data found: {data is not None}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Error fetching resume by thread_id {thread_id}: {e}")
            return None

    # Save resume data for a given user_id and resume_id
    def save_resume(self,user_id: str, resume_id: str, resume: dict):
        try:
            # SHOULD check Resume Schema validation here
            key = self.generate_key(user_id, resume_id)
            self.r.set(key, json.dumps(resume))
        except Exception as e:
            logger.error(f"Error saving resume for user {user_id}, resume {resume_id}: {e}")
            
    # Save resume data for a given user_id and resume_id
    def save_resume_by_threadId(self,thread_id: str, resume: dict):
        try:
            # SHOULD check Resume Schema validation here
            key = self.generate_key_by_threadId(thread_id)
            self.r.set(key, json.dumps(resume))
        except Exception as e:
            logger.error(f"Error saving resume for user {thread_id} :{e}")
            
    # Get tailoring keys for a given user_id and resume_id
    def get_tailoring_keys(self,user_id: str, resume_id: str) -> list:

        key = self.generate_key(user_id, resume_id)
        data = self.r.get(key)
        
        if not data:
            return []
        
        data = json.loads(data)
        
        # print(data.get("tailoring_keys"))  # Debugging line
        if "tailoring_keys" in data:
            return data["tailoring_keys"]

        return []

