"""
Pydantic schemas for FastAPI – ANAF localities API.

Defines the structures used for serializing and validating data
in API responses. Compatible with SQLAlchemy Async ORM and Pydantic v2.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


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
