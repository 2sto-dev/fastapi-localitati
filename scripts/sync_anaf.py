"""
ANAF Full Synchronization Utility
→ Synchronizes all counties, localities, and streets into MySQL.
"""

import aiohttp
import asyncio
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiohttp.client_exceptions import ClientResponseError, ClientConnectorError, ServerTimeoutError

from fastapi_localitati import models
from fastapi_localitati.database import async_session_maker

ANAF_BASE_URL = "https://webnom.anaf.ro/Nomenclatoare/api/judete"


# ============================================================
# 🔧 get_or_create
# ============================================================
async def get_or_create(db: AsyncSession, model, defaults=None, **kwargs):
    result = await db.execute(select(model).filter_by(**kwargs))
    instance = result.scalars().first()
    if instance:
        return instance, False

    params = kwargs.copy()
    if defaults:
        params.update(defaults)

    instance = model(**params)
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance, True


# ============================================================
# 🌐 Fetch helper cu retry
# ============================================================
async def fetch_with_retry(session, url, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()
        except (ClientResponseError, ClientConnectorError, ServerTimeoutError, aiohttp.ClientError) as exc:
            print(f"⚠️ Eroare ({attempt}/{retries}) pentru {url}: {exc}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                print(f"❌ Eșuat definitiv pentru {url}")
                return None


# ============================================================
# 🔁 Sincronizare completă
# ============================================================
async def sync_all_judete(db: AsyncSession):
    print("\n=== 🔄 Pornesc sincronizarea completă ANAF ===")
    start = time.time()

    async with aiohttp.ClientSession() as session:
        judete_data = await fetch_with_retry(session, ANAF_BASE_URL)
        if not judete_data:
            print("❌ Eroare: nu s-au putut descărca județele.")
            return

        print(f"📦 {len(judete_data)} județe descărcate din ANAF.\n")

        for j_idx, judet in enumerate(judete_data, start=1):
            cod_judet = int(judet.get("cod"))
            denumire_judet = judet.get("denumire")

            print(f"\n🏞️ [{j_idx}/{len(judete_data)}] Județ: {denumire_judet} ({cod_judet})")

            judet_obj, _ = await get_or_create(
                db,
                models.Judet,
                cod=cod_judet,
                defaults={"denumire": denumire_judet},
            )
            await db.refresh(judet_obj)

            # Localități
            url_loc = f"{ANAF_BASE_URL}/{cod_judet}"
            localitati_data = await fetch_with_retry(session, url_loc)
            if not localitati_data:
                print(f"⚠️ Nu s-au găsit localități pentru {denumire_judet}")
                continue

            print(f"📍 {len(localitati_data)} localități în județul {denumire_judet}")

            for l_idx, loc in enumerate(localitati_data, start=1):
                cod_loc = int(loc.get("cod"))
                denumire_loc = loc.get("denumire")

                loc_obj, _ = await get_or_create(
                    db,
                    models.Localitate,
                    cod=cod_loc,
                    defaults={"denumire": denumire_loc, "judet_id": judet_obj.id},
                )
                await db.commit()

                # Străzi
                url_strazi = f"{ANAF_BASE_URL}/{cod_judet}/{cod_loc}"
                strazi_data = await fetch_with_retry(session, url_strazi)
                if not strazi_data:
                    continue

                for strada in strazi_data:
                    cod_str = int(strada.get("cod"))
                    denumire_str = strada.get("denumire")

                    await get_or_create(
                        db,
                        models.Strada,
                        cod=cod_str,
                        defaults={"denumire": denumire_str, "localitate_id": loc_obj.id},
                    )
                await db.commit()

    print(f"\n✅ Sincronizare completă terminată în {time.time() - start:.2f} secunde.")


# ============================================================
# 🚀 Runner manual
# ============================================================
async def main():
    async with async_session_maker() as session:
        await sync_all_judete(session)


if __name__ == "__main__":
    asyncio.run(main())
