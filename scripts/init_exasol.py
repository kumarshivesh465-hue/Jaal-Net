#!/usr/bin/env python
"""Create and seed the Exasol schema from schema.sql.

    python scripts/init_exasol.py

* Loads .env (EXASOL_DSN / USER / PASSWORD / SCHEMA) without extra deps.
* Creates the schema when absent.
* Executes every statement in schema.sql in order: the tables are
  `CREATE OR REPLACE`, so re-running is safe; seed INSERTs that collide with
  an existing primary key are reported and skipped.
* Prints "created N tables, seeded M rows".

Statement splitting is a simple `;` split with `--` comments removed. That is
safe for schema.sql today (no stored procedures, no `--` inside string
literals); if either changes, switch to a real SQL parser.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_SQL = os.path.join(ROOT, "schema.sql")


def load_env(path: str) -> None:
    """Populate os.environ from a KEY=VALUE file without overriding the
    process environment (python-dotenv semantics, zero dependency)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def split_statements(text: str) -> list[str]:
    """Split a SQL script into executable statements."""
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "--" in line:
            line = line.split("--", 1)[0]
        kept.append(line)
    return [chunk.strip() for chunk in "\n".join(kept).split(";") if chunk.strip()]


def rowcount(statement: object) -> int:
    getter = getattr(statement, "rowcount", None)
    if callable(getter):
        try:
            return int(getter())
        except Exception:  # some statements report nothing
            return 0
    return 0


def main() -> int:
    load_env(os.path.join(ROOT, ".env"))

    password = os.environ.get("EXASOL_PASSWORD", "")
    dsn = os.environ.get("EXASOL_DSN", "localhost:8563")
    user = os.environ.get("EXASOL_USER", "sys")
    schema = os.environ.get("EXASOL_SCHEMA", "FRAUD")

    if not password:
        print("EXASOL_PASSWORD is not set (checked .env and the environment).",
              file=sys.stderr)
        return 1

    try:
        import pyexasol
    except ImportError:
        print("pyexasol is not installed (it is in requirements.lock).",
              file=sys.stderr)
        return 1

    print(f"connecting to {dsn} as {user} ...")
    conn = pyexasol.connect(dsn=dsn, user=user, password=password,
                            # lower_ident would fold the upper-case system-view
                            # column names used below and they would not resolve.
                            compression=True, fetch_dict=True, lower_ident=False,
                            # Disable strict cert validation for Personal edition
                            websocket_sslopt={"cert_reqs": __import__("ssl").CERT_NONE})
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    conn.execute(f'OPEN SCHEMA "{schema}"')

    with open(SCHEMA_SQL, encoding="utf-8") as fh:
        statements = split_statements(fh.read())
    print(f"schema.sql: {len(statements)} statement(s)")

    # CREATE OR REPLACE cannot be used on a table that other tables reference
    # by foreign key (Exasol: "constraint violation - table is referenced by
    # foreign keys"), so an existing table is left untouched instead: init is
    # additive and never destroys loaded data.
    # EXA_ALL_TABLES (not EXA_USER_TABLES, which this build does not expose)
    # is case-sensitive and upper case; lower_ident would fold the names.
    existing = {
        str(next(iter(row.values()))).upper()
        for row in conn.execute(
            "SELECT TABLE_NAME FROM EXA_ALL_TABLES "
            f"WHERE TABLE_SCHEMA = '{schema.upper()}'"
        ).fetchall()
    }

    seeded = 0
    skipped = 0
    created = 0
    for stmt in statements:
        head = " ".join(stmt.lstrip().split()[:3]).upper()
        if head.startswith("CREATE"):
            parts = stmt.lstrip().split()
            name = parts[parts.index("TABLE") + 1].strip('"').upper()
            if name in existing:
                skipped += 1
                print(f"  skip (table exists): {name.lower()}")
                continue
            existing.add(name)
        try:
            result = conn.execute(stmt)
        except Exception as exc:
            # Only the server's `message =>` line may be inspected: str(exc)
            # echoes the whole failing statement, and a DDL statement contains
            # "PRIMARY KEY", which used to make every CREATE look like a
            # duplicate and get silently skipped.
            message = str(exc)
            if "message" in message:
                message = message.split("message", 1)[1].split("dsn", 1)[0]
            message = message.lower()
            duplicate = ("unique constraint" in message
                         or "already exists" in message
                         or "duplicate" in message
                         # Exasol seed INSERT onto an existing key:
                         # "constraint violation - primary key (PK_... on table ...)"
                         or "constraint violation - primary key" in message)
            if duplicate:
                skipped += 1
                print(f"  skip (already present): {head}")
                continue
            print(f"FAILED on: {head}\n  {exc}", file=sys.stderr)
            conn.close()
            return 1

        if head.startswith("CREATE"):
            created += 1
        elif head.startswith("INSERT"):
            seeded += rowcount(result)

    # Report the real table count rather than counting CREATE statements.
    # pyexasol forwards `:name` placeholders as host parameters, which this
    # Exasol edition rejects, so the schema name is inlined in its upper-case
    # system-table form.
    tables = conn.execute(
        "SELECT COUNT(*) AS n FROM EXA_ALL_TABLES "
        f"WHERE TABLE_SCHEMA = '{schema.upper()}'"
    ).fetchone()
    n_tables = int(next(iter(tables.values()))) if tables else created

    print(f"created {created} tables, seeded {seeded} rows; "
          f"schema {schema.upper()} now holds {n_tables} tables"
          + (f" ({skipped} table(s) already present)" if skipped else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
