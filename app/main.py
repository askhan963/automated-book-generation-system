from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from app.modules.auth.router import router as auth_router
from app.modules.books.router import router as books_router
from app.modules.projects.router import router as projects_router
from app.modules.webhooks.router import router as webhooks_router
from app.modules.templates.router import router as templates_router

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

app = FastAPI(
    title="Automated Book Generation System",
    description="Generate book outlines and chapters with human-in-the-loop gating.",
    version="1.0.0",
    dependencies=[Depends(oauth2_scheme)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(books_router)
app.include_router(projects_router)
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