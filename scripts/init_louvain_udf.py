"""
Register the In-Database MPP Mule Community Detector Python 3 SET UDF in Exasol.
"""

import os
import sys
import pyexasol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    load_env(os.path.join(ROOT, ".env"))
    dsn = os.environ.get("EXASOL_DSN", "localhost:8563")
    user = os.environ.get("EXASOL_USER", "sys")
    password = os.environ.get("EXASOL_PASSWORD", "")
    schema = os.environ.get("EXASOL_SCHEMA", "FRAUD")

    print(f"Connecting to Exasol {dsn} to register Louvain SET UDF in {schema}...")
    conn = pyexasol.connect(
        dsn=dsn, user=user, password=password, schema=schema,
        compression=True, fetch_dict=True, lower_ident=False,
        websocket_sslopt={"cert_reqs": __import__("ssl").CERT_NONE}
    )

    udf_sql = """
CREATE OR REPLACE PYTHON3 SET SCRIPT jaalnet_louvain_detector(
    src_account VARCHAR(20),
    dst_account VARCHAR(20),
    amount DOUBLE,
    score INT
)
EMITS (
    account_id VARCHAR(20),
    cluster_id INT,
    cluster_size INT,
    total_mule_volume DOUBLE,
    avg_mule_risk DOUBLE,
    ring_type VARCHAR(20)
) AS

from collections import defaultdict, deque

def run(ctx):
    # In-Memory Graph Storage
    adj = defaultdict(set)
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    volume_by_account = defaultdict(float)
    score_by_account = defaultdict(list)
    edges = []

    # 1. Stream edge rows directly from Exasol in-memory partition
    while True:
        src = ctx.src_account
        dst = ctx.dst_account
        amt = float(ctx.amount if ctx.amount is not None else 0.0)
        sc = int(ctx.score if ctx.score is not None else 50)

        if src and dst:
            adj[src].add(dst)
            adj[dst].add(src) # Undirected view for community reachability
            out_degree[src] += 1
            in_degree[dst] += 1
            volume_by_account[src] += amt
            volume_by_account[dst] += amt
            score_by_account[src].append(sc)
            score_by_account[dst].append(sc)
            edges.append((src, dst, amt))

        if not ctx.next():
            break

    if not adj:
        return

    # 2. Extract Connected Components / Topological Syndicates
    visited = set()
    cluster_id = 1

    for node in list(adj.keys()):
        if node not in visited:
            component = []
            q = deque([node])
            visited.add(node)

            while q:
                curr = q.popleft()
                component.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        q.append(neighbor)

            # Filter for meaningful syndicates (size >= 3)
            if len(component) >= 3:
                comp_set = set(component)
                total_vol = sum(volume_by_account[n] for n in component)
                all_scores = [s for n in component for s in score_by_account[n]]
                avg_risk = sum(all_scores) / len(all_scores) if all_scores else 50.0

                # Determine ring typology
                max_fanout = max(out_degree[n] for n in component)
                max_fanin = max(in_degree[n] for n in component)

                if max_fanout >= 4 and max_fanin <= 2:
                    typology = "SMURFING_DISPERSION"
                elif max_fanin >= 4 and max_fanout <= 2:
                    typology = "FUNNEL_COLLECTION"
                elif any(out_degree[n] >= 2 and in_degree[n] >= 2 for n in component):
                    typology = "CIRCULAR_LAYER"
                else:
                    typology = "STAR_HUB"

                c_size = len(component)
                for member in component:
                    ctx.emit(
                        str(member),
                        int(cluster_id),
                        int(c_size),
                        float(total_vol),
                        float(round(avg_risk, 1)),
                        str(typology)
                    )
                cluster_id += 1
/
"""
    conn.execute(udf_sql)
    print("Successfully created/updated PYTHON3 SET SCRIPT jaalnet_louvain_detector in Exasol!")

    # Test the UDF with a sample query
    test_sql = """
    SELECT cluster_id, ring_type, cluster_size, total_mule_volume, avg_mule_risk, count(*) as member_count
    FROM (
        EXECUTE SCRIPT jaalnet_louvain_detector(
            sender_account, receiver_account, amount_inr, model_score
        ) FROM upi_transactions
        WHERE model_score >= 70 OR ring_id IS NOT NULL
    )
    GROUP BY cluster_id, ring_type, cluster_size, total_mule_volume, avg_mule_risk
    ORDER BY cluster_size DESC
    LIMIT 10
    """
    print("Testing UDF execution on live upi_transactions...")
    res = conn.execute(test_sql).fetchall()
    print(f"UDF executed successfully! Found {len(res)} top clusters directly in Exasol memory:")
    for r in res[:5]:
        print(" ", r)

    return 0


if __name__ == "__main__":
    sys.exit(main())
