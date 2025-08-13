# db.py
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorDatabase
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URL = os.environ.get("MONGODB_URL") or "mongodb://localhost:27017"
MONGODB_DB_NAME = os.environ.get("MONGO_DB_NAME", "Career_AI_db")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Development")

print(f"Connecting to MongoDB at {MONGODB_URL}")
print(f"Environment is set to {ENVIRONMENT}")

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGODB_URL, uuidRepresentation="standard")
db:AsyncIOMotorDatabase = client[MONGODB_DB_NAME]

# Optionally, define collection accessors if needed
internship_collection = db["internships"]
resume_collection = db["resumes"]


# Dependency for FastAPI
def get_database() -> AsyncIOMotorDatabase:
    return db

# Async init placeholder for future (if needed)
async def init_db():
    users_collection = db.get_collection("users")
    
    # Create unique index for email
    await users_collection.create_index(
        [("email", 1)],
        unique=True,
        name="unique_email_index"
    )
    print("MongoDB client initialized.")


if __name__ == "__main__":
    init_db()
    print("MongoDB connection established.")