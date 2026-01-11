"""
Portfolio Dashboard API

FastAPI backend for the portfolio management system.
Serves both the management web UI and the Three.js dashboard.

Run with: uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import json

from api.database import init_database, sync_csv_to_db
from api.routes import state, trades, options, cash, prices, events, web, backup, chat, research, config, history, setup, notifications, alt_history, scanner
from api.services.skill_discovery import create_skill_router

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"

# Initialize app
app = FastAPI(
    title="Portfolio Dashboard API",
    description="API for managing financial portfolio with event sourcing",
    version="1.0.0"
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev server
        "http://localhost:8000",  # Same origin
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(state.router)
app.include_router(trades.router)
app.include_router(options.router)
app.include_router(cash.router)
app.include_router(prices.router)
app.include_router(events.router)
app.include_router(backup.router)  # Backup/restore routes
app.include_router(chat.router)  # Chat with LLM
app.include_router(research.router)  # Dexter financial research
app.include_router(config.router)  # LLM configuration
app.include_router(history.router)  # History playback
app.include_router(setup.router)  # Setup and initialization
app.include_router(notifications.router)  # Agent notifications
app.include_router(alt_history.router)  # Alternate history / what-if scenarios
app.include_router(scanner.router)  # Options scanner for income opportunities
app.include_router(create_skill_router())  # Skill discovery and management
app.include_router(web.router)  # Web UI routes


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    favicon_path = STATIC_DIR / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return FileResponse(status_code=204)  # No content


# WebSocket connection manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def do_price_update():
    """Perform price update for scheduler."""
    from api.routes.prices import update_prices
    try:
        result = await update_prices(save_to_log=True)
        return result.data if result else None
    except Exception as e:
        print(f"[Scheduler] Price update failed: {e}")
        return None


async def do_alert_check():
    """Perform alert check for scheduler."""
    from api.services.alerts import run_all_alert_checks
    try:
        return run_all_alert_checks()
    except Exception as e:
        print(f"[Scheduler] Alert check failed: {e}")
        return None


@app.on_event("startup")
async def startup_event():
    """Initialize database and sync on startup if data exists."""
    from pathlib import Path
    from api.services.scheduler import scheduler

    SCRIPT_DIR = Path(__file__).parent.parent.resolve()
    CSV_PATH = SCRIPT_DIR / 'data' / 'event_log_enhanced.csv'

    # Only init database if CSV exists (real or demo data)
    if CSV_PATH.exists():
        init_database()
        sync_csv_to_db()
    else:
        # Just create empty database schema
        init_database()

    # Configure and start scheduler
    scheduler.set_callbacks(
        price_update=do_price_update,
        alert_check=do_alert_check,
        broadcast=manager.broadcast
    )
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    from api.services.scheduler import scheduler
    scheduler.stop()


@app.get("/")
async def root():
    """Root endpoint - redirect to dashboard or show API info."""
    return {
        "message": "Portfolio Dashboard API",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "management": "/manage"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve static files for web UI and dashboard
SCRIPT_DIR = Path(__file__).parent.parent.resolve()

# Mount static directories if they exist
web_static = SCRIPT_DIR / "web" / "static"
if web_static.exists():
    app.mount("/static", StaticFiles(directory=str(web_static)), name="static")

dashboard_dist = SCRIPT_DIR / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")

    # Serve PWA files at root level for the dashboard
    @app.get("/manifest.json")
    async def get_manifest():
        from fastapi.responses import FileResponse
        manifest_path = dashboard_dist / "manifest.json"
        if manifest_path.exists():
            return FileResponse(manifest_path, media_type="application/manifest+json")
        return {"error": "manifest not found"}

    @app.get("/icon.svg")
    async def get_icon():
        from fastapi.responses import FileResponse
        icon_path = dashboard_dist / "icon.svg"
        if icon_path.exists():
            return FileResponse(icon_path, media_type="image/svg+xml")
        return {"error": "icon not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
