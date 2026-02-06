"""
Unit tests for session_manager module.
Tests duplicate detection, session lifecycle, and user management.
"""

import pytest
from datetime import datetime, timedelta
from models import Athlete
import session_manager as sm


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear all sessions before and after each test."""
    sm.sessions.clear()
    yield
    sm.sessions.clear()


class TestIsDuplicate:
    """Tests for the is_duplicate function — entity ID vs name-based detection."""

    def _create_session_with_athlete(self, entity_id: str, normalized_name: str) -> str:
        """Helper: create a session and add one athlete, return session code."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        athlete = Athlete(
            name="Test Athlete",
            normalized_name=normalized_name,
            sport="Q5372",
            submitted_by="user1",
            submitted_at=datetime.utcnow(),
            validated=True,
            entity_id=entity_id,
        )
        sm.add_athlete(code, athlete)
        return code

    def test_same_entity_id_is_duplicate(self):
        """Same entity ID should be detected as duplicate."""
        code = self._create_session_with_athlete("Q11571", "cristiano ronaldo")
        assert sm.is_duplicate(code, "cristiano ronaldo", "Q11571") is True

    def test_different_entity_id_not_duplicate(self):
        """Different entity ID should NOT be duplicate, even if normalized name matches."""
        code = self._create_session_with_athlete("Q11571", "ronaldo")
        # Different entity (Ronaldo Nazario Q36041) sharing search term "ronaldo"
        assert sm.is_duplicate(code, "ronaldo", "Q36041") is False

    def test_no_entity_id_falls_back_to_name(self):
        """When no entity_id provided, fall back to name-based check."""
        code = self._create_session_with_athlete("Q11571", "cristiano ronaldo")
        # No entity ID — name match should catch it
        assert sm.is_duplicate(code, "cristiano ronaldo") is True

    def test_no_entity_id_different_name_not_duplicate(self):
        """When no entity_id and different name, not a duplicate."""
        code = self._create_session_with_athlete("Q11571", "cristiano ronaldo")
        assert sm.is_duplicate(code, "lionel messi") is False

    def test_entity_id_authoritative_over_name(self):
        """Entity ID check should NOT fall through to name check.
        This is the core Ronaldo bug fix — two different athletes sharing
        the same search term must both be submittable."""
        code = self._create_session_with_athlete("Q11571", "ronaldo")

        # Submit "ronaldo" again but it resolves to a DIFFERENT entity (R9)
        # Old bug: name "ronaldo" was in athlete_names, so it returned True
        # Fixed: entity_id Q36041 is not in athlete_entity_ids, so returns False
        assert sm.is_duplicate(code, "ronaldo", "Q36041") is False

    def test_nonexistent_session_returns_false(self):
        """Non-existent session should return False."""
        assert sm.is_duplicate("INVALID", "test", "Q123") is False

    def test_multiple_athletes_different_entities(self):
        """Multiple athletes with different entity IDs should all be accepted."""
        session = sm.create_session(host_username="testhost")
        code = session.code

        # Add Cristiano Ronaldo
        sm.add_athlete(
            code,
            Athlete(
                name="Cristiano Ronaldo",
                normalized_name="ronaldo",
                sport="Q2736",
                submitted_by="user1",
                submitted_at=datetime.utcnow(),
                validated=True,
                entity_id="Q11571",
            ),
        )

        # Ronaldo Nazario should NOT be duplicate
        assert sm.is_duplicate(code, "ronaldo", "Q36041") is False

        # Add Ronaldo Nazario
        sm.add_athlete(
            code,
            Athlete(
                name="Ronaldo Nazário",
                normalized_name="ronaldo",
                sport="Q2736",
                submitted_by="user2",
                submitted_at=datetime.utcnow(),
                validated=True,
                entity_id="Q36041",
            ),
        )

        # Now BOTH should be duplicates
        assert sm.is_duplicate(code, "ronaldo", "Q11571") is True
        assert sm.is_duplicate(code, "ronaldo", "Q36041") is True


class TestGetNonDuplicateEntityIds:
    """Tests for the get_non_duplicate_entity_ids function."""

    def test_filters_existing_ids(self):
        """Should filter out entity IDs already in the session."""
        session = sm.create_session(host_username="testhost")
        code = session.code

        sm.add_athlete(
            code,
            Athlete(
                name="Cristiano Ronaldo",
                normalized_name="cristiano ronaldo",
                sport="Q2736",
                submitted_by="user1",
                submitted_at=datetime.utcnow(),
                validated=True,
                entity_id="Q11571",
            ),
        )

        result = sm.get_non_duplicate_entity_ids(code, ["Q11571", "Q36041"])
        assert result == ["Q36041"]

    def test_all_new_ids_returned(self):
        """When none are duplicates, all should be returned."""
        session = sm.create_session(host_username="testhost")
        code = session.code

        result = sm.get_non_duplicate_entity_ids(code, ["Q11571", "Q36041"])
        assert result == ["Q11571", "Q36041"]


class TestPauseSession:
    """Tests for the pause_session function."""

    def _create_active_session(self) -> str:
        """Helper: create and start a session, return code."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.start_session(code)
        return code

    def test_pause_active_session(self):
        """Should pause an active session and return remaining time."""
        code = self._create_active_session()
        result = sm.pause_session(code)
        assert result is not None
        assert result > 0
        session = sm.get_session(code)
        assert session.is_paused is True
        assert session.paused_at is not None
        assert session.time_remaining_at_pause == result

    def test_pause_nonexistent_session(self):
        """Should return None for nonexistent session."""
        result = sm.pause_session("INVALID")
        assert result is None

    def test_pause_waiting_session(self):
        """Should return None if session is not active."""
        session = sm.create_session(host_username="testhost")
        result = sm.pause_session(session.code)
        assert result is None

    def test_pause_already_paused(self):
        """Should return None if already paused."""
        code = self._create_active_session()
        sm.pause_session(code)
        result = sm.pause_session(code)
        assert result is None

    def test_pause_records_correct_remaining_time(self):
        """Remaining time should roughly match ends_at minus now."""
        code = self._create_active_session()
        session = sm.get_session(code)
        expected_remaining = int((session.ends_at - datetime.utcnow()).total_seconds())
        actual_remaining = sm.pause_session(code)
        # Allow 2 second tolerance for test execution time
        assert abs(actual_remaining - expected_remaining) <= 2


class TestResumeSession:
    """Tests for the resume_session function."""

    def _create_paused_session(self) -> str:
        """Helper: create, start, and pause a session, return code."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.start_session(code)
        sm.pause_session(code)
        return code

    def test_resume_paused_session(self):
        """Should resume a paused session and return new ends_at."""
        code = self._create_paused_session()
        session = sm.get_session(code)
        stored_remaining = session.time_remaining_at_pause

        new_ends_at = sm.resume_session(code)
        assert new_ends_at is not None
        session = sm.get_session(code)
        assert session.is_paused is False
        assert session.paused_at is None
        assert session.time_remaining_at_pause is None
        # New ends_at should be approximately now + stored_remaining
        expected_ends = datetime.utcnow() + timedelta(seconds=stored_remaining)
        delta = abs((new_ends_at - expected_ends).total_seconds())
        assert delta <= 2

    def test_resume_nonexistent_session(self):
        """Should return None for nonexistent session."""
        result = sm.resume_session("INVALID")
        assert result is None

    def test_resume_not_paused(self):
        """Should return None if session is not paused."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.start_session(code)
        result = sm.resume_session(code)
        assert result is None

    def test_resume_waiting_session(self):
        """Should return None if session is still waiting."""
        session = sm.create_session(host_username="testhost")
        result = sm.resume_session(session.code)
        assert result is None


class TestRemoveUserByUsername:
    """Tests for the remove_user_by_username function."""

    def test_remove_connected_user(self):
        """Should remove a connected user and return their socket ID."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.add_connected_user(code, "sid_host", "testhost")
        sm.add_connected_user(code, "sid_player", "player1")

        result = sm.remove_user_by_username(code, "player1")
        assert result == "sid_player"
        session = sm.get_session(code)
        assert "sid_player" not in session.connected_users
        assert "player1" not in session.connected_users.values()

    def test_remove_disconnected_user(self):
        """Should remove a disconnected user (returns None for sid since not connected)."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.add_connected_user(code, "sid_player", "player1")
        sm.remove_connected_user(code, "sid_player")  # disconnects the user
        session = sm.get_session(code)
        assert "player1" in session.disconnected_users

        result = sm.remove_user_by_username(code, "player1")
        # Returns None because user was disconnected (no active socket)
        assert result is None
        session = sm.get_session(code)
        assert "player1" not in session.disconnected_users

    def test_remove_nonexistent_user(self):
        """Should return None for nonexistent user."""
        session = sm.create_session(host_username="testhost")
        result = sm.remove_user_by_username(session.code, "ghost")
        assert result is None

    def test_remove_nonexistent_session(self):
        """Should return None for nonexistent session."""
        result = sm.remove_user_by_username("INVALID", "player1")
        assert result is None

    def test_host_remains_after_removing_player(self):
        """Host should still be connected after removing another player."""
        session = sm.create_session(host_username="testhost")
        code = session.code
        sm.add_connected_user(code, "sid_host", "testhost")
        sm.add_connected_user(code, "sid_player", "player1")

        sm.remove_user_by_username(code, "player1")
        session = sm.get_session(code)
        assert "testhost" in session.connected_users.values()
        assert len(session.connected_users) == 1
