"""
Improved ANAF synchronization utility with robust error handling and retry logic.
Synchronizes counties, localities, and streets from the ANAF public API into MySQL.
"""

import aiohttp
import asyncio
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiohttp.client_exceptions import ClientResponseError, ClientConnectorError, ServerTimeoutError

from . import models

# 🔗 Baza pentru endpointurile ANAF
ANAF_BASE_URL = "https://webnom.anaf.ro/Nomenclatoare/api/judete"

# ============================================================
# 🧱 Funcție utilitară get_or_create (async)
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
# 🔁 Funcție helper pentru cereri HTTP cu retry
# ============================================================
async def fetch_with_retry(session, url, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 404:
                    print(f"⚠️ 404 - Resursa lipsă: {url}")
                    return None
                resp.raise_for_status()
                return await resp.json()
        except (ClientResponseError, ClientConnectorError, ServerTimeoutError, aiohttp.ClientError) as exc:
            print(f"⚠️ Eroare la cererea către {url} (încercarea {attempt}/{retries}): {exc}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                print(f"❌ Eșuat definitiv după {retries} încercări pentru {url}")
                return None


# ============================================================
# 🔄 Sincronizare completă pentru un singur județ
# ============================================================
async def sync_judet_from_anaf(db: AsyncSession, cod_judet: int):
    print(f"\n=== 🔄 Încep sincronizarea pentru județul cu cod {cod_judet} ===")
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # 1️⃣ Descărcăm localitățile
        url_localitati = f"{ANAF_BASE_URL}/{cod_judet}"
        localitati_data = await fetch_with_retry(session, url_localitati)
        if not localitati_data:
            print(f"⚠️ Nu există localități pentru județul {cod_judet}.")
            return

        print(f"📍 {len(localitati_data)} localități descărcate pentru județul {cod_judet}")

        # Creăm sau actualizăm județul
        judet_obj, _ = await get_or_create(
            db,
            models.Judet,
            cod=cod_judet,
            defaults={"denumire": f"Județ {cod_judet}"}
        )

        # 2️⃣ Iterăm prin localități
        for idx, loc in enumerate(localitati_data, start=1):
            cod_loc = int(loc.get("cod"))
            denumire_loc = loc.get("denumire")

            print(f"\n🏙️ [{idx}/{len(localitati_data)}] Localitate: {denumire_loc} ({cod_loc})")

            loc_obj, created_loc = await get_or_create(
                db,
                models.Localitate,
                cod=cod_loc,
                defaults={"denumire": denumire_loc, "judet_id": judet_obj.id},
            )
            if created_loc:
                print(f"  ➕ Localitate nouă adăugată: {denumire_loc}")
            elif loc_obj.denumire != denumire_loc:
                print(f"  ✏️ Actualizat nume localitate: {loc_obj.denumire} → {denumire_loc}")
                loc_obj.denumire = denumire_loc
                await db.commit()

            # 3️⃣ Descărcăm străzile localității
            url_strazi = f"{ANAF_BASE_URL}/{cod_judet}/{cod_loc}"
            strazi_data = await fetch_with_retry(session, url_strazi)

            if not strazi_data:
                print(f"  ⚠️ Nicio stradă disponibilă pentru {denumire_loc}.")
                continue

            print(f"  🏠 {len(strazi_data)} străzi descărcate pentru {denumire_loc}")

            # 4️⃣ Salvăm străzile
            for strada in strazi_data:
                cod_str = int(strada.get("cod"))
                denumire_str = strada.get("denumire")

                strada_obj, created_str = await get_or_create(
                    db,
                    models.Strada,
                    cod=cod_str,
                    defaults={"denumire": denumire_str, "localitate_id": loc_obj.id},
                )

                if created_str:
                    print(f"    ➕ Stradă nouă: {denumire_str}")
                elif strada_obj.denumire != denumire_str:
                    print(f"    ✏️ Actualizat stradă: {strada_obj.denumire} → {denumire_str}")
                    strada_obj.denumire = denumire_str
                    await db.commit()

    print(f"\n✅ Sincronizare completă pentru județul {cod_judet} în {time.time() - start_time:.2f} secunde.")


# ============================================================
# 🚀 Wrapper: poți apela direct un cod de județ specific
# ============================================================
async def main():
    from .database import async_session_maker  # ajustează în funcție de proiectul tău
    async with async_session_maker() as session:
        await sync_judet_from_anaf(session, cod_judet=25)  # 25 = Mehedinți


if __name__ == "__main__":
    asyncio.run(main())
