"""Mock UPI transaction stream and fraud ring generator. Implements CONTRACTS.md section 5."""

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import networkx as nx

import config

random.seed(42)

INDIAN_STATES = config.INDIAN_STATE_CODES


@dataclass
class Transaction:
    txn_id: str
    timestamp: datetime
    sender: str
    receiver: str
    amount: float
    score: int
    action: str
    state: str
    device_change: bool
    ip_risk: float
    ring_id: Optional[str] = None

    @property
    def explanation(self) -> list[tuple[str, float]]:
        """Attribution signal weights scaled proportionally by transaction risk score."""
        base = [
            ("2-hop cycle detected", 0.34),
            ("Sender velocity spike", 0.28),
            ("New device + IP change", 0.19),
            ("Receiver mule-flagged", 0.12),
            ("Amount > 95th percentile", 0.07),
        ]
        scale = max(0.05, self.score / 100)
        out = [(label, round(w * scale, 3)) for label, w in base]
        return sorted(out, key=lambda x: -x[1])


def _acct() -> str:
    prefix = random.choice("ABCDEFGH")
    return f"{prefix}***{random.randint(1000, 9999)}"


def _make_ring(n: int = 8) -> list[str]:
    """Create a mule ring — circular flow with a layering chain."""
    accounts = [_acct() for _ in range(n)]
    return accounts


# rings are generated once at import so the graphs stay stable across reruns
RINGS: dict[str, list[str]] = {
    "RING-001": _make_ring(8),
    "RING-002": _make_ring(5),
    "RING-003": _make_ring(12),
}


def action_from_score(score: int) -> str:
    """Map a 0-100 score to an action using config thresholds."""
    if score < config.THRESHOLD_MONITOR:
        return config.ACTION_ALLOW
    if score < config.THRESHOLD_STEPUP:
        return config.ACTION_MONITOR
    if score < config.THRESHOLD_BLOCK:
        return config.ACTION_STEPUP
    return config.ACTION_BLOCK


def _score_from_features(
    ring_id: Optional[str], device_change: bool, ip_risk: float, amount: float
) -> int:
    score = 15
    if ring_id:
        score += random.randint(55, 75)
    if device_change:
        score += random.randint(8, 16)
    score += int(ip_risk * 20)
    if amount > 40000:
        score += random.randint(4, 10)
    return min(100, max(0, score))


def generate_transaction(i: int) -> Transaction:
    """Generate one mock transaction. i must be >= 0."""
    if i < 0:
        raise ValueError(f"i must be >= 0, got {i}")

    in_ring = random.random() < 0.02
    ring_id = None
    if in_ring:
        ring_id = random.choice(list(RINGS.keys()))
        accounts = RINGS[ring_id]
        sender = random.choice(accounts)
        receiver = random.choice([a for a in accounts if a != sender])
    else:
        sender = _acct()
        receiver = _acct()

    amount = round(random.choice([
        random.uniform(50, 2000),
        random.uniform(2000, 20000),
        random.uniform(20000, 100000),
    ]), 2)

    device_change = random.random() < 0.15
    ip_risk = random.random() * (0.9 if in_ring else 0.35)
    score = _score_from_features(ring_id, device_change, ip_risk, amount)

    return Transaction(
        txn_id=f"UPI-{int(time.time())}-{i:05d}",
        timestamp=datetime.now() - timedelta(seconds=random.randint(0, 5)),
        sender=sender,
        receiver=receiver,
        amount=amount,
        score=score,
        action=action_from_score(score),
        state=random.choice(INDIAN_STATES),
        device_change=device_change,
        ip_risk=round(ip_risk, 3),
        ring_id=ring_id,
    )


def initial_stream(n: int = 30) -> list[Transaction]:
    """Return n transactions ordered newest-first.

    Preconditions: 1 <= n <= 500. Raises ValueError otherwise.
    """
    if not (1 <= n <= 500):
        raise ValueError(f"n must be in [1, 500], got {n}")
    stream = [generate_transaction(i) for i in range(n)]
    stream.sort(key=lambda t: t.timestamp, reverse=True)
    return stream


def build_ring_graph(ring_id: str) -> nx.DiGraph:
    """Build the directed graph for a known mule ring.

    Preconditions: ring_id in config.RING_IDS. Raises ValueError otherwise.
    """
    if ring_id not in RINGS:
        raise ValueError(f"Unknown ring_id: {ring_id}")

    G = nx.DiGraph()
    accounts = RINGS[ring_id]

    for a in accounts:
        G.add_node(a, score=random.randint(60, 95))

    # circular flow
    for i in range(len(accounts)):
        a = accounts[i]
        b = accounts[(i + 1) % len(accounts)]
        G.add_edge(a, b, amount=round(random.uniform(5000, 45000), 2), edge_type=config.EDGE_RING)

    # layering shortcuts
    for _ in range(len(accounts) // 2):
        a, b = random.sample(accounts, 2)
        if not G.has_edge(a, b):
            G.add_edge(a, b, amount=round(random.uniform(2000, 30000), 2), edge_type=config.EDGE_LAYERING)

    return G


def build_neighborhood_graph(txn: Transaction, hops: int = 2) -> nx.DiGraph:
    """Build a `hops`-hop neighborhood graph around a transaction's sender+receiver.

    Preconditions: 1 <= hops <= 3. Raises ValueError otherwise.
    """
    if not (1 <= hops <= 3):
        raise ValueError(f"hops must be in [1, 3], got {hops}")

    G = nx.DiGraph()
    G.add_edge(
        txn.sender, txn.receiver,
        amount=txn.amount,
        edge_type=config.EDGE_RING if txn.ring_id else config.EDGE_NORMAL,
    )

    # add a few random neighbors for realism
    neighbor_count = min(config.MAX_NEIGHBORS_PER_NODE, random.randint(4, 9) * hops)
    for _ in range(neighbor_count):
        a = random.choice([txn.sender, txn.receiver])
        b = _acct()
        if a == txn.sender and b == txn.receiver:
            continue
        G.add_edge(a, b, amount=round(random.uniform(500, 25000), 2), edge_type=config.EDGE_NORMAL)

    for node in G.nodes:
        G.nodes[node]["score"] = random.randint(10, 95)

    G.nodes[txn.sender]["score"] = txn.score
    return G
