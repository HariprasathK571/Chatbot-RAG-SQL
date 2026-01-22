from fastapi import FastAPI
from src.chatbot.routes import chatbot_router
from fastapi.middleware.cors import CORSMiddleware
from src.auth.routes import auth_router
from src.db.core import init_db  # ✅ this will load User model also
from src.conversations.routes import router as conversation_router

from src.core.logger import setup_logging
from src.core.middleware import RequestIdMiddleware
from src.core.routes import router as logs_router

setup_logging()

app = FastAPI(title="SQL LLM API")

@app.on_event("startup")
async def on_startup():
    await init_db()  

# ✅ request-id middleware
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # ✅ Vite frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

version_prefix =f"/api"

app.include_router(auth_router, prefix=f"{version_prefix}/auth", tags=["auth"])
app.include_router(conversation_router, prefix=f"{version_prefix}/conversations", tags=["conversations"])
app.include_router(chatbot_router, prefix=f"{version_prefix}/chatbot", tags=["chatbot"])
app.include_router(logs_router, prefix=f"{version_prefix}/logs", tags=["logs"])