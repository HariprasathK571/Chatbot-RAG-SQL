from fastapi import FastAPI
from src.chatbot.routes import chatbot_router
from fastapi.middleware.cors import CORSMiddleware
from src.auth.routes import auth_router
from src.db.core import init_db  # ✅ this will load User model also

app = FastAPI(title="SQL LLM API")

@app.on_event("startup")
async def on_startup():
    await init_db()  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # ✅ Vite frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

version_prefix =f"/api"

app.include_router(auth_router, prefix=f"{version_prefix}/auth", tags=["auth"])
app.include_router(chatbot_router, prefix=f"{version_prefix}/chatbot", tags=["chatbot"])