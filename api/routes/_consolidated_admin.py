"""Admin routes - Configuration, backup, setup, and notifications.

This is a consolidation wrapper that includes multiple sub-routers.
All original endpoints are preserved for backward compatibility.

Consolidated from:
- config.py (LLM configuration)
- backup.py (backup/restore operations)
- setup.py (database initialization and setup)
- notifications.py (agent notifications and alerts)
"""

from fastapi import APIRouter

# Import existing routers
from api.routes import config, backup, setup, notifications

# Create consolidated router
router = APIRouter(tags=["admin"])

# Include all sub-routers
# These will maintain their original prefixes for backward compatibility
router.include_router(config.router)
router.include_router(backup.router)
router.include_router(setup.router)
router.include_router(notifications.router)
