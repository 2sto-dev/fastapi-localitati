"""
FastAPI entry point for ANAF full synchronization (all counties).
"""

import os
import logging
import asyncio
from fastapi import FastAPI, Depends
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every

from fastapi_localitati.database import Base, engine, async_session_maker
from fastapi_localitati import auth, models
from fastapi_localitati.scripts.sync_anaf import sync_all_judete
from fastapi_localitati.routers.localitati import router as localitati_router
from fastapi_localitati.settings import get_settings
from sqlalchemy import select, func

from fastapi_localitati.auth import get_password_hash


# ============================================================
# 🔊 Logging
# ============================================================
settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("anaf_sync")

# ============================================================
# 🚀 Inițializare aplicație
# ============================================================
app = FastAPI(
    title="ANAF Full Nomenclatoare Sync API",
    default_response_class=ORJSONResponse,
)

# Security: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Security: minimal HTTP security headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    path = request.url.path

    # 🔥 Nu aplica CSP pentru Swagger/OpenAPI
    if (
        path.startswith("/docs")
        or path.startswith("/openapi.json")
        or path.startswith("/redoc")
    ):
        return response

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")

    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "connect-src 'self'; "
        "font-src 'self' data:",
    )

    return response


# Include API routers
app.include_router(auth.router)
app.include_router(localitati_router)


# ============================================================
# 🧱 Inițializare tabele DB
# ============================================================
async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database schema ready.")


# ============================================================
# 🟢 Startup: sincronizare automată pentru toate județele
# ============================================================
async def run_initial_sync():
    logger.info("🚀 Sincronizare automată completă ANAF…")
    async with async_session_maker() as session:
        await sync_all_judete(session)
    logger.info("✅ Sincronizare completă cu succes.")


async def seed_admin_user() -> None:
    if not settings.SEED_ADMIN_ON_STARTUP:
        return
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        logger.warning(
            "SEED_ADMIN_ON_STARTUP=true dar lipsesc ADMIN_USERNAME/ADMIN_PASSWORD; omit seeding."
        )
        return
    async with async_session_maker() as session:
        res = await session.execute(
            select(models.User).where(models.User.username == settings.ADMIN_USERNAME)
        )
        user = res.scalars().first()
        if user:
            logger.info(
                "Admin user '%s' există deja; omit seeding.", settings.ADMIN_USERNAME
            )
            return
        user = models.User(
            username=settings.ADMIN_USERNAME,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        logger.info("✅ Seeded admin user '%s'", settings.ADMIN_USERNAME)


@app.on_event("startup")
async def startup_event():
    await init_models()
    await seed_admin_user()
    # rulează sincronizarea inițială în fundal, fără să blocheze startup-ul
    asyncio.create_task(run_initial_sync())


# ============================================================
# ⏰ Sincronizare săptămânală
# ============================================================
@app.on_event("startup")
@repeat_every(seconds=60 * 60 * 24 * 7, wait_first=True)
async def weekly_sync():
    logger.info("🔁 Weekly synchronisation with ANAF (all counties)…")
    async with async_session_maker() as session:
        await sync_all_judete(session)
    logger.info("✅ Weekly sync done.")


# ============================================================
# 🏠 Endpoint principal
# ============================================================
@app.get("/")
async def root():
    return {
        "message": "✅ ANAF Sync API — toate județele. Folosește /token pentru autentificare."
    }


@app.get("/api/judete/stats")
async def get_all_judete(
    _: models.User = Depends(auth.get_current_user),
    __: None = Depends(auth.rate_limiter),
):
    """
    Returnează toate județele cu numărul de localități și străzi.
    """
    async with async_session_maker() as session:
        # număr localități / străzi per județ
        result = await session.execute(
            select(
                models.Judet.id,
                models.Judet.cod,
                models.Judet.denumire,
                func.count(func.distinct(models.Localitate.id)).label("nr_localitati"),
                func.count(func.distinct(models.Strada.id)).label("nr_strazi"),
            )
            .join(
                models.Localitate,
                models.Judet.id == models.Localitate.judet_id,
                isouter=True,
            )
            .join(
                models.Strada,
                models.Localitate.id == models.Strada.localitate_id,
                isouter=True,
            )
            .group_by(models.Judet.id)
            .order_by(models.Judet.cod)
        )

        rows = result.all()
        if not rows:
            return {"status": "empty", "message": "Nu există date în baza de date."}

        judete = [
            {
                "id": r.id,
                "cod": r.cod,
                "denumire": r.denumire,
                "nr_localitati": r.nr_localitati,
                "nr_strazi": r.nr_strazi,
            }
            for r in rows
        ]

        return {"total_judete": len(judete), "judete": judete}


# ============================================================
# 🔻 Shutdown: eliberează conexiunile async
# ============================================================
@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()
    logger.info("🧹 Async engine disposed.")
