import socketio
import asyncio
from datetime import datetime
from models import Athlete
from validation import validate_athlete_full, normalize_name, sanitize_athlete_name
from sports_config import get_sport_label, is_valid_sport_qid
import session_manager as sm
import logging

logger = logging.getLogger(__name__)

# Active timer tasks
timer_tasks = {}


def verify_sender(code: str, sid: str, username: str) -> bool:
    """
    Verify that the socket ID (sid) is actually connected as the claimed username.
    Prevents spoofing where any socket claims to be any user.
    """
    session = sm.get_session(code)
    if not session:
        return False
    return session.connected_users.get(sid) == username


async def handle_join_session(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle user joining a session."""
    code = data.get("code")
    username = data.get("username")

    if not code or not username:
        await sio.emit("error", {"message": "Missing code or username"}, room=sid)
        return

    session = sm.get_session(code)
    if not session:
        await sio.emit("error", {"message": "Session not found"}, room=sid)
        return

    # Prevent joining completed sessions
    if session.status == "completed":
        await sio.emit("error", {"message": "This session has ended"}, room=sid)
        return

    # Check if user is reconnecting (takes priority over username check)
    is_reconnecting = sm.can_reclaim_username(code, username)

    # Check if username is taken by a DIFFERENT active socket.
    # add_connected_user() cleans up stale sockets for the same username,
    # so transport reconnections (same user, new socket) are handled gracefully.
    # We only reject if the username is held by a socket that is NOT stale.
    if not is_reconnecting and sm.is_username_taken_by_other(code, username, sid):
        await sio.emit("error", {"message": "Username already in use"}, room=sid)
        return

    # Add user to session (cleans up stale sockets for same username first)
    sm.add_connected_user(code, sid, username)

    # Join Socket.IO room
    await sio.enter_room(sid, code)

    # Get user list and leaderboard
    users_with_status = sm.get_users_with_status(code)
    leaderboard = sm.get_leaderboard(code)

    # Send full state to the joining user
    your_submissions = sm.get_user_submissions_count(code, username)
    is_host = sm.is_host(code, username)

    await sio.emit(
        "session_joined",
        {
            "code": session.code,
            "status": session.status,
            "started_at": session.started_at.isoformat()
            if session.started_at
            else None,
            "ends_at": session.ends_at.isoformat() if session.ends_at else None,
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
            "count": len(session.athletes),
            "users": users_with_status,
            "your_submissions": your_submissions,
            "reconnected": is_reconnecting,
            "is_host": is_host,
            "host_username": session.host_username,
            "leaderboard": leaderboard,
            "is_paused": session.is_paused,
            "time_remaining_at_pause": session.time_remaining_at_pause,
        },
        room=sid,
    )

    # Notify others in the room with updated user list
    await sio.emit(
        "user_joined",
        {
            "username": username,
            "users": users_with_status,
            "user_count": len(session.connected_users),
            "reconnected": is_reconnecting,
        },
        room=code,
        skip_sid=sid,
    )

    logger.info(
        f"User {username} joined session {code} (reconnected: {is_reconnecting}, host: {is_host})"
    )


async def handle_start_game(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle game start request. Only host can start."""
    code = data.get("code")
    username = data.get("username")

    if not code:
        await sio.emit("error", {"message": "Missing session code"}, room=sid)
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit("error", {"message": "Authentication failed"}, room=sid)
        return

    session = sm.get_session(code)
    if not session:
        await sio.emit("error", {"message": "Session not found"}, room=sid)
        return

    # Verify the requester is the host
    if not sm.is_host(code, username):
        await sio.emit(
            "error", {"message": "Only the host can start the game"}, room=sid
        )
        return

    if session.status != "waiting":
        await sio.emit("error", {"message": "Game already started"}, room=sid)
        return

    # Start the session
    if not sm.start_session(code):
        await sio.emit("error", {"message": "Failed to start game"}, room=sid)
        return

    # Notify all users
    await sio.emit(
        "game_started",
        {
            "started_at": session.started_at.isoformat(),
            "ends_at": session.ends_at.isoformat(),
        },
        room=code,
    )

    # Start the timer task
    timer_tasks[code] = asyncio.create_task(run_timer(sio, code))

    logger.info(f"Game started for session {code} by host {username}")


async def handle_submit_athlete(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle athlete submission with full validation, entity tracking, and disambiguation."""
    code = data.get("session_code")
    athlete_name = data.get("athlete_name")
    sport = data.get("sport")
    username = data.get("username")
    hint = data.get("hint")  # Optional disambiguation hint

    if not all([code, athlete_name, sport, username]):
        await sio.emit(
            "submission_error",
            {"error": "missing_fields", "message": "Missing required fields"},
            room=sid,
        )
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit(
            "submission_error",
            {"error": "auth_failed", "message": "Authentication failed"},
            room=sid,
        )
        return

    # Validate sport Q-ID
    if not is_valid_sport_qid(sport):
        await sio.emit(
            "submission_error",
            {
                "error": "invalid_sport",
                "message": "Invalid sport selection. Please select a valid sport.",
            },
            room=sid,
        )
        return

    # Resolve sport label for display in messages
    sport_display = get_sport_label(sport) or sport

    # Sanitize athlete name input (blocks injection, invalid formats)
    is_valid_input, sanitized_name, sanitize_error = sanitize_athlete_name(athlete_name)
    if not is_valid_input:
        # Record rejected submission
        sm.add_rejected_submission(code, athlete_name, sport, username, "invalid_input")
        await sio.emit(
            "submission_error",
            {
                "error": "invalid_input",
                "message": sanitize_error or "Invalid athlete name",
            },
            room=sid,
        )
        return

    # Use sanitized name from here on
    athlete_name = sanitized_name

    session = sm.get_session(code)
    if not session:
        await sio.emit(
            "submission_error",
            {"error": "session_not_found", "message": "Session not found"},
            room=sid,
        )
        return

    if session.status != "active":
        await sio.emit(
            "submission_error",
            {"error": "game_not_active", "message": "Game is not active"},
            room=sid,
        )
        return

    if session.is_paused:
        await sio.emit(
            "submission_error",
            {
                "error": "game_paused",
                "message": "Game is paused. Wait for the host to resume.",
            },
            room=sid,
        )
        return

    # Normalize name for duplicate checking
    normalized = normalize_name(athlete_name)

    # Validate athlete (full validation with entity ID, disambiguation, and canonical name)
    try:
        (
            is_valid,
            error,
            validated_sports,
            api_succeeded,
            entity_id,
            multiple_matches,
            canonical_name,
            all_matching_ids,
        ) = await validate_athlete_full(athlete_name, sport, hint)

        # IMPORTANT: Check disambiguation BEFORE duplicate check
        # This allows "Ronaldo" to be submitted again after Cristiano Ronaldo was added
        if error == "disambiguation_required" and multiple_matches:
            # Check if there are still non-duplicate options available
            non_duplicate_ids = sm.get_non_duplicate_entity_ids(code, all_matching_ids)

            if len(non_duplicate_ids) == 0:
                # All matching athletes have been submitted - it's a duplicate
                sm.add_rejected_submission(
                    code, athlete_name, sport, username, "duplicate"
                )
                await sio.emit(
                    "submission_error",
                    {
                        "error": "duplicate",
                        "message": f"All athletes named '{athlete_name}' in {sport_display} have already been submitted",
                    },
                    room=sid,
                )
                return
            elif len(non_duplicate_ids) < len(all_matching_ids):
                # Some have been submitted, but others are still available
                # Still require disambiguation
                await sio.emit(
                    "submission_error",
                    {
                        "error": "disambiguation_required",
                        "message": f"Multiple athletes found with the name '{athlete_name}' in {sport_display}. Some have already been submitted. Please add a hint (team, country, or birth year) to identify a different player.",
                        "requires_hint": True,
                    },
                    room=sid,
                )
                return
            else:
                # No duplicates yet, still need disambiguation
                await sio.emit(
                    "submission_error",
                    {
                        "error": "disambiguation_required",
                        "message": f"Multiple athletes found with the name '{athlete_name}' in {sport_display}. Please add a hint (team, country, or birth year) to identify the specific player.",
                        "requires_hint": True,
                    },
                    room=sid,
                )
                return

        # Acquire session lock for atomic duplicate-check + add
        lock = sm.get_session_lock(code)
        async with lock:
            # Now check for duplicate using entity ID (catches "Messi" == "Lionel Messi")
            if entity_id and sm.is_duplicate(code, normalized, entity_id):
                # Record rejected submission
                sm.add_rejected_submission(
                    code, athlete_name, sport, username, "duplicate"
                )
                # Use canonical name in message if available
                display_name = canonical_name or athlete_name
                await sio.emit(
                    "submission_error",
                    {
                        "error": "duplicate",
                        "message": f"{display_name} has already been submitted",
                    },
                    room=sid,
                )
                return

            # Also check normalized name for fallback duplicate detection
            if not entity_id and sm.is_duplicate(code, normalized):
                # Record rejected submission
                sm.add_rejected_submission(
                    code, athlete_name, sport, username, "duplicate"
                )
                await sio.emit(
                    "submission_error",
                    {
                        "error": "duplicate",
                        "message": f"{athlete_name} has already been submitted",
                    },
                    room=sid,
                )
                return

            if not is_valid:
                # Record rejected submission
                sm.add_rejected_submission(
                    code, athlete_name, sport, username, error or "unknown"
                )

                error_messages = {
                    "invalid_athlete": f"{athlete_name} could not be verified as a real athlete",
                    "wrong_sport": f"No athlete found with that name for {sport_display}",
                    "validation_failed": "Validation service unavailable. Please try again.",
                }

                response_data = {
                    "error": error,
                    "message": error_messages.get(error, "Validation failed"),
                }

                await sio.emit("submission_error", response_data, room=sid)
                return

            # Create athlete entry (only reached if validation succeeded and no duplicate)
            # Use canonical name if available, otherwise use user input
            display_name = canonical_name if canonical_name else athlete_name

            athlete = Athlete(
                name=display_name,  # Store canonical name as primary name
                normalized_name=normalized,
                sport=sport,
                sport_display=sport_display,  # Human-readable sport label
                submitted_by=username,
                submitted_at=datetime.utcnow(),
                validated=True,  # Always true now since we reject on failure
                entity_id=entity_id,  # For entity-based duplicate detection
                hint=hint,  # Store hint if provided
                canonical_name=canonical_name,  # Also store separately for reference
            )

            # Add to session (inside lock — atomic with duplicate check)
            sm.add_athlete(code, athlete)

    except Exception as e:
        logger.error(f"Validation error: {e}")
        # Record rejected submission
        sm.add_rejected_submission(
            code, athlete_name, sport, username, "validation_failed"
        )
        # On API failure, reject the submission
        await sio.emit(
            "submission_error",
            {
                "error": "validation_failed",
                "message": "Validation service unavailable. Please try again.",
            },
            room=sid,
        )
        return

    # Get updated leaderboard
    leaderboard = sm.get_leaderboard(code)

    # Broadcast to all users in the room
    await sio.emit(
        "athlete_added",
        {
            "athlete": {
                "name": athlete.name,
                "sport": athlete.sport_display or athlete.sport,
                "submitted_by": athlete.submitted_by,
                "submitted_at": athlete.submitted_at.isoformat(),
                "validated": athlete.validated,
                "canonical_name": athlete.canonical_name,
            },
            "count": len(session.athletes),
        },
        room=code,
    )

    # Emit leaderboard update to all users
    await sio.emit(
        "leaderboard_update",
        {"leaderboard": leaderboard},
        room=code,
    )

    # Note: 2000 is a target, not a limit. Game continues until timer expires.

    logger.info(
        f"Athlete {display_name} added to session {code} by {username} (entity_id: {entity_id})"
    )


async def handle_pause_game(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle pause request. Only host can pause."""
    code = data.get("code")
    username = data.get("username")

    if not code or not username:
        await sio.emit("error", {"message": "Missing code or username"}, room=sid)
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit("error", {"message": "Authentication failed"}, room=sid)
        return

    if not sm.is_host(code, username):
        await sio.emit(
            "error", {"message": "Only the host can pause the game"}, room=sid
        )
        return

    time_remaining = sm.pause_session(code)
    if time_remaining is None:
        await sio.emit(
            "error",
            {"message": "Cannot pause game (not active or already paused)"},
            room=sid,
        )
        return

    # Cancel the timer task so it stops ticking
    if code in timer_tasks:
        timer_tasks[code].cancel()
        del timer_tasks[code]

    # Broadcast to all users
    await sio.emit(
        "game_paused",
        {"time_remaining": time_remaining},
        room=code,
    )

    logger.info(f"Game paused for session {code} by host {username}")


async def handle_resume_game(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle resume request. Only host can resume."""
    code = data.get("code")
    username = data.get("username")

    if not code or not username:
        await sio.emit("error", {"message": "Missing code or username"}, room=sid)
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit("error", {"message": "Authentication failed"}, room=sid)
        return

    if not sm.is_host(code, username):
        await sio.emit(
            "error", {"message": "Only the host can resume the game"}, room=sid
        )
        return

    new_ends_at = sm.resume_session(code)
    if new_ends_at is None:
        await sio.emit(
            "error",
            {"message": "Cannot resume game (not active or not paused)"},
            room=sid,
        )
        return

    # Restart the timer task
    timer_tasks[code] = asyncio.create_task(run_timer(sio, code))

    # Broadcast to all users
    await sio.emit(
        "game_resumed",
        {"ends_at": new_ends_at.isoformat()},
        room=code,
    )

    logger.info(f"Game resumed for session {code} by host {username}")


async def handle_end_game_early(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle early game end request. Only host can end."""
    code = data.get("code")
    username = data.get("username")

    if not code or not username:
        await sio.emit("error", {"message": "Missing code or username"}, room=sid)
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit("error", {"message": "Authentication failed"}, room=sid)
        return

    if not sm.is_host(code, username):
        await sio.emit("error", {"message": "Only the host can end the game"}, room=sid)
        return

    session = sm.get_session(code)
    if not session or session.status != "active":
        await sio.emit("error", {"message": "Game is not active"}, room=sid)
        return

    # End the game using the existing end_game function
    await end_game(sio, code)

    logger.info(f"Game ended early for session {code} by host {username}")


async def handle_remove_player(sio: socketio.AsyncServer, sid: str, data: dict):
    """Handle player removal request. Only host can remove players."""
    code = data.get("code")
    username = data.get("username")
    target_username = data.get("target_username")

    if not code or not username or not target_username:
        await sio.emit("error", {"message": "Missing required fields"}, room=sid)
        return

    # Verify the sender is who they claim to be
    if not verify_sender(code, sid, username):
        await sio.emit("error", {"message": "Authentication failed"}, room=sid)
        return

    if not sm.is_host(code, username):
        await sio.emit(
            "error", {"message": "Only the host can remove players"}, room=sid
        )
        return

    # Cannot remove yourself (the host)
    if target_username == username:
        await sio.emit("error", {"message": "Cannot remove yourself"}, room=sid)
        return

    target_sid = sm.remove_user_by_username(code, target_username)

    # Notify the removed player (if they're connected)
    if target_sid:
        await sio.emit(
            "player_removed",
            {
                "username": target_username,
                "message": "You have been removed from the session by the host.",
            },
            room=target_sid,
        )
        # Force leave the room
        await sio.leave_room(target_sid, code)

    # Get updated user list
    users_with_status = sm.get_users_with_status(code)
    leaderboard = sm.get_leaderboard(code)

    # Notify room about the removal
    await sio.emit(
        "user_removed",
        {
            "username": target_username,
            "users": users_with_status,
            "leaderboard": leaderboard,
        },
        room=code,
    )

    logger.info(
        f"Player {target_username} removed from session {code} by host {username}"
    )


async def handle_disconnect(sio: socketio.AsyncServer, sid: str):
    """Handle user disconnection."""
    session = sm.find_session_by_socket(sid)
    if not session:
        return

    username = sm.remove_connected_user(session.code, sid)
    if not username:
        return

    # Get updated user list
    users_with_status = sm.get_users_with_status(session.code)

    # Notify others
    await sio.emit(
        "user_left",
        {
            "username": username,
            "users": users_with_status,
            "user_count": len(session.connected_users),
            "reason": "disconnected",
        },
        room=session.code,
    )

    logger.info(f"User {username} disconnected from session {session.code}")


async def run_timer(sio: socketio.AsyncServer, code: str):
    """Run the countdown timer for a session."""
    session = sm.get_session(code)
    if not session or not session.ends_at:
        return

    try:
        while datetime.utcnow() < session.ends_at:
            remaining = (session.ends_at - datetime.utcnow()).total_seconds()
            if remaining <= 0:
                break

            await sio.emit("timer_tick", {"remaining": int(remaining)}, room=code)
            await asyncio.sleep(1)

        # Time's up
        await end_game(sio, code)

    except asyncio.CancelledError:
        logger.info(f"Timer cancelled for session {code}")
    except Exception as e:
        logger.error(f"Timer error for session {code}: {e}")


async def end_game(sio: socketio.AsyncServer, code: str):
    """End the game and notify all users. Idempotent — safe to call multiple times."""
    session = sm.get_session(code)
    if not session:
        return

    # Idempotency guard: if already completed, do nothing
    if session.status == "completed":
        return

    sm.end_session(code)

    # Cancel timer task if running
    if code in timer_tasks:
        timer_tasks[code].cancel()
        del timer_tasks[code]

    # Get final leaderboard
    leaderboard = sm.get_leaderboard(code)

    # Notify all users with final stats and rejected submissions
    await sio.emit(
        "game_ended",
        {
            "final_count": len(session.athletes),
            "goal_reached": len(session.athletes) >= 2000,
            "athletes": [
                {
                    "name": a.name,
                    "sport": a.sport_display or a.sport,
                    "submitted_by": a.submitted_by,
                    "validated": a.validated,
                }
                for a in session.athletes
            ],
            "leaderboard": leaderboard,
            "rejected_submissions": [
                {
                    "name": r.name,
                    "sport": get_sport_label(r.sport) or r.sport,
                    "username": r.username,
                }
                for r in session.rejected_submissions
            ],
        },
        room=code,
    )

    logger.info(f"Game ended for session {code}, final count: {len(session.athletes)}")


def register_events(sio: socketio.AsyncServer):
    """Register all Socket.IO event handlers."""

    @sio.event
    async def join_session(sid, data):
        await handle_join_session(sio, sid, data)

    @sio.event
    async def start_game(sid, data):
        await handle_start_game(sio, sid, data)

    @sio.event
    async def submit_athlete(sid, data):
        await handle_submit_athlete(sio, sid, data)

    @sio.event
    async def pause_game(sid, data):
        await handle_pause_game(sio, sid, data)

    @sio.event
    async def resume_game(sid, data):
        await handle_resume_game(sio, sid, data)

    @sio.event
    async def end_game_early(sid, data):
        await handle_end_game_early(sio, sid, data)

    @sio.event
    async def remove_player(sid, data):
        await handle_remove_player(sio, sid, data)

    @sio.event
    async def disconnect(sid):
        await handle_disconnect(sio, sid)
