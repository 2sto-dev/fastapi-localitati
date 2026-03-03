#!/usr/bin/env python3
"""
MySQL UTF-8 (utf8mb4) audit and fixer for Romanian diacritics issues.

Features:
- Audits server/database/table/column character set & collation
- Generates ALTER statements to migrate to utf8mb4 + chosen collation (default: utf8mb4_romanian_ci)
- Optionally applies the changes
- Optional "mojibake" repair for text columns where data was stored with a wrong encoding (latin1→utf8mb4)

Usage (PowerShell on Windows):
  .\venv\Scripts\Activate.ps1
  python scripts\mysql_charset_audit.py --host localhost --port 3306 \
    --user root --password "PAROLA" --db localitati_db --report

Apply safe fixes (DB + tables + columns):
  python scripts\mysql_charset_audit.py --host localhost --port 3306 \
    --user root --password "PAROLA" --db localitati_db \
    --apply-db --apply-tables --apply-columns --dry-run
  # remove --dry-run to actually execute

Attempt mojibake repair (use with caution; test first):
  python scripts\mysql_charset_audit.py --host localhost --port 3306 \
    --user root --password "PAROLA" --db localitati_db --repair-mojibake --dry-run

Dependencies:
- PyMySQL (pure-Python; no MySQL client needed): pip install PyMySQL
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Tuple

try:
    import pymysql
except ImportError:
    print("ERROR: PyMySQL is not installed. Install with: pip install PyMySQL")
    sys.exit(1)

TEXT_TYPES = {
    "char",
    "varchar",
    "tinytext",
    "text",
    "mediumtext",
    "longtext",
    "enum",
    "set",
}


def connect_mysql(host: str, port: int, user: str, password: str, db: str):
    # Ensure utf8mb4 connection charset
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.Cursor,
    )


def fetch_server_charsets(conn) -> Dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SHOW VARIABLES LIKE 'character_set_server'")
        cs_server = cur.fetchone()
        cur.execute("SHOW VARIABLES LIKE 'collation_server'")
        collation_server = cur.fetchone()
    return {
        "character_set_server": cs_server[1] if cs_server else None,
        "collation_server": collation_server[1] if collation_server else None,
    }


def fetch_db_collation(conn, db: str) -> Tuple[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME=%s
            """,
            (db,),
        )
        row = cur.fetchone()
    return (row[0], row[1]) if row else (None, None)


def fetch_tables(conn, db: str) -> List[Tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT TABLE_NAME, TABLE_COLLATION
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA=%s
            ORDER BY TABLE_NAME
            """,
            (db,),
        )
        rows = cur.fetchall()
    return [(r[0], r[1]) for r in rows]


def fetch_text_columns(conn, db: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_SET_NAME, COLLATION_NAME, COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s
              AND DATA_TYPE IN ('char','varchar','tinytext','text','mediumtext','longtext','enum','set')
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (db,),
        )
        cols = cur.fetchall()
    result = []
    for r in cols:
        result.append(
            {
                "table": r[0],
                "column": r[1],
                "data_type": r[2],
                "char_set": r[3],
                "collation": r[4],
                "column_type": r[5],
            }
        )
    return result


def generate_alter_db(db: str, target_collation: str) -> str:
    return f"ALTER DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE {target_collation};"


def generate_alter_table(table: str, target_collation: str) -> str:
    return f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE {target_collation};"


def generate_alter_column(table: str, column: str, column_type: str, target_collation: str) -> str:
    return (
        f"ALTER TABLE `{table}` MODIFY `{column}` {column_type} "
        f"CHARACTER SET utf8mb4 COLLATE {target_collation};"
    )


def generate_repair_update(table: str, column: str) -> str:
    # latin1 bytes -> utf8mb4 text
    return (
        f"UPDATE `{table}` SET `{column}` = "
        f"CONVERT(CAST(CONVERT(`{column}` USING latin1) AS BINARY) USING utf8mb4) "
        f"WHERE `{column}` IS NOT NULL;"
    )


def main():
    p = argparse.ArgumentParser(description="Audit and fix MySQL UTF-8 (utf8mb4) charsets/collations.")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--db", required=True, help="Database name to audit")
    p.add_argument("--target-collation", default="utf8mb4_romanian_ci",
                   help="Target collation (default: utf8mb4_romanian_ci)")
    p.add_argument("--report", action="store_true", help="Only print report and suggested SQL")
    p.add_argument("--apply-db", action="store_true", help="Apply ALTER DATABASE to utf8mb4")
    p.add_argument("--apply-tables", action="store_true", help="Apply ALTER TABLE CONVERT TO utf8mb4")
    p.add_argument("--apply-columns", action="store_true", help="Apply ALTER COLUMN for non-utf8mb4 columns")
    p.add_argument("--repair-mojibake", action="store_true", help="Attempt mojibake repair (latin1 -> utf8mb4)")
    p.add_argument("--dry-run", action="store_true", default=False, help="Do not execute SQL; just print")

    args = p.parse_args()

    conn = connect_mysql(args.host, args.port, args.user, args.password, args.db)

    try:
        print("== Server charset/collation ==")
        srv = fetch_server_charsets(conn)
        print(srv)

        print("\n== Database charset/collation ==")
        db_cs, db_coll = fetch_db_collation(conn, args.db)
        print({"database": args.db, "charset": db_cs, "collation": db_coll})

        print("\n== Tables (non-utf8mb4 collation) ==")
        tables = fetch_tables(conn, args.db)
        non_utf8mb4_tables = [(t, c) for t, c in tables if not (c and c.lower().startswith("utf8mb4"))]
        for t, c in non_utf8mb4_tables:
            print(f"- {t}: {c}")
        if not non_utf8mb4_tables:
            print("(all tables use utf8mb4 collation)")

        print("\n== Text columns (non-utf8mb4) ==")
        columns = fetch_text_columns(conn, args.db)
        non_utf8mb4_columns = [col for col in columns if (col["char_set"] and col["char_set"].lower() != "utf8mb4")]
        for col in non_utf8mb4_columns:
            print(
                f"- {col['table']}.{col['column']}: {col['data_type']} ({col['column_type']}), "
                f"{col['char_set']}/{col['collation']}"
            )
        if not non_utf8mb4_columns:
            print("(all text columns use utf8mb4)")

        # Suggested SQL
        alter_db_sql = generate_alter_db(args.db, args.target_collation)
        alter_table_sqls = [generate_alter_table(t, args.target_collation) for t, _ in non_utf8mb4_tables]
        alter_column_sqls = [
            generate_alter_column(col["table"], col["column"], col["column_type"], args.target_collation)
            for col in non_utf8mb4_columns
        ]

        print("\n== Suggested SQL ==")
        if db_cs and db_cs.lower() != "utf8mb4":
            print(alter_db_sql)
        for s in alter_table_sqls:
            print(s)
        for s in alter_column_sqls:
            print(s)
        if not (alter_db_sql or alter_table_sqls or alter_column_sqls):
            print("(no changes suggested)")

        # Apply changes
        if args.apply_db or args.apply_tables or args.apply_columns or args.repair_mojibake:
            executed = False
            with conn.cursor() as cur:
                try:
                    if args.apply_db and (db_cs and db_cs.lower() != "utf8mb4"):
                        print(f"\nApplying: {alter_db_sql}")
                        if args.dry_run:
                            print("(dry-run) not executed")
                        else:
                            cur.execute(alter_db_sql)
                            executed = True

                    if args.apply_tables and alter_table_sqls:
                        print("\nApplying ALTER TABLE for non-utf8mb4 tables...")
                        for sql in alter_table_sqls:
                            print(sql)
                            if not args.dry_run:
                                cur.execute(sql)
                                executed = True

                    if args.apply_columns and alter_column_sqls:
                        print("\nApplying ALTER COLUMN for non-utf8mb4 columns...")
                        for sql in alter_column_sqls:
                            print(sql)
                            if not args.dry_run:
                                cur.execute(sql)
                                executed = True

                    if args.repair_mojibake:
                        print("\nMojibake repair (latin1 -> utf8mb4) for text columns")
                        for col in columns:
                            if col["data_type"] in TEXT_TYPES:
                                sql = generate_repair_update(col["table"], col["column"])
                                print(sql)
                                if not args.dry_run:
                                    cur.execute(sql)
                                    executed = True

                    if executed and not args.dry_run:
                        conn.commit()
                        print("\nCommitted changes.")
                    else:
                        print("\nNo changes executed.")
                except Exception as e:
                    conn.rollback()
                    print(f"\nERROR: {e}. Rolled back.")
        else:
            print("\n(No --apply* flags provided; nothing executed.)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
