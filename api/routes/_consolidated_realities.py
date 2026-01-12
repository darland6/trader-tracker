"""Realities routes - Alternate histories, projections, and timeline playback.

This is a consolidation wrapper that includes multiple sub-routers.
All original endpoints are preserved for backward compatibility.

Consolidated from:
- alt_history.py (alternate portfolio histories and what-if scenarios)
- alt_reality.py (user-defined alternate realities)
- history.py (timeline playback and portfolio snapshots)
"""

from fastapi import APIRouter

# Import existing routers
from api.routes import alt_history, history
# Note: alt_reality functionality is included in alt_history now

# Create consolidated router
router = APIRouter(tags=["realities"])

# Include all sub-routers
# These will maintain their original prefixes for backward compatibility
router.include_router(alt_history.router)
router.include_router(history.router)

# Alt-reality endpoints are now part of alt_history
# No need for separate alt_reality router inclusion
