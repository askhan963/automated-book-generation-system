from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pathlib

from app.core.config import get_settings
from app.modules.auth.router import router as auth_router
from app.modules.books.router import router as books_router
from app.modules.projects.router import router as projects_router
from app.modules.webhooks.router import router as webhooks_router
from app.modules.templates.router import router as templates_router

settings = get_settings()

app = FastAPI(
    title="Automated Book Generation System",
    description="Generate book outlines and chapters with human-in-the-loop gating.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(books_router)
app.include_router(projects_router)
app.include_router(webhooks_router)
app.include_router(templates_router)

EXPORT_DIR = pathlib.Path(__file__).parent.parent / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(EXPORT_DIR)), name="exports")


@app.get("/")
def root():
    return {"docs": "/docs", "health": "/api/v1/health"}
