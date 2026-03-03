from __future__ import annotations

import argparse
from typing import Any

from .token_manager import TokenManager
from .api import get_judete, get_localitati, get_strazi


def preview(items: list[Any], limit: int) -> list[Any]:
    return items if limit <= 0 else items[:limit]


def main() -> None:
    p = argparse.ArgumentParser(description="localitati-sdk CLI test (no .env)")
    p.add_argument(
        "--base-url", required=True, help="API base URL, ex: http://127.0.0.1:8080"
    )
    p.add_argument("--refresh-token", required=True, help="Refresh token (JWT)")
    p.add_argument(
        "--cod-judet", type=int, default=10, help="Cod judet (default 10=Buzau)"
    )
    p.add_argument(
        "--cod-localitate",
        type=int,
        default=None,
        help="Cod localitate (default: first from list)",
    )
    p.add_argument("--limit", type=int, default=5, help="Preview limit (0 = all)")
    args = p.parse_args()

    tm = TokenManager(base_url=args.base_url, refresh_token=args.refresh_token)

    judete = get_judete(tm)
    print("Judete:", len(judete))
    print("Preview judete:", preview(judete, args.limit))

    localitati = get_localitati(tm, cod_judet=args.cod_judet)
    print(f"Localitati in judet {args.cod_judet}:", len(localitati))

    if not localitati:
        return

    cod_loc = args.cod_localitate or localitati[0]["cod"]
    strazi = get_strazi(tm, cod_judet=args.cod_judet, cod_localitate=cod_loc)
    print(f"Strazi in localitate {cod_loc}:", len(strazi))
    print("Preview strazi:", preview(strazi, args.limit))


if __name__ == "__main__":
    main()
