"""
API endpoint tests for the Athletes 2000 Challenge backend.
Tests FastAPI REST endpoints using httpx.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from sports_config import initialize_sports_cache


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _init_sports_cache():
    """Ensure sports cache is populated before tests that need it."""
    await initialize_sports_cache()


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_status(self):
        """Test that the root endpoint returns a running status."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "2000 Athletes" in data["message"]


class TestSessionEndpoints:
    """Tests for session-related endpoints."""

    # Test credentials - must match ADMIN_PASSWORD in .env or default
    VALID_PASSWORD = "admin900"
    TEST_HOST = "testhost"

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a new session with valid credentials."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/session/create",
                json={"password": self.VALID_PASSWORD, "host_username": self.TEST_HOST},
            )

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert len(data["code"]) == 6  # Session codes are 6 characters
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_session_invalid_password(self):
        """Test that invalid password is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/session/create",
                json={"password": "wrongpassword", "host_username": self.TEST_HOST},
            )

        assert response.status_code == 403
        assert "Invalid admin password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_session_missing_host(self):
        """Test that missing host_username is rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/session/create",
                json={"password": self.VALID_PASSWORD, "host_username": ""},
            )

        assert response.status_code == 400
        assert "Host username is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting session details."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First create a session
            create_response = await client.post(
                "/api/session/create",
                json={"password": self.VALID_PASSWORD, "host_username": self.TEST_HOST},
            )
            session_code = create_response.json()["code"]

            # Then get its details
            response = await client.get(f"/api/session/{session_code}")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == session_code
        assert data["status"] == "waiting"
        assert data["count"] == 0
        assert data["host_username"] == self.TEST_HOST

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test getting a non-existent session."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/session/INVALID")

        assert response.status_code == 404


class TestSportsEndpoint:
    """Tests for the sports endpoint."""

    @pytest.mark.asyncio
    async def test_get_sports(self):
        """Test getting the list of available sports."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/sports")

        assert response.status_code == 200
        data = response.json()
        assert "sports" in data
        assert len(data["sports"]) > 0

        # Values are now Wikidata Q-IDs (e.g., "Q5372")
        sport_values = [s["value"] for s in data["sports"]]
        sport_labels = [s["label"].lower() for s in data["sports"]]

        # All values should be Q-IDs
        for val in sport_values:
            assert val.startswith("Q"), f"Sport value '{val}' is not a Q-ID"

        # Common sports should be present by label (dynamic list from Wikidata or fallback)
        assert any("basketball" in label for label in sport_labels)
        assert any("tennis" in label for label in sport_labels)

    @pytest.mark.asyncio
    async def test_sports_have_required_fields(self):
        """Test that each sport has the required fields."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/sports")

        data = response.json()
        for sport in data["sports"]:
            assert "value" in sport, "Sport missing 'value' field"
            assert "label" in sport, "Sport missing 'label' field"
            assert "wikidata_id" in sport, "Sport missing 'wikidata_id' field"
            # value and wikidata_id should be the same Q-ID
            assert sport["value"] == sport["wikidata_id"]


class TestDisplayNameOverrides:
    """Tests for user-friendly display name overrides."""

    @pytest.mark.asyncio
    async def test_association_football_override(self):
        """Test that 'association football' is displayed as 'Football (Soccer)'."""
        from sports_config import get_sport_label

        label = get_sport_label("Q2736")
        assert label == "Football (Soccer)"

    @pytest.mark.asyncio
    async def test_mma_override(self):
        """Test that 'mixed martial arts' is displayed as 'MMA / Mixed Martial Arts'."""
        from sports_config import get_sport_label

        label = get_sport_label("Q114466")
        assert label == "MMA / Mixed Martial Arts"

    @pytest.mark.asyncio
    async def test_athletics_override(self):
        """Test that 'athletics' is displayed as 'Athletics (Track & Field)'."""
        from sports_config import get_sport_label

        label = get_sport_label("Q542")
        assert label == "Athletics (Track & Field)"

    @pytest.mark.asyncio
    async def test_overrides_in_api_response(self):
        """Test that overridden labels appear in the /api/sports response."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/sports")

        data = response.json()
        labels = {s["value"]: s["label"] for s in data["sports"]}

        # Q2736 should be overridden
        if "Q2736" in labels:
            assert labels["Q2736"] == "Football (Soccer)"

    @pytest.mark.asyncio
    async def test_non_overridden_sport_keeps_original_label(self):
        """Test that sports without overrides keep their Wikidata label."""
        from sports_config import get_sport_label

        # Basketball (Q5372) has no override — should keep original label
        label = get_sport_label("Q5372")
        assert label is not None
        assert "basketball" in label.lower()
