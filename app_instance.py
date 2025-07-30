from fastapi import FastAPI
from websocket_manger import ConnectionManager

app = FastAPI()
app.state.connection_manager = ConnectionManager()
