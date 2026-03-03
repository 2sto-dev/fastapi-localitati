from __future__ import annotations

import argparse
from typing import Any, Optional

from client_app.token_manager import TokenManager
from client_app.api import get_judete, get_localitati, get_strazi


def get_field(obj: Any, name: str) -> Any:
    """Return field from dict or object attribute; None if missing."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def preview(items: list[Any], limit: int) -> list[Any]:
    if limit <= 0:
        return items
    return items[:limit]


def main() -> None:
    p = argparse.ArgumentParser(description="Client SDK test for fastapi-localitati")
    p.add_argument(
        "--cod-judet",
        type=int,
        default=None,
        help="Cod judet (ex: 10). If missing, uses first returned.",
    )
    p.add_argument(
        "--cod-localitate",
        type=int,
        default=None,
        help="Cod localitate. If missing, uses first returned.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Preview limit for printed lists (default 5). Use 0 for all.",
    )
    p.add_argument(
        "--no-strazi-in-localitati",
        action="store_true",
        help="Do not print 'strazi' preview from localitati.",
    )
    p.add_argument(
        "--only",
        choices=["judete", "localitati", "strazi"],
        default=None,
        help="Run only one step and exit.",
    )
    args = p.parse_args()

    tm = TokenManager()

    # 1) JUDETE
    judete = get_judete(tm)
    print("Judete:", len(judete))
    if not judete:
        print("Nu exista judete returnate de API.")
        return

    if args.only == "judete":
        print("Preview judete:", preview(judete, args.limit))
        return

    # pick cod_judet
    if args.cod_judet is None:
        first = judete[0]
        cod_judet = get_field(first, "cod")
        print("Primul judet:", first)
        if cod_judet is None:
            raise SystemExit(
                "Eroare: nu am putut extrage campul 'cod' din primul judet."
            )
        cod_judet = int(cod_judet)
    else:
        cod_judet = args.cod_judet

    print("cod_judet ales:", cod_judet)

    # 2) LOCALITATI
    localitati = get_localitati(tm, cod_judet=cod_judet)
    print("Localitati:", len(localitati))
    if not localitati:
        print("Nu exista localitati pentru judetul ales.")
        return

    if args.only == "localitati":
        if args.no_strazi_in_localitati:
            # remove heavy strazi field from preview print
            trimmed = [
                {"cod": get_field(x, "cod"), "denumire": get_field(x, "denumire")}
                for x in preview(localitati, args.limit)
            ]
            print("Preview localitati:", trimmed)
        else:
            print("Preview localitati:", preview(localitati, args.limit))
        return

    # pick cod_localitate
    if args.cod_localitate is None:
        first_loc = localitati[0]
        cod_localitate = get_field(first_loc, "cod")
        print(
            "Prima localitate:",
            (
                first_loc
                if not args.no_strazi_in_localitati
                else {
                    "cod": get_field(first_loc, "cod"),
                    "denumire": get_field(first_loc, "denumire"),
                }
            ),
        )
        if cod_localitate is None:
            raise SystemExit(
                "Eroare: nu am putut extrage campul 'cod' din prima localitate."
            )
        cod_localitate = int(cod_localitate)
    else:
        cod_localitate = args.cod_localitate

    print("cod_localitate ales:", cod_localitate)

    # 3) STRAZI
    strazi = get_strazi(tm, cod_judet=cod_judet, cod_localitate=cod_localitate)
    print("Strazi:", len(strazi))
    print("Preview strazi:", preview(strazi, args.limit))


if __name__ == "__main__":
    main()
