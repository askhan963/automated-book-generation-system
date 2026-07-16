from uuid import UUID
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["generation"])
# Generation endpoints have been moved to the books module for better feature cohesion