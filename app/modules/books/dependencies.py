"""
Dependency injection for books module.
Provides dependencies for routers and services.
"""
from typing import Annotated

from fastapi import Depends

from app.core.dependencies import (
    get_supabase_client,
    get_openai_client,
    get_settings,
)
from app.modules.books.repository import get_supabase
from app.modules.books.service import (
    create_book_and_outline,
    generate_chapter,
    generate_outline,
    get_book_response,
    list_books_response,
    update_outline,
    update_final_review,
    generate_next_chapter,
    get_chapter_response,
    list_chapters_response,
    update_chapter_with_gate,
    regenerate_chapter_content,
    moderate_chapter_content,
    compile_book_content,
    get_book_draft,
)

# Repository dependencies
def get_books_repository():
    """Get books repository instance."""
    # In this implementation, we're using direct function calls
    # but we could return a repository class if needed
    pass

# Service dependencies
def get_books_service():
    """Get books service instance."""
    # In this implementation, we're using direct function calls
    # but we could return a service class if needed
    pass

# For now, we're using direct imports in the router
# These dependency functions are placeholders for future refinement