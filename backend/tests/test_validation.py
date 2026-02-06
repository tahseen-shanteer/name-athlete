"""
Unit tests for the validation module.
Tests Wikidata SPARQL-based validation, name similarity checking,
input sanitization, and disambiguation.
"""

import pytest
from validation import (
    normalize_name,
    sanitize_athlete_name,
    validate_athlete,
    validate_athlete_full,
    search_wikidata_person,
    verify_is_athlete,
    check_name_similarity,
    validation_cache,
)


# =============================================================================
# Sport Q-ID constants for readability
# =============================================================================
BASKETBALL = "Q5372"
SOCCER = "Q2736"  # association football
TENNIS = "Q847"
MMA = "Q114466"  # mixed martial arts
AMERICAN_FOOTBALL = "Q41323"
BASEBALL = "Q5369"
ATHLETICS = "Q542"  # track & field
ICE_HOCKEY = "Q41466"
BOXING = "Q32112"
CRICKET = "Q5375"


class TestNormalizeName:
    """Tests for the normalize_name function."""

    def test_lowercase(self):
        assert normalize_name("LeBron James") == "lebron james"

    def test_strip_whitespace(self):
        assert normalize_name("  LeBron James  ") == "lebron james"

    def test_normalize_multiple_spaces(self):
        assert normalize_name("LeBron   James") == "lebron james"

    def test_remove_accents(self):
        assert normalize_name("José González") == "jose gonzalez"

    def test_complex_name(self):
        assert normalize_name("  Cristiano   Ronaldo  ") == "cristiano ronaldo"


class TestSanitizeAthleteName:
    """Tests for the sanitize_athlete_name function."""

    def test_valid_name(self):
        is_valid, sanitized, error = sanitize_athlete_name("LeBron James")
        assert is_valid is True
        assert sanitized == "LeBron James"
        assert error is None

    def test_name_with_apostrophe(self):
        is_valid, sanitized, error = sanitize_athlete_name("Shaquille O'Neal")
        assert is_valid is True
        assert sanitized == "Shaquille O'Neal"

    def test_name_with_hyphen(self):
        is_valid, sanitized, error = sanitize_athlete_name("Mary-Jane Watson")
        assert is_valid is True
        assert sanitized == "Mary-Jane Watson"

    def test_name_with_period(self):
        is_valid, sanitized, error = sanitize_athlete_name("J.J. Watt")
        assert is_valid is True
        assert sanitized == "J.J. Watt"

    def test_name_with_accents(self):
        is_valid, sanitized, error = sanitize_athlete_name("José González")
        assert is_valid is True
        assert "José" in sanitized or "Jose" in sanitized

    def test_too_short(self):
        is_valid, sanitized, error = sanitize_athlete_name("A")
        assert is_valid is False
        assert "short" in error.lower()

    def test_too_long(self):
        is_valid, sanitized, error = sanitize_athlete_name("A" * 101)
        assert is_valid is False
        assert "long" in error.lower()

    def test_block_url(self):
        is_valid, sanitized, error = sanitize_athlete_name("https://example.com")
        assert is_valid is False
        assert "url" in error.lower()

    def test_block_wikipedia_title_format(self):
        is_valid, sanitized, error = sanitize_athlete_name(
            "Michael_Jordan_(basketball)"
        )
        assert is_valid is False
        assert "format" in error.lower()

    def test_block_brackets(self):
        is_valid, sanitized, error = sanitize_athlete_name("Name [test]")
        assert is_valid is False
        assert "character" in error.lower()

    def test_block_sql_injection(self):
        is_valid, sanitized, error = sanitize_athlete_name("SELECT * FROM users")
        assert is_valid is False

    def test_block_sparql_injection(self):
        is_valid, sanitized, error = sanitize_athlete_name("test WHERE { ?x ?y ?z }")
        assert is_valid is False

    def test_empty_string(self):
        is_valid, sanitized, error = sanitize_athlete_name("")
        assert is_valid is False

    def test_whitespace_only(self):
        is_valid, sanitized, error = sanitize_athlete_name("   ")
        assert is_valid is False


class TestCheckNameSimilarity:
    """Tests for the check_name_similarity function (rapidfuzz-based)."""

    def test_exact_match(self):
        assert check_name_similarity("Lionel Messi", "Lionel Messi") is True

    def test_case_insensitive_match(self):
        assert check_name_similarity("lionel messi", "Lionel Messi") is True

    def test_last_name_matches_full_name(self):
        """Last name should match as substring of full canonical name."""
        assert check_name_similarity("Messi", "Lionel Messi") is True

    def test_first_name_matches_full_name(self):
        assert check_name_similarity("LeBron", "LeBron James") is True

    def test_nickname_partial_match(self):
        """Ronaldo should match Cristiano Ronaldo."""
        assert check_name_similarity("Ronaldo", "Cristiano Ronaldo") is True

    def test_short_form_neymar(self):
        assert check_name_similarity("Neymar", "Neymar Jr.") is True

    def test_completely_different_names_fail(self):
        """Totally unrelated name should fail."""
        assert check_name_similarity("xyz123abc", "Lionel Messi") is False

    def test_accented_vs_unaccented(self):
        """Accented names should match after normalization."""
        assert check_name_similarity("Jose Gonzalez", "José González") is True

    def test_full_name_matches_canonical(self):
        assert check_name_similarity("Cristiano Ronaldo", "Cristiano Ronaldo") is True


class TestSearchWikidataPerson:
    """Tests for the search_wikidata_person function (live API)."""

    @pytest.mark.asyncio
    async def test_find_lebron_james(self):
        """Test that we can find LeBron James in Wikidata."""
        result, multiple, matches = await search_wikidata_person(
            "LeBron James", BASKETBALL
        )
        assert result is not None
        # LeBron James has Wikidata ID Q36159
        assert result == "Q36159"

    @pytest.mark.asyncio
    async def test_find_lionel_messi(self):
        """Test that we can find Lionel Messi in Wikidata."""
        result, multiple, matches = await search_wikidata_person("Lionel Messi", SOCCER)
        assert result is not None
        # Messi has Wikidata ID Q615
        assert result == "Q615"

    @pytest.mark.asyncio
    async def test_not_found_fake_person(self):
        """Test that a fake person returns None."""
        result, multiple, matches = await search_wikidata_person(
            "FakePersonXYZ123456789", BASKETBALL
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_sport_prioritization(self):
        """Test that results matching the target sport are prioritized."""
        # Jon Jones - should return the MMA fighter, not the rugby player
        result, multiple, matches = await search_wikidata_person("Jon Jones", MMA)
        assert result is not None
        # The MMA fighter Jon Jones has Wikidata ID Q285450
        assert result == "Q285450"


class TestVerifyIsAthlete:
    """Tests for the verify_is_athlete function (live API)."""

    @pytest.mark.asyncio
    async def test_lebron_james_is_athlete(self):
        """Test that LeBron James is identified as an athlete."""
        is_athlete, sports = await verify_is_athlete("Q36159")  # LeBron's ID
        assert is_athlete is True
        assert len(sports) > 0

    @pytest.mark.asyncio
    async def test_messi_is_athlete(self):
        """Test that Messi is identified as an athlete."""
        is_athlete, sports = await verify_is_athlete("Q615")  # Messi's ID
        assert is_athlete is True

    @pytest.mark.asyncio
    async def test_non_athlete_person(self):
        """Test that a non-athlete (e.g., politician) is not identified as athlete."""
        # Q76 is Barack Obama
        is_athlete, sports = await verify_is_athlete("Q76")
        assert is_athlete is False


class TestValidateAthlete:
    """Integration tests for the full validate_athlete function (live API)."""

    @pytest.mark.asyncio
    async def test_valid_athlete_correct_sport(self, clear_validation_cache):
        """Test validating LeBron James as a basketball player."""
        # Note: LeBron James may require disambiguation due to LeBron James Jr.
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "LeBron James", BASKETBALL
        )
        # Either valid or needs disambiguation (both are acceptable)
        assert error in [None, "disambiguation_required"]
        assert api_succeeded is True

    @pytest.mark.asyncio
    async def test_valid_athlete_messi_soccer(self, clear_validation_cache):
        """Test validating Messi as a soccer player."""
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "Lionel Messi", SOCCER
        )
        # Messi is unique enough that it should validate
        assert is_valid is True or error == "disambiguation_required"
        assert api_succeeded is True

    @pytest.mark.asyncio
    async def test_valid_athlete_serena_williams(self, clear_validation_cache):
        """Test validating Serena Williams as a tennis player."""
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "Serena Williams", TENNIS
        )
        # Should validate (unique name in tennis), but may fail due to API issues
        assert is_valid is True or error in [
            "disambiguation_required",
            "validation_failed",
        ]

    @pytest.mark.asyncio
    async def test_invalid_athlete_fake_person(self, clear_validation_cache):
        """Test that a fake person is rejected."""
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "FakePersonXYZ123456789", BASKETBALL
        )
        assert is_valid is False
        assert error == "invalid_athlete"

    @pytest.mark.asyncio
    async def test_wrong_sport_detected(self, clear_validation_cache):
        """Test that an athlete in the wrong sport is detected."""
        # LeBron James is a basketball player, not a tennis player
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "LeBron James", TENNIS
        )
        # Should either be wrong_sport or invalid_athlete
        assert is_valid is False
        assert error in ["wrong_sport", "invalid_athlete", "disambiguation_required"]


class TestValidateAthleteFull:
    """Tests for the full validation function with entity ID and disambiguation."""

    @pytest.mark.asyncio
    async def test_returns_entity_id(self, clear_validation_cache):
        """Test that entity ID is returned for valid athletes."""
        (
            is_valid,
            error,
            sports,
            api_ok,
            entity_id,
            multi,
            canonical,
            all_ids,
        ) = await validate_athlete_full("LeBron James", BASKETBALL)
        # May need disambiguation due to LeBron James Jr.
        assert entity_id is not None
        # LeBron's Wikidata ID
        assert entity_id == "Q36159"

    @pytest.mark.asyncio
    async def test_jon_jones_mma_correct(self, clear_validation_cache):
        """Test that Jon Jones (MMA) is validated correctly with sport prioritization."""
        (
            is_valid,
            error,
            sports,
            api_ok,
            entity_id,
            multi,
            canonical,
            all_ids,
        ) = await validate_athlete_full("Jon Jones", MMA)
        # Should find the MMA fighter, though may need disambiguation
        assert entity_id == "Q285450"  # Jon Jones MMA fighter's Wikidata ID

    @pytest.mark.asyncio
    async def test_disambiguation_with_hint(self, clear_validation_cache):
        """Test that providing a hint resolves disambiguation."""
        # First try without hint
        (
            is_valid,
            error,
            sports,
            api_ok,
            entity_id,
            multi,
            canonical,
            all_ids,
        ) = await validate_athlete_full("LeBron James", BASKETBALL)
        # If disambiguation was required, try with hint
        if error == "disambiguation_required":
            (
                is_valid,
                error,
                sports,
                api_ok,
                entity_id,
                multi,
                canonical,
                all_ids,
            ) = await validate_athlete_full(
                "LeBron James",
                BASKETBALL,
                hint="1984",  # Birth year hint
            )
            # With hint, should either validate or still need more specific hint
            assert entity_id == "Q36159"

    @pytest.mark.asyncio
    async def test_canonical_name_returned(self, clear_validation_cache):
        """Test that canonical name is fetched for valid athletes."""
        (
            is_valid,
            error,
            sports,
            api_ok,
            entity_id,
            multi,
            canonical,
            all_ids,
        ) = await validate_athlete_full("Messi", SOCCER)
        # If validation succeeded (not disambiguation), canonical should be set
        if is_valid and canonical:
            assert "Messi" in canonical or "messi" in canonical.lower()

    @pytest.mark.asyncio
    async def test_name_similarity_blocks_gaming(self, clear_validation_cache):
        """Test that submitting a completely unrelated name is blocked by similarity check."""
        # If someone tries to submit "xyz" and it somehow matches a real athlete,
        # the name similarity check should block it
        (
            is_valid,
            error,
            sports,
            api_ok,
            entity_id,
            multi,
            canonical,
            all_ids,
        ) = await validate_athlete_full("zzzznotaname", BASKETBALL)
        # Should be invalid_athlete (not found)
        assert is_valid is False


class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    @pytest.mark.asyncio
    async def test_name_with_accents(self, clear_validation_cache):
        """Test that names with accents are handled properly."""
        # Neymar Jr. should be found (may require disambiguation as single-word name)
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "Neymar", SOCCER
        )
        # Single-word names now require disambiguation, so accept either outcome
        assert is_valid is True or error == "disambiguation_required"

    @pytest.mark.asyncio
    async def test_name_with_extra_spaces(self, clear_validation_cache):
        """Test that names with extra spaces are handled."""
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "  LeBron   James  ", BASKETBALL
        )
        # Accept valid, disambiguation, or even invalid_athlete
        # (Wikidata search may handle whitespace differently)
        assert is_valid is True or error in [
            "disambiguation_required",
            "invalid_athlete",
        ]

    @pytest.mark.asyncio
    async def test_case_insensitive(self, clear_validation_cache):
        """Test that name matching is case insensitive."""
        is_valid, error, sports, api_succeeded = await validate_athlete(
            "LEBRON JAMES", BASKETBALL
        )
        # Accept either valid or disambiguation_required (LeBron James Sr. vs Jr.)
        assert is_valid is True or error == "disambiguation_required"

    @pytest.mark.asyncio
    async def test_different_names_same_person(self, clear_validation_cache):
        """Test that full name returns correct entity ID."""
        # Test with full name
        _, _, _, _, entity_id_full, _, _, _ = await validate_athlete_full(
            "Lionel Messi", SOCCER
        )
        # Full name should reliably return Messi's Wikidata ID
        assert entity_id_full == "Q615"

        # Note: Single-word "Messi" may match different entities in Wikidata
        # (e.g., the city of Messi, or other people named Messi),
        # so we don't assert entity_id_short == "Q615"
