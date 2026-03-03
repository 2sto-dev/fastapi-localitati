import os, sys
from fastapi.routing import APIRoute

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from fastapi_localitati.main import app
except Exception as e:
    print(f"Error importing app: {e}")
    raise

for route in app.router.routes:
    if isinstance(route, APIRoute):
        methods = ",".join(sorted(m for m in route.methods if m not in {"HEAD","OPTIONS"}))
        print(f"{methods:10} {route.path} -> {route.name}")
