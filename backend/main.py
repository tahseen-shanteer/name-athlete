from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socketio
import uvicorn
import os
from dotenv import load_dotenv
from models import CreateSessionResponse, CreateSessionRequest
import session_manager as sm
from sports_config import initialize_sports_cache, get_cached_sports
from validation import close_http_session
from events import register_events
import logging

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Get admin password from environment
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "athletes2000admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize caches on startup."""
    logger.info("Initializing sports cache from Wikidata...")
    await initialize_sports_cache()
    logger.info("Sports cache ready.")
    yield
    # Shutdown: clean up shared resources
    await close_http_session()
    logger.info("Application shutting down.")


# Create FastAPI app
app = FastAPI(title="2000 Athletes Challenge API", lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False,
)

# Register Socket.IO events
register_events(sio)

# Wrap with ASGI app
socket_app = socketio.ASGIApp(sio, app)


# REST API endpoints
@app.get("/")
async def root():
    return {"message": "2000 Athletes Challenge API", "status": "running"}


@app.post("/api/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new game session. Requires admin password."""
    # Verify admin password
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")

    if not request.host_username or not request.host_username.strip():
        raise HTTPException(status_code=400, detail="Host username is required")

    # Create session with host
    session = sm.create_session(host_username=request.host_username.strip())
    return CreateSessionResponse(code=session.code, created_at=session.created_at)


@app.get("/api/session/{code}")
async def get_session(code: str):
    """Get session details."""
    session = sm.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "code": session.code,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ends_at": session.ends_at.isoformat() if session.ends_at else None,
        "count": len(session.athletes),
        "host_username": session.host_username,
        "athletes": [
            {
                "name": a.name,
                "sport": a.sport_display or a.sport,
                "submitted_by": a.submitted_by,
                "submitted_at": a.submitted_at.isoformat(),
                "validated": a.validated,
            }
            for a in session.athletes
        ],
        "connected_users": len(session.connected_users),
    }


@app.get("/api/sports")
async def get_sports():
    """Get list of available sports (dynamically fetched from Wikidata)."""
    sports = get_cached_sports()
    if not sports:
        raise HTTPException(
            status_code=503,
            detail="Sports list not yet loaded. Please try again in a moment.",
        )
    return {"sports": sports}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(socket_app, host="0.0.0.0", port=port, log_level="info")
