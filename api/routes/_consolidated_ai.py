"""AI routes - Chat, scanner, ideas, and research.

This is a consolidation wrapper that includes multiple sub-routers.
All original endpoints are preserved for backward compatibility.

Consolidated from:
- chat.py (LLM chat interface with portfolio context)
- scanner.py (options scanner for income opportunities)
- ideas.py (seed ideas and manifestation)
- research.py (Dexter financial research integration)
"""

from fastapi import APIRouter

# Import existing routers
from api.routes import chat, scanner, ideas, research

# Create consolidated router
router = APIRouter(tags=["ai"])

# Include all sub-routers
# These will maintain their original prefixes for backward compatibility
router.include_router(chat.router)
router.include_router(scanner.router)
router.include_router(ideas.router)
router.include_router(research.router)
