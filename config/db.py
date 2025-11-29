# db.py
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorDatabase
from config.env_config import MONGODB_URL, MONGODB_DB_NAME, ENVIRONMENT



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