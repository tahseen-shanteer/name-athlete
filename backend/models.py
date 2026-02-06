from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Athlete(BaseModel):
    name: str
    normalized_name: str
    sport: str  # Wikidata Q-ID (e.g., "Q5372" for basketball)
    sport_display: Optional[str] = (
        None  # Human-readable sport label (e.g., "basketball")
    )
    submitted_by: str
    submitted_at: datetime
    validated: bool = True  # False if Wikidata API failed
    entity_id: Optional[str] = None  # Wikidata Q-ID for the athlete
    hint: Optional[str] = None  # Disambiguation hint if provided
    canonical_name: Optional[str] = (
        None  # Official name from Wikidata (e.g., "Lionel Messi")
    )


class RejectedSubmission(BaseModel):
    """Record of a rejected athlete submission."""

    name: str
    sport: str
    username: str
    reason: (
        str  # "duplicate" | "invalid_athlete" | "wrong_sport" | "invalid_input" | etc.
    )
    submitted_at: datetime


class DisconnectedUser(BaseModel):
    disconnected_at: datetime
    submissions_count: int


class ConnectedUser(BaseModel):
    """Represents a user in the session with connection status."""

    username: str
    is_connected: bool = True
    is_host: bool = False


class Session(BaseModel):
    code: str
    status: str  # "waiting" | "active" | "completed"
    created_at: datetime
    started_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    host_username: Optional[str] = None  # The user who created/hosts the session
    athletes: list[Athlete] = []
    athlete_names: set[str] = set()  # Normalized names for duplicate check
    athlete_entity_ids: set[str] = set()  # Entity IDs for entity-based duplicate check
    connected_users: dict[str, str] = {}  # {socket_id: username}
    disconnected_users: dict[str, DisconnectedUser] = {}
    rejected_submissions: list[RejectedSubmission] = []  # All rejected submissions
    # Pause/resume state
    is_paused: bool = False
    paused_at: Optional[datetime] = None
    time_remaining_at_pause: Optional[int] = None  # seconds remaining when paused

    class Config:
        arbitrary_types_allowed = True


class SubmitAthleteRequest(BaseModel):
    session_code: str
    athlete_name: str
    sport: str
    username: str


class CreateSessionRequest(BaseModel):
    """Request to create a new session with admin password."""

    password: str
    host_username: str  # Username of the person creating the session


class CreateSessionResponse(BaseModel):
    code: str
    created_at: datetime


class JoinSessionRequest(BaseModel):
    code: str
    username: str
