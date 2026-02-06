import string
import random
from datetime import datetime, timedelta
from models import Session, Athlete, DisconnectedUser, RejectedSubmission
from typing import Optional, Dict, List
from collections import Counter
import logging

logger = logging.getLogger(__name__)

# In-memory session storage
sessions: Dict[str, Session] = {}


def generate_session_code(length: int = 6) -> str:
    """Generate a random alphanumeric session code."""
    characters = string.ascii_uppercase + string.digits
    code = "".join(random.choices(characters, k=length))

    # Ensure uniqueness
    while code in sessions:
        code = "".join(random.choices(characters, k=length))

    return code


def create_session(host_username: Optional[str] = None) -> Session:
    """Create a new session with optional host."""
    code = generate_session_code()
    session = Session(
        code=code,
        status="waiting",
        created_at=datetime.utcnow(),
        host_username=host_username,
    )
    sessions[code] = session
    logger.info(f"Created session: {code} (host: {host_username})")
    return session


def get_session(code: str) -> Optional[Session]:
    """Get session by code."""
    return sessions.get(code)


def start_session(code: str) -> bool:
    """Start the game timer for a session."""
    session = sessions.get(code)
    if not session:
        return False

    if session.status != "waiting":
        return False

    session.status = "active"
    session.started_at = datetime.utcnow()
    session.ends_at = session.started_at + timedelta(hours=2)
    logger.info(f"Started session {code}, ends at {session.ends_at}")
    return True


def end_session(code: str) -> bool:
    """End a session."""
    session = sessions.get(code)
    if not session:
        return False

    session.status = "completed"
    logger.info(f"Ended session {code}, final count: {len(session.athletes)}")
    return True


def add_athlete(code: str, athlete: Athlete) -> bool:
    """Add an athlete to the session."""
    session = sessions.get(code)
    if not session:
        return False

    session.athletes.append(athlete)
    session.athlete_names.add(athlete.normalized_name)

    # Track entity ID for duplicate detection
    if athlete.entity_id:
        session.athlete_entity_ids.add(athlete.entity_id)

    return True


def add_rejected_submission(
    code: str, name: str, sport: str, username: str, reason: str
) -> bool:
    """Record a rejected submission."""
    session = sessions.get(code)
    if not session:
        return False

    rejection = RejectedSubmission(
        name=name,
        sport=sport,
        username=username,
        reason=reason,
        submitted_at=datetime.utcnow(),
    )
    session.rejected_submissions.append(rejection)
    logger.info(
        f"Recorded rejected submission: {name} by {username} (reason: {reason})"
    )
    return True


def is_duplicate(
    code: str, normalized_name: str, entity_id: Optional[str] = None
) -> bool:
    """
    Check if athlete is duplicate.

    When entity_id is provided, it is authoritative — only the entity ID is checked.
    This prevents false positives when two different athletes share a search term
    (e.g., Cristiano Ronaldo vs Ronaldo Nazário both found via "ronaldo").

    Falls back to normalized name check only when no entity_id is available.
    """
    session = sessions.get(code)
    if not session:
        return False

    if entity_id:
        # Entity ID is authoritative — only check by ID
        return entity_id in session.athlete_entity_ids

    # No entity ID available — fall back to name check
    return normalized_name in session.athlete_names


def get_non_duplicate_entity_ids(code: str, entity_ids: list) -> list:
    """
    Filter a list of entity IDs to return only those not already submitted.

    Used during disambiguation to check if there are still valid options
    (e.g., "Ronaldo" submitted with Cristiano, but Brazilian Ronaldo still available).

    Args:
        code: Session code
        entity_ids: List of potential entity IDs

    Returns:
        List of entity IDs that are NOT already in the session
    """
    session = sessions.get(code)
    if not session:
        return entity_ids

    return [eid for eid in entity_ids if eid not in session.athlete_entity_ids]


def are_all_entity_ids_duplicates(code: str, entity_ids: list) -> bool:
    """
    Check if ALL entity IDs in a list are already submitted.

    Used to determine if we should show "duplicate" error vs "disambiguation_required".

    Returns:
        True if all entity IDs are duplicates (no valid options left)
        False if at least one entity ID is still available
    """
    if not entity_ids:
        return False

    non_duplicates = get_non_duplicate_entity_ids(code, entity_ids)
    return len(non_duplicates) == 0


def add_connected_user(code: str, socket_id: str, username: str) -> bool:
    """Add a user to the session."""
    session = sessions.get(code)
    if not session:
        return False

    # Clean up any stale connections with this username (e.g., from broken sockets)
    stale_sids = [
        sid for sid, uname in session.connected_users.items() if uname == username
    ]
    for stale_sid in stale_sids:
        del session.connected_users[stale_sid]
        logger.info(f"Cleaned up stale connection for {username} (sid: {stale_sid})")

    # Check if reconnecting from disconnected state
    if username in session.disconnected_users:
        del session.disconnected_users[username]
        logger.info(f"User {username} reconnected to session {code}")

    session.connected_users[socket_id] = username
    return True


def remove_connected_user(code: str, socket_id: str) -> Optional[str]:
    """Remove a user from connected list, add to disconnected."""
    session = sessions.get(code)
    if not session or socket_id not in session.connected_users:
        return None

    username = session.connected_users[socket_id]
    del session.connected_users[socket_id]

    # Add to disconnected users with 5-minute reservation
    submissions_count = sum(1 for a in session.athletes if a.submitted_by == username)
    session.disconnected_users[username] = DisconnectedUser(
        disconnected_at=datetime.utcnow(), submissions_count=submissions_count
    )

    logger.info(f"User {username} disconnected from session {code}")
    return username


def is_username_taken(code: str, username: str) -> bool:
    """Check if username is currently in use (connected)."""
    session = sessions.get(code)
    if not session:
        return False

    return username in session.connected_users.values()


def is_username_taken_by_other(code: str, username: str, requesting_sid: str) -> bool:
    """
    Check if username is held by a DIFFERENT active socket.

    During Socket.IO transport negotiation (polling -> websocket upgrade),
    the same user may get a new socket ID before the old one is cleaned up.
    This function returns False if the only socket holding this username is
    stale (i.e., not the requesting socket), allowing add_connected_user()
    to clean it up gracefully instead of rejecting the join.

    Returns True only if a genuinely different connection holds the username.
    """
    session = sessions.get(code)
    if not session:
        return False

    for sid, uname in session.connected_users.items():
        if uname == username and sid != requesting_sid:
            return True

    return False


def can_reclaim_username(code: str, username: str) -> bool:
    """Check if username can be reclaimed (disconnected < 5 min ago)."""
    session = sessions.get(code)
    if not session or username not in session.disconnected_users:
        return False

    disconnect_info = session.disconnected_users[username]
    time_since_disconnect = datetime.utcnow() - disconnect_info.disconnected_at

    # 5 minute reservation window
    return time_since_disconnect < timedelta(minutes=5)


def get_user_submissions_count(code: str, username: str) -> int:
    """Get number of submissions by a user."""
    session = sessions.get(code)
    if not session:
        return 0

    return sum(1 for a in session.athletes if a.submitted_by == username)


def find_session_by_socket(socket_id: str) -> Optional[Session]:
    """Find which session a socket ID belongs to."""
    for session in sessions.values():
        if socket_id in session.connected_users:
            return session
    return None


def is_host(code: str, username: str) -> bool:
    """Check if a user is the host of a session."""
    session = sessions.get(code)
    if not session:
        return False
    return session.host_username == username


def get_leaderboard(code: str) -> List[dict]:
    """
    Get leaderboard data for a session.
    Returns list of {username, score, rank} sorted by score descending.
    """
    session = sessions.get(code)
    if not session:
        return []

    # Count submissions per user
    submission_counts = Counter(a.submitted_by for a in session.athletes)

    # Get all users (both connected and disconnected who have participated)
    all_usernames = set(session.connected_users.values())
    all_usernames.update(session.disconnected_users.keys())

    # Add any user who submitted athletes but might not be tracked
    all_usernames.update(submission_counts.keys())

    # Build leaderboard
    leaderboard = []
    for username in all_usernames:
        leaderboard.append(
            {"username": username, "score": submission_counts.get(username, 0)}
        )

    # Sort by score descending, then by username for stability
    leaderboard.sort(key=lambda x: (-x["score"], x["username"]))

    # Add ranks
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1

    return leaderboard


def pause_session(code: str) -> Optional[int]:
    """
    Pause an active session. Records the time remaining so we can resume later.

    Returns the number of seconds remaining at pause, or None if the session
    cannot be paused (not found, not active, or already paused).
    """
    session = sessions.get(code)
    if not session:
        return None
    if session.status != "active" or session.is_paused:
        return None

    now = datetime.utcnow()
    remaining = int((session.ends_at - now).total_seconds())
    remaining = max(remaining, 0)

    session.is_paused = True
    session.paused_at = now
    session.time_remaining_at_pause = remaining

    logger.info(f"Session {code} paused with {remaining}s remaining")
    return remaining


def resume_session(code: str) -> Optional[datetime]:
    """
    Resume a paused session. Calculates new ends_at from the stored remaining time.

    Returns the new ends_at datetime, or None if the session cannot be resumed.
    """
    session = sessions.get(code)
    if not session:
        return None
    if session.status != "active" or not session.is_paused:
        return None

    now = datetime.utcnow()
    remaining = session.time_remaining_at_pause or 0
    session.ends_at = now + timedelta(seconds=remaining)

    session.is_paused = False
    session.paused_at = None
    session.time_remaining_at_pause = None

    logger.info(f"Session {code} resumed, new ends_at: {session.ends_at}")
    return session.ends_at


def remove_user_by_username(code: str, target_username: str) -> Optional[str]:
    """
    Remove a user from the session by username (host kicks a player).

    Unlike disconnect (which preserves the user in disconnected_users for reconnection),
    this fully removes the user from the session.

    Returns the socket_id of the removed user, or None if not found.
    """
    session = sessions.get(code)
    if not session:
        return None

    # Find the socket ID for this username
    target_sid = None
    for sid, uname in session.connected_users.items():
        if uname == target_username:
            target_sid = sid
            break

    if target_sid:
        del session.connected_users[target_sid]
        logger.info(
            f"User {target_username} removed from session {code} (sid: {target_sid})"
        )
    else:
        # User might be in disconnected_users
        if target_username in session.disconnected_users:
            del session.disconnected_users[target_username]
            logger.info(
                f"Disconnected user {target_username} removed from session {code}"
            )
        else:
            logger.warning(
                f"User {target_username} not found in session {code} for removal"
            )
            return None

    return target_sid


def get_users_with_status(code: str) -> List[dict]:
    """
    Get all users with their connection status.
    Returns list of {username, is_connected, is_host}.
    """
    session = sessions.get(code)
    if not session:
        return []

    users = []
    connected_usernames = set(session.connected_users.values())

    # Add connected users
    for username in connected_usernames:
        users.append(
            {
                "username": username,
                "is_connected": True,
                "is_host": username == session.host_username,
            }
        )

    # Add disconnected users
    for username in session.disconnected_users.keys():
        if username not in connected_usernames:
            users.append(
                {
                    "username": username,
                    "is_connected": False,
                    "is_host": username == session.host_username,
                }
            )

    # Sort: host first, then connected, then by username
    users.sort(key=lambda x: (not x["is_host"], not x["is_connected"], x["username"]))

    return users
