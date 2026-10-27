"""Shared pytest fixtures. No project code is imported at module load."""

import random

import pytest

from config import RING_IDS
from data import Transaction, generate_transaction, initial_stream


@pytest.fixture(autouse=True)
def _seed_random():
    """Make every test deterministic."""
    random.seed(42)


@pytest.fixture
def sample_txn() -> Transaction:
    """A single, deterministic transaction."""
    return generate_transaction(1)


@pytest.fixture
def sample_stream() -> list[Transaction]:
    """A fixed 30-item stream."""
    return initial_stream(30)


@pytest.fixture
def all_ring_ids() -> list[str]:
    return list(RING_IDS)
