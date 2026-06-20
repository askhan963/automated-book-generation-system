from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.generation import router as generation_router
from app.api.routes import router
from app.api.webhooks import router as webhooks_router
from app.api.templates import router as templates_router

app = FastAPI(
    title="Automated Book Generation System",
    description="Generate book outlines and chapters with human-in-the-loop gating.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(generation_router)
app.include_router(webhooks_router)
app.include_router(templates_router)

# Serve generated export files
from fastapi.staticfiles import StaticFiles
import pathlib
EXPORT_DIR = pathlib.Path(__file__).parent.parent / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(EXPORT_DIR)), name="exports")


@app.get("/")
def root():
    return {"docs": "/docs", "health": "/api/v1/health"}
