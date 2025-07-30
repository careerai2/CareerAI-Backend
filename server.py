from dotenv import load_dotenv
import os

load_dotenv()

print("PYTHONPYCACHEPREFIX =", os.environ.get("PYTHONPYCACHEPREFIX"))
port = int(os.environ.get("PORT", 8000))
host = "127.0.1" if os.environ.get("ENVIRONMENT") == "Development" else os.environ.get("HOST", "127.0.0.1")


import uvicorn
# uvicorn.run("app_main:app", reload=True)
if __name__ == "__main__":
    uvicorn.run("main:app", port=port, reload=True)