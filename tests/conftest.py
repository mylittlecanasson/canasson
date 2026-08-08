"""Fixtures pytest partagées (charge le response.json de test)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def response() -> dict:
    """Le response.json de test (schéma identique à la production)."""
    return json.load(open(FIXTURES_DIR / "response.json", encoding="utf-8"))
