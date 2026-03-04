"""
Pydantic schemas for FastAPI – ANAF localities API.

Defines the structures used for serializing and validating data
in API responses. Compatible with SQLAlchemy Async ORM and Pydantic v2.
"""

from typing import List, Optional
import re

from pydantic import BaseModel, ConfigDict, field_serializer


# ============================================================
# Helpers (strip prefix stradal)
# ============================================================

_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    # Stradă
    r"str\.?|strada|"
    # Bulevard
    r"bd\.?|bld\.?|blvd\.?|bulevard(?:ul)?|"
    # Alee
    r"alee(?:a)?|"
    # Intrare
    r"intr\.?|intrarea|"
    # Calea
    r"cal\.?|calea|"
    # Șosea / Sos.
    r"șos\.?|sos\.?|șoseaua|soseaua|"
    # Piață (variante)
    r"p-?ța\.?|piata|piața|"
    # Splai / Prelungire / Drum / Fundătură
    r"splai(?:ul)?|"
    r"prel\.?|prelungirea|"
    r"dr\.?|drumul|"
    r"fund\.?|fundatura|fundătur(?:a|ă)|"
    # Pasaj / Pod / Dig
    r"pasaj(?:ul)?|" r"pod(?:ul)?|" r"dig(?:ul)?" r")\s+",
    flags=re.IGNORECASE,
)


def strip_road_prefix(denumire: str) -> str:
    """Remove common Romanian street prefixes from the beginning of the string."""
    if not denumire:
        return denumire
    cleaned = _PREFIX_PATTERN.sub("", denumire.strip(), count=1)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


# ============================================================
# 🏙 STRĂZI
# ============================================================
class StradaBase(BaseModel):
    """Base schema for a street (stradă)."""

    cod: int
    denumire: str


class StradaOut(StradaBase):
    """Output schema for a street (used in responses)."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("denumire")
    def _serialize_denumire(self, v: str) -> str:
        # IMPORTANT: doar pentru output JSON; nu modifică DB
        return strip_road_prefix(v)


# ============================================================
# 🏘 LOCALITĂȚI
# ============================================================
class LocalitateBase(BaseModel):
    """Base schema for a locality (localitate)."""

    cod: int
    denumire: str


class LocalitateOut(LocalitateBase):
    """Output schema for a locality with optional list of streets."""

    strazi: Optional[List[StradaOut]] = None
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 🏞 JUDEȚE
# ============================================================
class JudetBase(BaseModel):
    """Base schema for a county (județ)."""

    cod: int
    denumire: str
    model_config = ConfigDict(from_attributes=True)


class JudetOut(JudetBase):
    """Output schema for a county with optional list of localities."""

    localitati: Optional[List[LocalitateOut]] = None
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 🔍 SEARCH RESULTS
# ============================================================
class SearchResult(BaseModel):
    """Simplified schema for search results."""

    id: int
    cod: int
    denumire: str
    judet: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 🔑 AUTENTIFICARE (opțional pentru token)
# ============================================================
class Token(BaseModel):
    """Schema for access and refresh tokens."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Request body for refreshing an access token."""

    refresh_token: str


class TokenData(BaseModel):
    """Payload stored inside a JWT token."""

    username: Optional[str] = None
