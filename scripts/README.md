# 🗺️ ANAF Localități – Sincronizare completă

> Script asincron pentru descărcarea și sincronizarea județelor, localităților și străzilor din API-ul public ANAF în baza de date MySQL.

---

## 🚀 Descriere

`sync_anaf.py` este un utilitar Python care:
- preia ierarhia administrativă din **API-ul ANAF**,
- salvează datele în tabelele `judete`, `localitati`, `strazi`,
- evită duplicatele și erorile de integritate,
- verifică consistența datelor,
- generează loguri detaliate pentru fiecare rulare.

Este parte a proiectului **FastAPI Localități**, dar poate fi folosit independent ca script standalone.

---

## ⚙️ Cerințe

| Componentă | Versiune minimă |
|-------------|-----------------|
| Python | 3.10+ |
| MySQL | 8.0+ |
| SQLAlchemy | 2.x (async) |
| aiomysql | 0.2.0+ |
| aiohttp | 3.9+ |

---

## 🧩 Structura tabelelor

### `judete`
| Câmp | Tip | Descriere |
|------|-----|-----------|
| id | INT, PK | ID automat |
| cod | INT, UNIQUE | Codul județului |
| denumire | VARCHAR(100) | Numele complet |

### `localitati`
| Câmp | Tip | Descriere |
|------|-----|-----------|
| id | INT, PK | ID automat |
| cod | INT | Cod localitate |
| denumire | VARCHAR(150) | Denumirea localității |
| judet_id | INT, FK | Legătura cu `judete.id` |
| 🔑 **UNIQUE** | (cod, judet_id) | Evită duplicatele între județe |

### `strazi`
| Câmp | Tip | Descriere |
|------|-----|-----------|
| id | INT, PK | ID automat |
| cod | INT | Codul străzii |
| denumire | VARCHAR(200) | Numele străzii |
| localitate_id | INT, FK | Legătura cu `localitati.id` |
| 🔑 **UNIQUE** | (cod, localitate_id) | Evită duplicate în aceeași localitate |

---

## 🧮 Funcționalitate

### 🔹 1. Sincronizare completă
Descărcă toate județele, localitățile și străzile din API-ul ANAF:
```bash
python -m fastapi_localitati.scripts.sync_anaf
```

### 🔹 2. Sincronizare parțială (doar un județ)
Exemplu: Mehedinți (`cod 25`)
```bash
python -m fastapi_localitati.scripts.sync_anaf --only 25
```

Poți specifica mai multe:
```bash
python -m fastapi_localitati.scripts.sync_anaf --only 25,10,16
```

### 🔹 3. Doar verificare
Verifică baza de date fără a face sincronizare:
```bash
python -m fastapi_localitati.scripts.sync_anaf --verify-only
```

---

## 📦 Structura proiectului

```text
fastapi_localitati/
 ├── database.py
 ├── models.py
 └── scripts/
      └── sync_anaf.py
logs/
 ├── anaf_sync_20251020_223000.log
 └── anaf_sync_20251021_094500.log
```

---

## 🧾 Loguri

Fiecare rulare generează un log dedicat:
```
=== 🔄 Pornesc sincronizarea completă ANAF ===
📦 42 județe descărcate din ANAF.

🏞️ [27/42] Județ: MEHEDINȚI (cod 25)
📍 358 localități în județul MEHEDINȚI
✅ Commit reușit pentru județul MEHEDINȚI (358 localități noi, 0 străzi noi)

🏁 Sincronizare completă în 14.77 secunde.
🧹 Închidere elegantă completă.
✅ Program terminat fără erori.
```

---

## ⚠️ Tratarea erorilor

Scriptul gestionează automat:
- reconectări HTTP (`fetch_with_retry`),
- duplicate SQL (`get_or_create`),
- erori de rețea sau timeout (`aiohttp.ClientError`),
- erori la închiderea event loop-ului (`RuntimeError: Event loop is closed`).

Toate erorile sunt logate și afișate fără întreruperea sincronizării globale.

---

## 🔧 Opțiuni CLI

| Flag | Descriere |
|------|------------|
| `--only [coduri]` | Sincronizează doar județele specificate |
| `--test [coduri]` | Echivalent cu `--only` (pentru test) |
| `--verify-only` | Doar verifică datele existente |
| `Ctrl + C` | Întrerupe manual sincronizarea |

---

## 🧹 Închidere curată

Scriptul închide automat toate conexiunile și taskurile asincrone:
```text
🧹 Închidere elegantă completă.
✅ Program terminat fără erori.
```

Fără erori `RuntimeError: Event loop is closed`.

---

## 🧠 Dezvoltatori

Autor: **SoftPower Dev**  
Proiect: **FastAPI Localități**  
Licență: MIT

---

## 💡 Sugestii extindere

- Adăugare opțiune `--reset-db` pentru golirea completă a bazei de date.
- Cache local pentru reducerea timpilor de sincronizare.
- Dashboard web pentru monitorizare sincronizări.

---

> 📘 Ultima actualizare: 20 octombrie 2025  
> Versiune script: **v6**
