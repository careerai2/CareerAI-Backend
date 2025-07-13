from dotenv import load_dotenv
import os

load_dotenv()

print("PYTHONPYCACHEPREFIX =", os.environ.get("PYTHONPYCACHEPREFIX"))

import uvicorn
# uvicorn.run("app_main:app", reload=True)
if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True,)