"""
API router for exposing nomenclature data (asincron).

All endpoints are protected with JWT authentication and
return hierarchical data about counties, localities, and streets.
Use `/token` to obtain a JWT before calling these endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fastapi_localitati.database import async_session_maker
from fastapi_localitati.scripts.sync_anaf import sync_all_judete

from .. import models, schemas, auth
from ..auth import get_current_user, rate_limiter

router = APIRouter(prefix="/api", tags=["Localitati"])


# -------------------- DATABASE SESSION --------------------
async def get_db():
    """Dependency that provides an Async SQLAlchemy session."""
    async with async_session_maker() as session:
        yield session


# -------------------- JUDEȚE --------------------
@router.get("/judete", response_model=List[schemas.JudetBase])
async def read_judete(
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Return all counties (only cod, denumire)."""
    result = await db.execute(select(models.Judet))
    return result.scalars().all()


@router.get("/judete/{cod}", response_model=schemas.JudetOut)
async def read_judet(
    cod: int,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Return a single county by code with localities and streets."""
    result = await db.execute(
        select(models.Judet)
        .options(
            selectinload(models.Judet.localitati).selectinload(models.Localitate.strazi)
        )
        .filter(models.Judet.cod == cod)
    )
    judet = result.scalars().first()
    if not judet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Județul nu există"
        )
    return judet


# -------------------- LOCALITĂȚI --------------------
@router.get("/localitati/{cod_judet}", response_model=List[schemas.LocalitateOut])
async def read_localitati(
    cod_judet: int,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Return localities for a given county."""
    result = await db.execute(
        select(models.Judet).filter(models.Judet.cod == cod_judet)
    )
    judet = result.scalars().first()
    if not judet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Județul nu există"
        )

    result_localitati = await db.execute(
        select(models.Localitate)
        .options(selectinload(models.Localitate.strazi))
        .filter(models.Localitate.judet_id == judet.id)
    )
    return result_localitati.scalars().all()


# -------------------- STRĂZI --------------------
@router.get(
    "/strazi/{cod_judet}/{cod_localitate}", response_model=List[schemas.StradaOut]
)
async def read_strazi(
    cod_judet: int,
    cod_localitate: int,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Return streets for a specific locality."""
    result_judet = await db.execute(
        select(models.Judet).filter(models.Judet.cod == cod_judet)
    )
    judet = result_judet.scalars().first()
    if not judet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Județul nu există"
        )

    result_loc = await db.execute(
        select(models.Localitate).filter(
            models.Localitate.cod == cod_localitate,
            models.Localitate.judet_id == judet.id,
        )
    )
    localitate = result_loc.scalars().first()
    if not localitate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Localitatea nu există"
        )

    result_strazi = await db.execute(
        select(models.Strada).filter(models.Strada.localitate_id == localitate.id)
    )
    return result_strazi.scalars().all()


# -------------------- REFRESH (ADMIN) --------------------
@router.post("/refresh")
async def refresh_data(
    user: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual refresh from ANAF (admin only)."""
    if user.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    await sync_all_judete(db)
    return {"status": "ok", "message": "Data refreshed from ANAF"}


# -------------------- SEARCH --------------------
@router.get("/search", response_model=List[schemas.LocalitateOut])
async def search_localitati(
    query: str,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Search localities by name."""
    result = await db.execute(
        select(models.Localitate)
        .options(selectinload(models.Localitate.strazi))
        .filter(models.Localitate.denumire.ilike(f"%{query}%"))
    )
    results = result.scalars().all()
    if not results:
        raise HTTPException(status_code=404, detail="Nicio localitate găsită")
    return results


# -------------------- TREE (Județ -> Localități -> Străzi) --------------------
@router.get("/tree", response_model=schemas.JudetOut)
async def read_tree(
    cod_judet: int,
    cod_localitate: Optional[int] = None,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    """Return a hierarchical tree for a county.

    - If cod_localitate is not provided: include all localities and their streets.
    - If cod_localitate is provided: include only that locality and its streets.
    """
    # First, get the county
    res_j = await db.execute(select(models.Judet).filter(models.Judet.cod == cod_judet))
    judet = res_j.scalars().first()
    if not judet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Județul nu există"
        )

    if cod_localitate is None:
        res_full = await db.execute(
            select(models.Judet)
            .options(
                selectinload(models.Judet.localitati).selectinload(
                    models.Localitate.strazi
                )
            )
            .filter(models.Judet.id == judet.id)
        )
        judet_full = res_full.scalars().first()
        return judet_full

    res_loc = await db.execute(
        select(models.Localitate)
        .options(selectinload(models.Localitate.strazi))
        .filter(
            models.Localitate.cod == cod_localitate,
            models.Localitate.judet_id == judet.id,
        )
    )
    localitate = res_loc.scalars().first()
    if not localitate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Localitatea nu există"
        )

    return schemas.JudetOut(
        cod=judet.cod,
        denumire=judet.denumire,
        localitati=[
            schemas.LocalitateOut.model_validate(localitate, from_attributes=True)
        ],
    )


@router.get("/autocomplete/judete", response_model=List[schemas.JudetBase])
async def autocomplete_judete(
    q: str,
    limit: int = 10,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Judet).filter(models.Judet.denumire.ilike(f"{q}%")).limit(limit)
    )
    return result.scalars().all()


@router.get("/autocomplete/localitati", response_model=List[schemas.LocalitateOut])
async def autocomplete_localitati(
    cod_judet: int,
    q: str,
    limit: int = 10,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    # găsește judet.id din cod
    res_j = await db.execute(select(models.Judet).filter(models.Judet.cod == cod_judet))
    judet = res_j.scalars().first()
    if not judet:
        raise HTTPException(status_code=404, detail="Județul nu există")

    res = await db.execute(
        select(models.Localitate)
        .options(selectinload(models.Localitate.strazi))
        .filter(
            models.Localitate.judet_id == judet.id,
            models.Localitate.denumire.ilike(f"{q}%"),
        )
        .limit(limit)
    )
    return res.scalars().all()


@router.get("/autocomplete/strazi", response_model=List[schemas.StradaOut])
async def autocomplete_strazi(
    cod_judet: int,
    cod_localitate: int,
    q: str,
    limit: int = 10,
    _: models.User = Depends(get_current_user),
    __: None = Depends(rate_limiter),
    db: AsyncSession = Depends(get_db),
):
    # găsește judet.id
    res_j = await db.execute(select(models.Judet).filter(models.Judet.cod == cod_judet))
    judet = res_j.scalars().first()
    if not judet:
        raise HTTPException(status_code=404, detail="Județul nu există")

    # găsește localitate.id
    res_l = await db.execute(
        select(models.Localitate).filter(
            models.Localitate.cod == cod_localitate,
            models.Localitate.judet_id == judet.id,
        )
    )
    loc = res_l.scalars().first()
    if not loc:
        raise HTTPException(status_code=404, detail="Localitatea nu există")

    res_s = await db.execute(
        select(models.Strada)
        .filter(
            models.Strada.localitate_id == loc.id,
            models.Strada.denumire.ilike(f"{q}%"),
        )
        .limit(limit)
    )
    return res_s.scalars().all()
