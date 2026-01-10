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
from api.routes import state, trades, options, cash, prices, events, web, backup, chat, research, config, history, setup

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
app.include_router(web.router)  # Web UI routes

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


@app.on_event("startup")
async def startup_event():
    """Initialize database and sync on startup if data exists."""
    from pathlib import Path
    SCRIPT_DIR = Path(__file__).parent.parent.resolve()
    CSV_PATH = SCRIPT_DIR / 'event_log_enhanced.csv'

    # Only init database if CSV exists (real or demo data)
    if CSV_PATH.exists():
        init_database()
        sync_csv_to_db()
    else:
        # Just create empty database schema
        init_database()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
