FastAPI Localități API — Securizat și Async (SQLAlchemy)

Descriere
- API de sincronizare și interogare pentru nomenclatoarele ANAF: județe, localități și străzi.
- Implementat cu FastAPI, SQLAlchemy Async, MySQL (aiomysql), JWT (access + refresh, rotație la refresh).
- Endpointuri protejate cu Bearer JWT, CORS configurabil, headere de securitate, limitare simplă de rată.
- Include scripturi pentru popularea datelor din ANAF și pentru administrare utilizatori.

Caracteristici
- JWT Access/Refresh cu tip explicit de token ("access"/"refresh"), rotație la refresh.
- Flow OAuth2 Password pentru /docs (Swagger „Authorize”).
- Endpoint ierarhic nou: /api/tree (județ → localități → străzi într-un singur răspuns JSON).
- Async SQLAlchemy cu selectinload pentru evitarea N+1.
- Configurare prin .env (inclusiv credențiale MySQL). Fără credențiale hardcodate în cod.

Cerințe
- Python 3.11+ (recomandat 3.12)
- MySQL/MariaDB funcțional
- Windows, Linux sau macOS

Instalare (Windows PowerShell)
1) Creează și activează un mediu virtual
- python -m venv venv
- venv\Scripts\Activate.ps1

2) Instalează dependențele
- pip install -r fastapi_localitati/requirements.txt

3) Configurează .env (în rădăcina proiectului)
- Creează un fișier .env și adaugă variabilele (exemplu minim fără DATABASE_URL):

  ENV=dev
  SECRET_KEY=dev-insecure-secret-change-me

  DB_DRIVER=mysql+aiomysql
  DB_USER=root
  DB_PASSWORD=parola_ta
  DB_HOST=127.0.0.1
  DB_PORT=3306
  DB_NAME=localitati_db

  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=Str0ngP@ss!
  SEED_ADMIN_ON_STARTUP=true

  ACCESS_TOKEN_EXPIRE_MINUTES=30
  REFRESH_TOKEN_EXPIRE_DAYS=7
  LOG_LEVEL=INFO

- Alternativ, poți seta direct DATABASE_URL (înlocuiește variabilele DB_*):
  DATABASE_URL=mysql+aiomysql://user:parola@127.0.0.1:3306/localitati_db?charset=utf8mb4

4) Pornește serverul
- uvicorn fastapi_localitati.main:app --reload --host 127.0.0.1 --port 8080

5) Autentificare și documentație
- Deschide http://127.0.0.1:8080/docs
- Apasă „Authorize” și folosește OAuth2 Password Flow (cu userul tău)
- /token întoarce access_token + refresh_token

Instalare (Linux/macOS — Bash)
- python3 -m venv venv
- source venv/bin/activate
- pip install -r fastapi_localitati/requirements.txt
- editează .env ca mai sus
- uvicorn fastapi_localitati.main:app --reload --host 127.0.0.1 --port 8080

Variabile de mediu (.env)
- ENV=dev|prod
- SECRET_KEY=cheie-aleatoare-puternică (obligatoriu în prod)
- DATABASE_URL=DSN complet (opțional dacă folosești DB_*)
- DB_DRIVER, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME (alternative la DATABASE_URL)
- ADMIN_USERNAME, ADMIN_PASSWORD, SEED_ADMIN_ON_STARTUP (seed utilizator admin în dev)
- ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
- LOG_LEVEL (INFO/DEBUG etc.)
- CORS_ORIGINS (opțional; listă JSON sau CSV)

Generare SECRET_KEY puternic
- python -c "import secrets; print(secrets.token_urlsafe(64))"

Endpointuri principale (securizate cu JWT)
- POST /token — OAuth2 Password (returnează access + refresh)
- POST /token/refresh — primește refresh_token și întoarce tokenuri noi (rotație)
- GET  /api/judete — listă județe (fără încărcare profundă)
- GET  /api/judete/{cod} — un județ + localități + străzi
- GET  /api/localitati/{cod_judet}
- GET  /api/strazi/{cod_judet}/{cod_localitate}
- GET  /api/tree?cod_judet=..[&cod_localitate=..] — ierarhie într-un singur JSON

Exemple de folosire (PowerShell)
- Obține token (din /docs sau cu username/parolă prin POST /token). Apoi:
  $token = "<ACCESS_TOKEN>"
  # Ierarhie completă pentru județul 12
  iwr -UseBasicParsing -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:8080/api/tree?cod_judet=12"
  # Doar o localitate din județul 12
  iwr -UseBasicParsing -Headers @{Authorization="Bearer $token"} "http://127.0.0.1:8080/api/tree?cod_judet=12&cod_localitate=1234"

Administrare utilizatori (dev-only)
- Creează utilizator:
  python -m scripts.create_user --username admin --password "Str0ngP@ss!"

Client fără user/parolă (doar refresh token)
- Vezi secțiunea „Localități SDK (localitati_sdk)” pentru o prezentare profesională a SDK-ului client inclus în acest repo (folderul localitati_sdk/).
- Pe scurt, SDK-ul oferă:
  - TokenManager (fără .env dependențe): primește base_url + refresh_token, gestionează access_token și rotația refresh_token (prin callback opțional).
  - API helpers: get_judete(), get_localitati(), get_strazi().
  - CLI de test: python -m localitati_sdk.client

Pași client (PowerShell)
1) Bootstrap (o singură dată)
- $env:API_BASE_URL="http://127.0.0.1:8080"; python -m client_app.bootstrap_refresh_token --username admin --password "Str0ngP@ss!"
- setează CLIENT_REFRESH_TOKEN în client_app/.env
2) Apelează API doar cu refresh (TokenManager gestionează accesul)
- python -c "from client_app.token_manager import TokenManager; from client_app.api import get_judete; tm=TokenManager(); print(len(get_judete(tm)))"

Localități SDK (localitati_sdk)
Ce este
- localitati_sdk este un SDK Python simplu și robust pentru integrarea cu acest API, fără a stoca username/parolă în client. Utilizează exclusiv refresh_token, gestionează ciclul de viață al tokenurilor (obține access_token, reîmprospătează automat la expirare sau 401) și oferă funcții convenabile pentru endpointurile cheie.

Structură (localitati_sdk/)
- __init__.py — exporturi publice (TokenManager, get_judete, get_localitati, get_strazi, erori)
- token_manager.py — TokenManager (nu citește/scrie .env; primește base_url + refresh_token și expune on_refresh_token_rotated pentru persistență sigură)
- api.py — helperi HTTP: get_judete(), get_localitati(cod_judet), get_strazi(cod_judet, cod_localitate)
- errors.py — ierarhia de erori: LocalitatiSDKError, AuthError, APIError
- bootstrap_refresh_token.py — script one-time pentru obținerea refresh_token (folosește user/parolă)
- client.py — CLI de test pentru SDK (fără .env), util pentru validare rapidă

Pentru cine este util
- Microservicii/servicii interne care consumă nomenclatoarele ANAF (citire) fără a gestiona credențiale de utilizator.
- ETL/automatizări/headless jobs unde token-only (refresh) este preferat.
- CLI-uri sau aplicații care doresc rotație automată a tokenurilor și un strat minim peste requests.

Caracteristici
- TokenManager:
  - Acceptă base_url și refresh_token (nu depinde de .env).
  - Obține access_token prin POST /token/refresh.
  - Cachează access_token + exp și reîmprospătează proactiv (implicit cu 30s înainte de expirare) sau la 401/403.
  - Rotează refresh_token; oferă callback on_refresh_token_rotated(refresh) pentru a salva noul token într-un secret store.
- API helpers:
  - get_judete(tm) → List[dict]
  - get_localitati(tm, cod_judet: int) → List[dict]
  - get_strazi(tm, cod_judet: int, cod_localitate: int) → List[dict]
  - Pentru ierarhie completă: tm.request("GET", "/api/tree", params={...})

Instalare / utilizare
- Dependințe: Python 3.11+, requests.
- În acest repo, SDK-ul este local (localitati_sdk/). Îl poți folosi direct:

  Programatic (exemplu scurt):
  python - <<PY
  from localitati_sdk.token_manager import TokenManager
  from localitati_sdk.api import get_judete, get_localitati, get_strazi
  tm = TokenManager(base_url="http://127.0.0.1:8080", refresh_token="<REFRESH_TOKEN>")
  judete = get_judete(tm)
  cod = judete[0]["cod"]
  print("judete:", len(judete))
  print("localitati in primul judet:", len(get_localitati(tm, cod)))
  PY

  CLI de test (fără .env):
  python -m localitati_sdk.client --base-url http://127.0.0.1:8080 --refresh-token <REFRESH_TOKEN> --cod-judet 12 --limit 3

Bootstrap refresh_token (one-time)
- Obține refresh_token folosind user/parolă, apoi stochează-l în secret store/config la alegere:
  python -m localitati_sdk.bootstrap_refresh_token --username admin --password "Str0ngP@ss!" --base http://127.0.0.1:8080
  # Doar token-ul (pentru scripting):
  python -m localitati_sdk.bootstrap_refresh_token --username admin --password "Str0ngP@ss!" --only-refresh

Integrare sigură (producție)
- Nu păstra refresh_token în fișiere locale; folosește un secret store (Vault, AWS Secrets Manager, Azure Key Vault etc.).
- Utilizează on_refresh_token_rotated în TokenManager pentru a salva refresh_token-ul nou după fiecare rotație.
- Limitează permisiunile contului care emite refresh_token (doar citire pentru nomenclatoare).

Depanare SDK
- AuthError: eșec la /token/refresh — verifică refresh_token-ul și drepturile.
- APIError: coduri HTTP >= 400 — vezi status_code și body pentru detalii.
- 422 la /api/localitati/None: asigură-te că treci un cod_judet valid (preia-l din /api/judete care întoarce cod, denumire).
- 401/403 persistente: regenerează refresh_token sau verifică că bearer tokenul este trimis (TokenManager face asta automat).

Securitate
- Tokenurile includ iat/nbf/exp și tip explicit; refresh are rotație la /token/refresh.
- Headere de securitate adăugate (X-Content-Type-Options, X-Frame-Options, CSP minimală pentru Swagger).
- CORS restrâns implicit la localhost; configurează CORS_ORIGINS în .env pentru front-end-ul tău.
- Limitare rată in-memory (per-proces) inclusă; pentru producție recomandăm limiter distribuit (Redis/gateway/WAF).

Depanare
- Eroare „DATABASE_URL ... trebuie setate în .env”: asigură-te că .env are fie DATABASE_URL, fie toate DB_DRIVER/DB_HOST/DB_PORT/DB_NAME și (opțional) DB_USER/DB_PASSWORD; repornește serverul după modificări.
- ModuleNotFoundError pydantic-settings: instalează dependențele cu pip install -r fastapi_localitati/requirements.txt.
- 401/403: folosește Authorize în /docs sau trimite headerul Authorization: Bearer <access_token>.

Cheat-sheet comenzi (PowerShell)
- Activare venv:
  venv\Scripts\Activate.ps1
- Instalare dependențe:
  pip install -r fastapi_localitati/requirements.txt
- Pornire server:
  uvicorn fastapi_localitati.main:app --reload --host 127.0.0.1 --port 8080
- Creare user dev:
  python -m scripts.create_user --username admin --password "Str0ngP@ss!"
- Smoke test login + refresh:
  python -m scripts.smoke_test --base http://127.0.0.1:8080 --username admin --password "Str0ngP@ss!"
