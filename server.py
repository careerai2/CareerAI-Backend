from dotenv import load_dotenv
import os
import uvicorn

# Load environment variables
load_dotenv()

# Expose app for Uvicorn
from main import app  # 👈 This makes server:app valid

print("PYTHONPYCACHEPREFIX =", os.environ.get("PYTHONPYCACHEPREFIX"))

port = int(os.environ.get("PORT", 8000))
host = "127.0.0.1"  # Always listen on all interfaces for Docker

if __name__ == "__main__":
    reload_flag = os.environ.get("ENVIRONMENT") == "Development"
    uvicorn.run("server:app", host=host, port=port, reload=reload_flag)
