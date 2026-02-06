"""
Athlete validation engine using Wikidata.

Validates that a submitted name corresponds to a real athlete who plays
the specified sport. Uses a hybrid approach:
1. wbsearchentities API for fuzzy name search (handles typos, name variants)
2. SPARQL for athlete + sport verification using Wikidata Q-IDs
3. rapidfuzz for submitted name vs canonical name similarity check

No Wikipedia fallback -- Wikidata only.
"""

import aiohttp
import re
import logging
from unidecode import unidecode
from rapidfuzz import fuzz
from typing import Optional, Tuple
from sports_config import is_valid_sport_qid, get_sport_label

logger = logging.getLogger(__name__)

# Wikimedia-compliant User-Agent (required for API access)
USER_AGENT = "Athletes2000ChallengeBot/1.0 (https://github.com/athletes2000; athletes2000challenge@example.com) Python/aiohttp"

# Minimum fuzzy match ratio for submitted name vs canonical name
# This prevents gaming with very generic names like "James"
NAME_SIMILARITY_THRESHOLD = 45  # Out of 100 -- lenient to allow nicknames/last names

# In-memory cache for validation results
# Structure: {(normalized_name, sport_qid): validation_result_tuple}
validation_cache: dict = {}


def sanitize_athlete_name(name: str) -> Tuple[bool, str, Optional[str]]:
    """
    Sanitize and validate athlete name input.
    Blocks invalid inputs like URLs, code injection, Wikipedia title format.

    Returns: (is_valid, sanitized_name, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "", "Invalid input"

    name = name.strip()

    # Length checks
    if len(name) < 2:
        return False, name, "Name too short"
    if len(name) > 100:
        return False, name, "Name too long"

    # Block Wikipedia title format (underscores between words)
    if "_" in name and " " not in name:
        return False, name, "Invalid name format"

    # Block URLs
    if re.search(r"https?://|www\.", name, re.IGNORECASE):
        return False, name, "URLs not allowed"

    # Block code-like patterns (brackets, pipes, backslashes, etc.)
    if re.search(r"[{}\[\]<>|\\;`]", name):
        return False, name, "Invalid characters in name"

    # Block SPARQL/SQL injection attempts
    if re.search(
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|WHERE|FILTER|UNION)\b",
        name,
        re.IGNORECASE,
    ):
        return False, name, "Invalid input"

    # Allow: letters (including unicode/accented), spaces, hyphens, apostrophes, periods, commas
    sanitized = re.sub(r"[^a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\s\-'.,]+", "", name)
    sanitized = " ".join(sanitized.split())  # Normalize whitespace

    if len(sanitized) < 2:
        return False, sanitized, "Name contains too many invalid characters"

    if not re.search(r"[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]", sanitized):
        return False, sanitized, "Name must contain letters"

    return True, sanitized, None


def normalize_name(name: str) -> str:
    """Normalize athlete name for comparison and duplicate detection."""
    name = name.lower().strip()
    name = " ".join(name.split())  # Normalize whitespace
    name = unidecode(name)  # Remove accents: "José" → "jose"
    return name


def check_name_similarity(submitted: str, canonical: str) -> bool:
    """
    Check if the submitted name is similar enough to the canonical name.
    Uses rapidfuzz partial_ratio to handle nicknames, last names, etc.

    Examples that should pass:
      "Messi" vs "Lionel Messi" -> partial_ratio ~100
      "LeBron" vs "LeBron James" -> partial_ratio ~100
      "Ronaldo" vs "Cristiano Ronaldo" -> partial_ratio ~100
      "Neymar" vs "Neymar Jr." -> partial_ratio ~100

    Examples that should fail:
      "James" vs "LeBron James" -> we use a lenient threshold so this may pass
      "xyz123" vs "Lionel Messi" -> partial_ratio ~0
    """
    submitted_norm = normalize_name(submitted)
    canonical_norm = normalize_name(canonical)

    # Exact match after normalization
    if submitted_norm == canonical_norm:
        return True

    # Check if submitted is contained in canonical or vice versa
    if submitted_norm in canonical_norm or canonical_norm in submitted_norm:
        return True

    # Use rapidfuzz partial_ratio for fuzzy matching
    ratio = fuzz.partial_ratio(submitted_norm, canonical_norm)
    return ratio >= NAME_SIMILARITY_THRESHOLD


# =============================================================================
# Wikidata Search API (fuzzy name search)
# =============================================================================


async def _fetch_wikidata_search(name: str, limit: int = 5) -> list:
    """
    Fetch search results from Wikidata wbsearchentities API.
    This API has built-in fuzzy matching for name variants and typos.
    Returns list of search results with id and description.
    """
    search_name = name.strip().title()

    search_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": search_name,
        "language": "en",
        "type": "item",
        "format": "json",
        "limit": limit,
    }
    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession() as session:
        async with session.get(
            search_url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status != 200:
                logger.error(f"Wikidata search failed with status {response.status}")
                raise Exception(f"Wikidata search failed: {response.status}")

            data = await response.json()
            return data.get("search", [])


async def search_wikidata_person(
    name: str, sport_qid: str, hint: Optional[str] = None
) -> Tuple[Optional[str], bool, list]:
    """
    Search for a person in Wikidata by name, then verify via SPARQL that
    they are an athlete in the specified sport (by Q-ID).

    Uses progressive search: k=5 first (k=10 for single-word names).
    Disambiguation triggered when multiple candidates are confirmed athletes
    in the same sport.

    Args:
        name: Athlete name to search
        sport_qid: Wikidata Q-ID for the sport (e.g., "Q5372" for basketball)
        hint: Optional disambiguation hint (team, country, year, etc.)

    Returns:
        (entity_id, multiple_matches_found, all_matching_entity_ids)
    """
    try:
        is_single_word = len(name.strip().split()) == 1
        initial_limit = 10 if is_single_word else 5

        search_results = await _fetch_wikidata_search(name, limit=initial_limit)
        if not search_results:
            return None, False, []

        # Collect candidate entity IDs
        candidate_ids = [r.get("id") for r in search_results if r.get("id")]

        if not candidate_ids:
            return None, False, []

        # Batch-verify candidates via SPARQL: check which are athletes in the target sport
        verified = await _verify_athletes_for_sport(candidate_ids, sport_qid)

        if not verified:
            # No candidates matched -- try expanding search if we haven't already
            if initial_limit < 10:
                logger.info(
                    f"No sport match in k={initial_limit} for {name}, expanding to k=10"
                )
                search_results = await _fetch_wikidata_search(name, limit=10)
                candidate_ids = [r.get("id") for r in search_results if r.get("id")]
                verified = await _verify_athletes_for_sport(candidate_ids, sport_qid)

        if not verified:
            # Still nothing - return first candidate for general athlete check
            return candidate_ids[0] if candidate_ids else None, False, []

        # We have verified athlete(s) in the sport
        verified_ids = [v["entity_id"] for v in verified]

        # Disambiguation logic
        if len(verified_ids) > 1:
            # Multiple athletes match -- try to narrow down with hint
            if hint:
                hint_lower = hint.lower()
                # Search through original results for hint match in description
                hint_matches = []
                for result in search_results:
                    rid = result.get("id")
                    if rid in verified_ids:
                        description = result.get("description", "").lower()
                        if hint_lower in description:
                            hint_matches.append(rid)

                if len(hint_matches) == 1:
                    return hint_matches[0], False, verified_ids
                elif len(hint_matches) > 1:
                    return hint_matches[0], True, hint_matches
                # Hint didn't help -- still ambiguous

            # For single-word names, always require disambiguation
            if is_single_word:
                return verified_ids[0], True, verified_ids

            # For multi-word names with multiple matches, also disambiguate
            return verified_ids[0], True, verified_ids

        # Single match -- no disambiguation needed
        return verified_ids[0], False, verified_ids

    except Exception as e:
        logger.error(f"Error searching Wikidata: {e}")
        raise


# =============================================================================
# SPARQL Verification (sport Q-ID based)
# =============================================================================


async def _verify_athletes_for_sport(
    entity_ids: list[str], sport_qid: str
) -> list[dict]:
    """
    Verify which of the given entity IDs are athletes who play the specified sport.
    Uses a single SPARQL query with VALUES clause for batch checking.

    The query checks multiple paths to the sport:
    1. Occupation (P106) -> subclass of athlete (Q2066131) + sport (P641) on entity
    2. Occupation (P106) -> sport (P641) on the occupation
    3. Team membership (P54) -> team's sport (P641)
    4. Direct sport (P641) on entity

    Returns list of dicts with entity_id and sport_labels.
    """
    if not entity_ids:
        return []

    # Build VALUES clause
    values_str = " ".join(f"wd:{eid}" for eid in entity_ids if eid.startswith("Q"))
    if not values_str:
        return []

    sparql_query = f"""
    SELECT DISTINCT ?entity ?entityLabel ?sport ?sportLabel WHERE {{
      VALUES ?entity {{ {values_str} }}
      ?entity wdt:P31 wd:Q5 .  # Must be human

      # Find sports through multiple paths
      {{
        # Path 1: Occupation is subclass of athlete + entity has sport
        ?entity wdt:P106 ?occ .
        ?occ wdt:P279* wd:Q2066131 .
        ?entity wdt:P641 ?sport .
      }}
      UNION
      {{
        # Path 2: Occupation itself links to sport via P641
        ?entity wdt:P106 ?occ .
        ?occ wdt:P279* wd:Q2066131 .
        ?occ wdt:P641 ?sport .
      }}
      UNION
      {{
        # Path 3: Team membership -> team's sport
        ?entity wdt:P54 ?team .
        ?team wdt:P641 ?sport .
      }}
      UNION
      {{
        # Path 4: Direct sport property
        ?entity wdt:P641 ?sport .
      }}

      # Filter to the target sport (or any sport that is a subclass of it)
      FILTER(?sport = wd:{sport_qid} || EXISTS {{ ?sport wdt:P279* wd:{sport_qid} }})

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """

    try:
        results = await execute_sparql_query(sparql_query, timeout=20)
        if not results:
            return []

        bindings = results.get("results", {}).get("bindings", [])
        if not bindings:
            return []

        # Group by entity
        entities = {}
        for binding in bindings:
            entity_uri = binding.get("entity", {}).get("value", "")
            entity_id = entity_uri.split("/")[-1]
            sport_label = binding.get("sportLabel", {}).get("value", "")

            if entity_id not in entities:
                entities[entity_id] = {
                    "entity_id": entity_id,
                    "sport_labels": [],
                }
            if sport_label and sport_label not in entities[entity_id]["sport_labels"]:
                entities[entity_id]["sport_labels"].append(sport_label)

        return list(entities.values())

    except Exception as e:
        logger.error(f"SPARQL athlete verification failed: {e}")
        raise


async def verify_is_athlete(entity_id: str) -> Tuple[bool, list[str]]:
    """
    Check if an entity is an athlete (any sport).
    Returns (is_athlete, list_of_sport_labels).
    """
    sparql_query = f"""
    SELECT DISTINCT ?sportLabel WHERE {{
      wd:{entity_id} wdt:P31 wd:Q5 .
      {{
        wd:{entity_id} wdt:P106 ?occ .
        ?occ wdt:P279* wd:Q2066131 .
        OPTIONAL {{ wd:{entity_id} wdt:P641 ?sport . }}
      }}
      UNION
      {{
        wd:{entity_id} wdt:P641 ?sport .
      }}
      UNION
      {{
        wd:{entity_id} wdt:P54 ?team .
        ?team wdt:P641 ?sport .
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 10
    """

    try:
        results = await execute_sparql_query(sparql_query, timeout=15)
        if not results:
            return False, []

        bindings = results.get("results", {}).get("bindings", [])
        if not bindings:
            return False, []

        sports = []
        for binding in bindings:
            label = binding.get("sportLabel", {}).get("value", "")
            if label and label not in sports:
                sports.append(label)

        return True, sports if sports else ["athlete"]

    except Exception as e:
        logger.error(f"Error checking if {entity_id} is athlete: {e}")
        raise


# =============================================================================
# SPARQL Execution
# =============================================================================


async def execute_sparql_query(query: str, timeout: int = 15):
    """Execute SPARQL query against Wikidata endpoint."""
    endpoint = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    params = {"query": query}
    timeout_obj = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            endpoint, params=params, headers=headers, timeout=timeout_obj
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"Wikidata query failed with status {response.status}")
                raise Exception(f"Wikidata query failed: {response.status}")


# =============================================================================
# Entity Label Fetching
# =============================================================================


async def get_entity_label(entity_id: str) -> Optional[str]:
    """
    Fetch the canonical English label for a Wikidata entity.

    Args:
        entity_id: Wikidata Q-ID (e.g., "Q615" for Messi)

    Returns:
        The English label (e.g., "Lionel Messi") or None if not found
    """
    if not entity_id or not entity_id.startswith("Q"):
        return None

    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "ids": entity_id,
        "props": "labels",
        "languages": "en",
        "format": "json",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"Failed to fetch label for {entity_id}: {response.status}"
                    )
                    return None

                data = await response.json()
                entity_data = data.get("entities", {}).get(entity_id, {})
                labels = entity_data.get("labels", {})
                en_label = labels.get("en", {}).get("value")

                if en_label:
                    logger.info(f"Fetched canonical name for {entity_id}: {en_label}")
                    return en_label
                return None
    except Exception as e:
        logger.warning(f"Error fetching label for {entity_id}: {e}")
        return None


# =============================================================================
# Main Validation Entry Points
# =============================================================================


async def validate_athlete(
    name: str, sport_qid: str
) -> Tuple[bool, Optional[str], Optional[list], bool]:
    """
    Validate that an athlete exists and plays the given sport.

    Returns:
        (is_valid, error_message, validated_sports, api_succeeded)
    """
    (
        is_valid,
        error,
        sports,
        api_ok,
        _entity_id,
        _multi,
        _canonical,
        _all_ids,
    ) = await validate_athlete_full(name, sport_qid)
    return is_valid, error, sports, api_ok


async def validate_athlete_full(
    name: str, sport_qid: str, hint: Optional[str] = None
) -> Tuple[
    bool, Optional[str], Optional[list], bool, Optional[str], bool, Optional[str], list
]:
    """
    Full validation with entity ID, disambiguation support, canonical name,
    and name similarity verification.

    Args:
        name: Athlete name to validate
        sport_qid: Wikidata Q-ID for the sport (e.g., "Q5372")
        hint: Optional disambiguation hint

    Returns:
        (is_valid, error_message, validated_sports, api_succeeded,
         entity_id, multiple_matches, canonical_name, all_matching_ids)
    """
    try:
        # Step 1: Search for the person using Wikidata search API (has fuzzy matching)
        person_id, multiple_matches, all_matches = await search_wikidata_person(
            name, sport_qid, hint
        )

        if not person_id:
            return False, "invalid_athlete", None, True, None, False, None, []

        # Step 2: If search returned a candidate but no verified sport matches,
        # check if the person is an athlete at all
        if not all_matches:
            # The person was found by search but not verified for this sport
            # Check if they're an athlete in any sport
            is_athlete, athlete_sports = await verify_is_athlete(person_id)

            if not is_athlete:
                return False, "invalid_athlete", None, True, None, False, None, []

            # They're an athlete but not in the requested sport
            sport_label = get_sport_label(sport_qid) or sport_qid
            return (
                False,
                "wrong_sport",
                athlete_sports,
                True,
                None,  # Don't return entity_id for wrong sport
                False,
                None,
                [],
            )

        # Step 3: Check disambiguation
        if multiple_matches and not hint:
            return (
                False,
                "disambiguation_required",
                None,
                True,
                person_id,
                True,
                None,
                all_matches,
            )

        # Step 4: Fetch canonical name
        canonical_name = await get_entity_label(person_id)

        # Step 5: Verify submitted name similarity to canonical name
        if canonical_name and not check_name_similarity(name, canonical_name):
            logger.info(f"Name similarity check failed: '{name}' vs '{canonical_name}'")
            return (
                False,
                "invalid_athlete",
                None,
                True,
                None,
                False,
                None,
                [],
            )

        # All checks passed
        sport_label = get_sport_label(sport_qid) or sport_qid
        return (
            True,
            None,
            [sport_label],
            True,
            person_id,
            False,
            canonical_name,
            [],
        )

    except Exception as e:
        logger.error(f"Validation failed for {name}: {e}")
        return False, "validation_failed", None, False, None, False, None, []
