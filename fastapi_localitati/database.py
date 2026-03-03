"""
Asynchronous SQLAlchemy database configuration for the FastAPI ANAF sync app.
"""

import os
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Load environment variables from .env if present (early)
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# ============================================================
# ⚙️ CONFIGURARE CONEXIUNE LA BAZA DE DATE
# ============================================================

# Construim URL-ul DB DOAR din .env/.environment
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    DB_DRIVER = os.getenv("DB_DRIVER")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    if all([DB_DRIVER, DB_HOST, DB_PORT, DB_NAME]):
        pwd = quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
        auth = f"{DB_USER}:{pwd}@" if DB_USER else ""
        _db_url = f"{DB_DRIVER}://{auth}{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

if not _db_url:
    raise RuntimeError(
        "DATABASE_URL sau variabilele DB_DRIVER/DB_HOST/DB_PORT/DB_NAME trebuie setate în .env"
    )

DATABASE_URL = _db_url

# ============================================================
# 🚀 ENGINE ASINCRON
# ============================================================

engine = create_async_engine(
    DATABASE_URL, echo=False, pool_pre_ping=True, pool_recycle=3600, future=True
)

# ============================================================
# 🧱 FACTORY PENTRU SESIUNI ASINCRONE
# ============================================================

async_session_maker = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)

# ============================================================
# 🧬 BAZA COMUNĂ PENTRU MODELE ORM
# ============================================================

Base = declarative_base()
