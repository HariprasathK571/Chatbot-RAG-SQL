from fastapi import FastAPI
from src.chatbot.routes import chatbot_router
app = FastAPI(title="SQL LLM API")

version_prefix =f"/api"

app.include_router(chatbot_router, prefix=f"{version_prefix}/chatbot", tags=["chatbot"])