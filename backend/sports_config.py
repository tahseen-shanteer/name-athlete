"""
Dynamic sports list from Wikidata.

Fetches all "type of sport" (Q31629) items from Wikidata at startup
and caches them in memory. The list is served via /api/sports.

Wikidata's sport classification is inconsistent: some major sports
(e.g. American football, rugby) are only tagged as P31:Q216048 (team sport)
rather than P31:Q31629 (type of sport). To ensure comprehensive coverage,
we merge SPARQL results with a curated list of well-known sports that
Wikidata doesn't classify under Q31629.
"""

import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Wikimedia-compliant User-Agent
USER_AGENT = "Athletes2000ChallengeBot/1.0 (https://github.com/athletes2000; athletes2000challenge@example.com) Python/aiohttp"

# In-memory cache: populated once at startup
# List of {"value": "Q5372", "label": "basketball", "wikidata_id": "Q5372"}
_sports_cache: list[dict] = []

# Quick lookup: label (lowercase) -> wikidata Q-ID
_label_to_qid: dict[str, str] = {}

# Quick lookup: Q-ID -> label
_qid_to_label: dict[str, str] = {}

# User-friendly display name overrides for Wikidata sport labels.
# Wikidata labels can be overly technical or confusing (e.g., "association football").
# This map overrides the label used in the UI while keeping the Q-ID unchanged
# for SPARQL matching. Applied during cache initialization.
_DISPLAY_NAME_OVERRIDES: dict[str, str] = {
    "Q2736": "Football (Soccer)",  # "association football"
    "Q114466": "MMA / Mixed Martial Arts",  # "mixed martial arts"
    "Q542": "Athletics (Track & Field)",  # "athletics"
    "Q41323": "American Football",  # normalize casing
    "Q131359": "Pro Wrestling",  # "professional wrestling"
    "Q5386": "Auto Racing / Motorsport",  # "auto racing"
    "Q5378": "Rugby",  # "rugby"
}

# Sports that Wikidata doesn't classify as P31:Q31629 (type of sport) but
# should be included. These are typically tagged only as P31:Q216048 (team sport),
# P31:Q877517 (ball game), or other narrow classes.
_SUPPLEMENTAL_SPORTS: list[dict] = [
    {"value": "Q41323", "label": "American football", "wikidata_id": "Q41323"},
    {"value": "Q5849", "label": "rugby union", "wikidata_id": "Q5849"},
    {"value": "Q10962", "label": "rugby league", "wikidata_id": "Q10962"},
    {"value": "Q131359", "label": "professional wrestling", "wikidata_id": "Q131359"},
    {"value": "Q5369", "label": "baseball", "wikidata_id": "Q5369"},
    {"value": "Q1455", "label": "field hockey", "wikidata_id": "Q1455"},
    {"value": "Q7707", "label": "water polo", "wikidata_id": "Q7707"},
    {"value": "Q38108", "label": "curling", "wikidata_id": "Q38108"},
    {"value": "Q7275", "label": "lacrosse", "wikidata_id": "Q7275"},
    {
        "value": "Q170746",
        "label": "Australian rules football",
        "wikidata_id": "Q170746",
    },
    {"value": "Q46952", "label": "softball", "wikidata_id": "Q46952"},
    {"value": "Q5378", "label": "rugby", "wikidata_id": "Q5378"},
]


def _parse_sparql_bindings(bindings: list[dict]) -> list[dict]:
    """
    Parse SPARQL result bindings into sport dicts, deduplicating
    and filtering out unresolved labels.
    """
    sports = []
    seen_qids: set[str] = set()

    for binding in bindings:
        sport_uri = binding.get("sport", {}).get("value", "")
        label = binding.get("sportLabel", {}).get("value", "")

        if not sport_uri or not label:
            continue

        # Extract Q-ID from URI (e.g., "http://www.wikidata.org/entity/Q5372" -> "Q5372")
        qid = sport_uri.split("/")[-1]
        if not qid.startswith("Q"):
            continue

        # Skip duplicates by Q-ID
        if qid in seen_qids:
            continue
        seen_qids.add(qid)

        # Skip labels that are just Q-IDs (unresolved labels)
        if label.startswith("Q") and label[1:].isdigit():
            continue

        sports.append(
            {
                "value": qid,
                "label": label,
                "wikidata_id": qid,
            }
        )

    return sports


def _merge_sport_lists(*sport_lists: list[dict]) -> list[dict]:
    """
    Merge multiple sport lists, deduplicating by Q-ID.
    Earlier lists take priority for label naming.
    """
    seen_qids: set[str] = set()
    merged: list[dict] = []

    for sports in sport_lists:
        for sport in sports:
            qid = sport["wikidata_id"]
            if qid not in seen_qids:
                seen_qids.add(qid)
                merged.append(sport)

    # Sort alphabetically by label
    merged.sort(key=lambda s: s["label"].lower())
    return merged


async def fetch_sports_from_wikidata() -> list[dict]:
    """
    Fetch all 'type of sport' items from Wikidata using SPARQL, then merge
    with supplemental sports that Wikidata doesn't classify under Q31629.
    Returns a sorted list of sport dicts with value (Q-ID), label, and wikidata_id.
    """
    sparql_query = """
    SELECT ?sport ?sportLabel WHERE {
      ?sport wdt:P31 wd:Q31629 .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ORDER BY ?sportLabel
    """

    endpoint = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    params = {"query": sparql_query}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    logger.error(
                        f"Wikidata sports query failed with status {response.status}"
                    )
                    return []

                data = await response.json()
                bindings = data.get("results", {}).get("bindings", [])

                sparql_sports = _parse_sparql_bindings(bindings)
                logger.info(f"Fetched {len(sparql_sports)} sports from Wikidata SPARQL")

                # Merge SPARQL results with supplemental sports list
                all_sports = _merge_sport_lists(sparql_sports, _SUPPLEMENTAL_SPORTS)
                logger.info(
                    f"Total sports after merging supplemental list: {len(all_sports)}"
                )
                return all_sports

    except Exception as e:
        logger.error(f"Failed to fetch sports from Wikidata: {e}")
        return []


async def initialize_sports_cache():
    """
    Fetch sports from Wikidata and populate the in-memory cache.
    Called once at application startup.
    Falls back to a minimal hardcoded list if Wikidata is unreachable.
    """
    global _sports_cache, _label_to_qid, _qid_to_label

    sports = await fetch_sports_from_wikidata()

    if not sports:
        logger.warning("Wikidata unreachable, using fallback sports list")
        sports = _get_fallback_sports()

    # Apply display name overrides for user-friendly labels
    for sport in sports:
        qid = sport["wikidata_id"]
        if qid in _DISPLAY_NAME_OVERRIDES:
            sport["label"] = _DISPLAY_NAME_OVERRIDES[qid]

    _sports_cache = sports

    # Build lookup indices
    _label_to_qid = {}
    _qid_to_label = {}
    for sport in sports:
        _label_to_qid[sport["label"].lower()] = sport["wikidata_id"]
        _qid_to_label[sport["wikidata_id"]] = sport["label"]

    logger.info(f"Sports cache initialized with {len(_sports_cache)} sports")


def get_cached_sports() -> list[dict]:
    """Return the cached sports list."""
    return _sports_cache


def get_sport_qid(label: str) -> Optional[str]:
    """
    Get the Wikidata Q-ID for a sport label (case-insensitive).
    Returns None if not found.
    """
    return _label_to_qid.get(label.lower())


def get_sport_label(qid: str) -> Optional[str]:
    """
    Get the label for a sport Q-ID.
    Returns None if not found.
    """
    return _qid_to_label.get(qid)


def is_valid_sport_qid(qid: str) -> bool:
    """Check if a Q-ID is a known sport."""
    return qid in _qid_to_label


def _get_fallback_sports() -> list[dict]:
    """
    Minimal fallback sports list used only when Wikidata is unreachable.
    These are the most common sports with their known Q-IDs.
    """
    return [
        {"value": "Q5372", "label": "basketball", "wikidata_id": "Q5372"},
        {"value": "Q2736", "label": "association football", "wikidata_id": "Q2736"},
        {"value": "Q41323", "label": "American football", "wikidata_id": "Q41323"},
        {"value": "Q5369", "label": "baseball", "wikidata_id": "Q5369"},
        {"value": "Q847", "label": "tennis", "wikidata_id": "Q847"},
        {"value": "Q5377", "label": "golf", "wikidata_id": "Q5377"},
        {"value": "Q41466", "label": "ice hockey", "wikidata_id": "Q41466"},
        {"value": "Q31920", "label": "swimming", "wikidata_id": "Q31920"},
        {"value": "Q542", "label": "athletics", "wikidata_id": "Q542"},
        {"value": "Q32112", "label": "boxing", "wikidata_id": "Q32112"},
        {"value": "Q114466", "label": "mixed martial arts", "wikidata_id": "Q114466"},
        {"value": "Q5375", "label": "cricket", "wikidata_id": "Q5375"},
        {"value": "Q5849", "label": "rugby union", "wikidata_id": "Q5849"},
        {"value": "Q10962", "label": "rugby league", "wikidata_id": "Q10962"},
        {"value": "Q53121", "label": "cycling", "wikidata_id": "Q53121"},
        {"value": "Q5765", "label": "skiing", "wikidata_id": "Q5765"},
        {"value": "Q61067", "label": "gymnastics", "wikidata_id": "Q61067"},
        {"value": "Q1734", "label": "volleyball", "wikidata_id": "Q1734"},
        {"value": "Q12117", "label": "wrestling", "wikidata_id": "Q12117"},
        {"value": "Q5386", "label": "auto racing", "wikidata_id": "Q5386"},
        {
            "value": "Q131359",
            "label": "professional wrestling",
            "wikidata_id": "Q131359",
        },
        {"value": "Q1455", "label": "field hockey", "wikidata_id": "Q1455"},
        {"value": "Q7707", "label": "water polo", "wikidata_id": "Q7707"},
        {"value": "Q38108", "label": "curling", "wikidata_id": "Q38108"},
        {"value": "Q7275", "label": "lacrosse", "wikidata_id": "Q7275"},
        {
            "value": "Q170746",
            "label": "Australian rules football",
            "wikidata_id": "Q170746",
        },
        {"value": "Q46952", "label": "softball", "wikidata_id": "Q46952"},
    ]
