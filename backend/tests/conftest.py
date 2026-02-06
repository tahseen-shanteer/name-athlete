"""
Pytest configuration and fixtures for the Athletes 2000 Challenge backend tests.
"""

import pytest
import sys
import os

# Add the backend directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def clear_validation_cache():
    """Clear the validation cache before each test."""
    from validation import validation_cache

    validation_cache.clear()
    yield
    validation_cache.clear()


@pytest.fixture
def sample_athletes():
    """Sample athlete data for testing (using Wikidata Q-IDs for sports)."""
    return [
        {
            "name": "LeBron James",
            "sport": "Q5372",
            "expected_valid": True,
        },  # basketball
        {
            "name": "Michael Jordan",
            "sport": "Q5372",
            "expected_valid": True,
        },  # basketball
        {
            "name": "Lionel Messi",
            "sport": "Q2736",
            "expected_valid": True,
        },  # association football
        {"name": "Serena Williams", "sport": "Q847", "expected_valid": True},  # tennis
        {
            "name": "Tom Brady",
            "sport": "Q41323",
            "expected_valid": True,
        },  # American football
        {"name": "Mike Trout", "sport": "Q5369", "expected_valid": True},  # baseball
        {"name": "Usain Bolt", "sport": "Q542", "expected_valid": True},  # athletics
        {
            "name": "FakePersonXYZ123",
            "sport": "Q5372",
            "expected_valid": False,
        },  # basketball
    ]


@pytest.fixture
def wrong_sport_athletes():
    """Athletes with wrong sport selections for testing (using Q-IDs)."""
    return [
        {
            "name": "LeBron James",
            "sport": "Q2736",
            "expected_valid": False,
        },  # soccer (wrong)
        {
            "name": "Lionel Messi",
            "sport": "Q5372",
            "expected_valid": False,
        },  # basketball (wrong)
    ]
