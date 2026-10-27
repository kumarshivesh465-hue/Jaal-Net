#!/usr/bin/env python
"""Exit 0 as soon as the local Exasol instance accepts a login.

    python scripts/probe_exasol.py

Used by the wait loop in docs/hardening_progress.md: Exasol Personal needs
several minutes of first-boot initialisation before port 8563 answers.
"""

from __future__ import annotations

import os
import socket
import ssl
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env(os.path.join(ROOT, ".env"))
    dsn = os.environ.get("EXASOL_DSN", "localhost:8563")
    user = os.environ.get("EXASOL_USER", "sys")
    password = os.environ.get("EXASOL_PASSWORD", "")

    host, _, port = dsn.partition(":")
    try:
        with socket.create_connection((host or "localhost", int(port or 8563)),
                                      timeout=5):
            pass
    except OSError as exc:
        print(f"port closed: {exc}")
        return 1

    try:
        import pyexasol

        # Exasol Personal ships a self-signed certificate; every other script
        # in this repo connects with validation disabled, so the probe must
        # match or it reports a false failure and the wait loop never ends.
        conn = pyexasol.connect(
            dsn=dsn, user=user, password=password,
            compression=True, fetch_dict=True, lower_ident=True,
            websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
        )
        row = conn.execute("SELECT 1 AS ok").fetchone()
        conn.close()
    except Exception as exc:  # noqa: BLE001 - probe reports any failure
        print(f"login failed: {type(exc).__name__}: {exc}")
        return 1

    print(f"login ok: {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
