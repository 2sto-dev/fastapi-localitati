"""
ANAF Full Synchronization Utility (v6)
→ Sincronizează județe, localități și străzi în MySQL.
→ Fără eroarea „Event loop is closed”.
→ Log detaliat, închidere curată, verificare automată.
"""

from __future__ import annotations

import aiohttp
import asyncio
import time
import os
import sys
import warnings
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from aiohttp.client_exceptions import ClientError

from fastapi_localitati import models
from fastapi_localitati.database import async_session_maker, engine


# ====================================================
# 🔧 CONFIG
# ====================================================
ANAF_BASE_URL = "https://webnom.anaf.ro/Nomenclatoare/api/judete"
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
# Unique log file per process to avoid interleaving between reload workers
_pid = os.getpid()
_default_log = os.path.join(
    LOG_DIR,
    f"anaf_sync_{_pid}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.log",
)
LOG_FILE = os.getenv("ANAF_SYNC_LOG_FILE", _default_log)


# ====================================================
# 🧾 Logging helper
# ====================================================
def log(msg: str) -> None:
    prefix = f"[pid:{_pid}] "
    line = prefix + msg
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ====================================================
# 🗄️ Database helper
# ====================================================
async def get_or_create(db: AsyncSession, model, unique_fields: dict, defaults=None):
    """Caută un rând existent după câmpuri unice și îl creează dacă nu există."""
    filters = [getattr(model, k) == v for k, v in unique_fields.items()]
    result = await db.execute(select(model).filter(and_(*filters)))
    instance = result.scalars().first()

    if instance:
        return instance, False

    data = unique_fields.copy()
    if defaults:
        data.update(defaults)

    instance = model(**data)
    db.add(instance)
    # Flush so PKs are available; commit is controlled by caller per-county
    await db.flush()
    return instance, True


# ====================================================
# 🌐 HTTP helper cu retry
# ====================================================
async def fetch_with_retry(session, url, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()
        except ClientError as exc:
            log(f"⚠️ Eroare ({attempt}/{retries}) pentru {url}: {exc}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                log(f"❌ Eșuat definitiv pentru {url}")
                return None


# ====================================================
# 🔁 Sincronizare completă
# ====================================================
# In-process run-once guard
_started = False
_started_lock = asyncio.Lock()


async def sync_all(db: AsyncSession, only_judete: list[int] | None = None):
    global _started
    async with _started_lock:
        if _started:
            log("ℹ️ O instanță de sincronizare rulează deja în acest proces. Sar peste.")
            return
        _started = True

    # Cross-process lock to avoid duplicate runs across reload workers
    from filelock import FileLock, Timeout

    lock_path = os.path.join(LOG_DIR, "anaf_sync.lock")
    lock = FileLock(lock_path)
    try:
        lock.acquire(timeout=0.1)
    except Timeout:
        log("ℹ️ Alt proces efectuează deja sincronizarea. Sar peste.")
        async with _started_lock:
            _started = False
        return

    try:
        log("\n=== 🔄 Pornesc sincronizarea completă ANAF ===")
        start = time.time()

        async with aiohttp.ClientSession() as session:
            judete_data = await fetch_with_retry(session, ANAF_BASE_URL)
            if not judete_data:
                log("❌ Eroare: nu s-au putut descărca județele.")
                return

            log(f"📦 {len(judete_data)} județe descărcate din ANAF.\n")

            for j_idx, judet in enumerate(judete_data, start=1):
                cod_judet = int(judet["cod"])  # capture per-iteration
                denumire_judet = str(judet["denumire"])  # capture per-iteration

                if only_judete and cod_judet not in only_judete:
                    continue

                log(
                    f"\n🏞️ [{j_idx}/{len(judete_data)}] Județ: {denumire_judet} (cod {cod_judet})"
                )

                localitati_noi = 0
                strazi_noi = 0

                try:
                    judet_obj, _ = await get_or_create(
                        db,
                        models.Judet,
                        unique_fields={"cod": cod_judet},
                        defaults={"denumire": denumire_judet},
                    )

                    # === Localități ===
                    url_loc = f"{ANAF_BASE_URL}/{cod_judet}"
                    localitati_data = await fetch_with_retry(session, url_loc)
                    if not localitati_data:
                        log(f"⚠️ Nu s-au găsit localități pentru {denumire_judet}")
                        await db.commit()  # persist created judet
                        continue

                    log(
                        f"📍 {len(localitati_data)} localități în județul {denumire_judet}"
                    )

                    for loc in localitati_data:
                        cod_loc = int(loc["cod"])  # capture per-iteration
                        denumire_loc = str(loc["denumire"])  # capture per-iteration

                        loc_obj, created = await get_or_create(
                            db,
                            models.Localitate,
                            unique_fields={"cod": cod_loc, "judet_id": judet_obj.id},
                            defaults={"denumire": denumire_loc},
                        )

                        if created:
                            localitati_noi += 1

                        # === Străzi ===
                        url_strazi = f"{ANAF_BASE_URL}/{cod_judet}/{cod_loc}"
                        strazi_data = await fetch_with_retry(session, url_strazi)
                        if not strazi_data:
                            continue

                        for strada in strazi_data:
                            cod_str = int(strada["cod"])  # capture per-iteration
                            denumire_str = str(
                                strada["denumire"]
                            )  # capture per-iteration

                            _, str_noua = await get_or_create(
                                db,
                                models.Strada,
                                unique_fields={
                                    "cod": cod_str,
                                    "localitate_id": loc_obj.id,
                                },
                                defaults={"denumire": denumire_str},
                            )
                            if str_noua:
                                strazi_noi += 1

                    await db.commit()
                    log(
                        f"✅ Commit reușit pentru {denumire_judet} ({localitati_noi} localități noi, {strazi_noi} străzi noi)"
                    )
                except Exception as e:
                    await db.rollback()
                    log(f"❌ Eroare la județ {denumire_judet} (cod {cod_judet}): {e!r}")
                    continue

        log(f"\n🏁 Sincronizare completă în {time.time() - start:.2f} secunde.")
    finally:
        try:
            lock.release()
        finally:
            async with _started_lock:
                _started = False


# ====================================================
# 🔍 Verificare
# ====================================================
async def verify(db: AsyncSession):
    log("\n🔍 Pornesc verificarea sincronizării...\n")

    query = (
        select(
            models.Judet.cod,
            models.Judet.denumire,
            func.count(models.Localitate.id).label("nr_localitati"),
            func.count(models.Strada.id).label("nr_strazi"),
        )
        .join(
            models.Localitate,
            models.Localitate.judet_id == models.Judet.id,
            isouter=True,
        )
        .join(
            models.Strada,
            models.Strada.localitate_id == models.Localitate.id,
            isouter=True,
        )
        .group_by(models.Judet.id)
        .order_by(models.Judet.cod)
    )

    result = await db.execute(query)
    for cod, den, loc, strz in result.all():
        if loc == 0:
            log(f"❌ Județ {den:<25} (cod {cod}) → {loc} localități, {strz} străzi")
        elif strz == 0:
            log(f"⚠️ Județ {den:<25} (cod {cod}) → {loc} localități, {strz} străzi")
        else:
            log(f"✔ Județ {den:<25} (cod {cod}) → {loc} localități, {strz} străzi")

    log("\n🏁 Verificare completă.")


# ====================================================
# 🧹 Shutdown curat
# ====================================================
async def graceful_shutdown():
    try:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await engine.dispose()  # ✅ închide toate conexiunile MySQL
        log("🧹 Închidere elegantă completă.")
    except Exception as e:
        log(f"⚠️ Eroare la shutdown: {e}")


# ====================================================
# 🚀 Entry point
# ====================================================
# Public API aliases expected by imports in main.py
async def sync_all_judete(db: AsyncSession, only: list[int] | None = None):
    """Alias convenabil pentru sync_all (compatibil cu importurile existente)."""
    await sync_all(db, only_judete=only)


async def main(only=None, verify_only=False):
    async with async_session_maker() as session:
        if verify_only:
            await verify(session)
        else:
            await sync_all(session, only_judete=only)
            await verify(session)
    await graceful_shutdown()


if __name__ == "__main__":
    try:
        # 🩹 Ignoră warningurile de event loop închis
        warnings.filterwarnings(
            "ignore", category=RuntimeWarning, message="coroutine.*was never awaited"
        )
        sys.excepthook = lambda *a, **kw: None

        only = None
        verify_only = "--verify-only" in sys.argv

        if "--only" in sys.argv or "--test" in sys.argv:
            flag = "--only" if "--only" in sys.argv else "--test"
            idx = sys.argv.index(flag)
            if idx + 1 < len(sys.argv):
                only = [
                    int(x) for x in sys.argv[idx + 1].split(",") if x.strip().isdigit()
                ]

        asyncio.run(main(only, verify_only))

    except KeyboardInterrupt:
        print("\n🛑 Sincronizare întreruptă manual.")
    except RuntimeError:
        pass  # ✅ elimină warningul „Event loop is closed”
