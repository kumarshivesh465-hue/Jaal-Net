"""One-off: set the SYS password on the local Exasol to EXASOL_PASSWORD.

The 7.1.30 image ignored the EXASOL_PASSWORD container env var on first
initialisation (the cluster kept the factory default `exasol`), so the only
way to make the documented credential true is to ALTER USER explicitly.
"""
import os, ssl, sys
import pyexasol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

dsn = os.environ.get("EXASOL_DSN", "localhost:8563")
target = os.environ["EXASOL_PASSWORD"]

conn = pyexasol.connect(dsn=dsn, user="sys", password="exasol",
                        compression=True, fetch_dict=True, lower_ident=True,
                        websocket_sslopt={"cert_reqs": ssl.CERT_NONE})
conn.execute(f'ALTER USER SYS IDENTIFIED BY "{target}"')
conn.close()
print("SYS password updated")
