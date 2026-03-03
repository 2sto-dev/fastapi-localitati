"""
SQLAlchemy models defining the database schema.

These classes represent the three hierarchical layers of Romania's
nomenclatures provided by ANAF: counties (județe), localities
(localități) and streets (străzi). Each model defines relationships
between the tables, so queries can easily traverse the hierarchy.

The `cod` field on each table corresponds to the unique code used by
ANAF. We also include an auto-incrementing primary key `id` for
internal relational purposes. Unique constraints ensure we don't
accidentally insert duplicate rows when syncing data from the external
API.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<User(username='{self.username}')>"



class Judet(Base):
    """Represents a Romanian county (județ).

    Attributes:
        id: Primary key used internally by SQLAlchemy.
        cod: Unique two-digit code identifying the county in the ANAF API.
        denumire: Full name of the county.
        localitati: One-to-many relationship to associated localities.
    """

    __tablename__ = "judete"

    id = Column(Integer, primary_key=True, index=True)
    cod = Column(Integer, unique=True, index=True, nullable=False)
    denumire = Column(String(100, collation="utf8mb4_romanian_ci"), nullable=False)

    # Establish a relationship to Localitate. When a Judet is deleted,
    # cascade the deletion to its localities and their streets.
    localitati = relationship(
        "Localitate",
        back_populates="judet",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Judet(cod={self.cod}, denumire='{self.denumire}')>"


class Localitate(Base):
    """Represents a locality belonging to a county.

    Attributes:
        id: Primary key used internally by SQLAlchemy.
        cod: Unique code identifying the locality in the ANAF API.
        denumire: Name of the locality.
        judet_id: Foreign key referencing the parent county.
        judet: Relationship back to the parent Judet.
        strazi: One-to-many relationship to associated streets.
    """

    __tablename__ = "localitati"

    id = Column(Integer, primary_key=True, index=True)
    cod = Column(Integer, index=True, nullable=False)
    denumire = Column(String(150, collation="utf8mb4_romanian_ci"), nullable=False)
    judet_id = Column(Integer, ForeignKey("judete.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("cod", "judet_id", name="uix_localitate_judet"),
    )

    # Relationship definitions
    judet = relationship("Judet", back_populates="localitati")
    strazi = relationship(
        "Strada", back_populates="localitate", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Localitate(cod={self.cod}, denumire='{self.denumire}', judet_id={self.judet_id})>"


class Strada(Base):
    """Represents a street belonging to a locality.

    Attributes:
        id: Primary key used internally by SQLAlchemy.
        cod: Unique code identifying the street in the ANAF API.
        denumire: Street name.
        localitate_id: Foreign key referencing the parent locality.
        localitate: Relationship back to the parent Localitate.
    """

    __tablename__ = "strazi"

    id = Column(Integer, primary_key=True, index=True)
    cod = Column(Integer, index=True, nullable=False)
    denumire = Column(String(200, collation="utf8mb4_romanian_ci"), nullable=False)
    localitate_id = Column(Integer, ForeignKey("localitati.id"), nullable=False)

    # Relationship definition
    localitate = relationship("Localitate", back_populates="strazi")

    # Ensure we don't insert duplicate streets for the same locality. The
    # combination of street code and locality must be unique.
    __table_args__ = (UniqueConstraint("cod", "localitate_id", name="uix_strada_localitate"),)

    def __repr__(self) -> str:
        return f"<Strada(cod={self.cod}, denumire='{self.denumire}', localitate_id={self.localitate_id})>"