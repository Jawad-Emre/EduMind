import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.users import router as users_router
from app.api.routes.subjects import router as subjects_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.messages import router as messages_router
from app.api.routes.documents import router as documents_router
from app.api.routes.chat import router as chat_router
from app.api.routes.admin import router as admin_router
from app.api.routes.quizzes import router as quizzes_router
from app.api.routes.auth import router as auth_router
from app.ingestion.embedder import _get_model


app = FastAPI(title="EduMind")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://edumind-frontend-production.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def warm_model():
    await asyncio.to_thread(_get_model)


app.include_router(users_router)
app.include_router(subjects_router)
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(quizzes_router)
app.include_router(auth_router)