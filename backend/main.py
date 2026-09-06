from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
import models  # noqa: F401 — ensures all models are registered before create_all
from routers import chat, user, room

app = FastAPI(title="Research Room API")

# Allow the Next.js dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creates tables that don't exist yet — fine for hackathon speed,
# swap for real migrations (alembic) if you have time later
Base.metadata.create_all(bind=engine)

app.include_router(user.router)
app.include_router(room.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}