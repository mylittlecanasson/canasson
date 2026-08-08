"""Tests du schéma response.json (préserver exactement le format d'origine)."""
from __future__ import annotations

import math

import pytest

from canasson.model.predict import _as_int


def test_response_schema(response: dict) -> None:
    """Structure rN → cN → {url, commentaire, total_prob, horses}."""
    for reunion, circuits in response.items():
        assert reunion.startswith("r")
        for circuit, race in circuits.items():
            assert circuit.startswith("c")
            assert set(race) == {"url", "commentaire", "total_prob", "horses"}
            assert race["url"].startswith("https://www.pmu.fr/turf/")
            assert isinstance(race["commentaire"], str)
            assert len(race["total_prob"]) == 2
            assert all(isinstance(v, (int, float)) for v in race["total_prob"])
            assert race["horses"]


def test_horse_fields(response: dict) -> None:
    """Chaque cheval porte nom, nom_query, numPmu_query, cribles, prob et rel_prob."""
    for race in (c for r in response.values() for c in r.values()):
        for horse in race["horses"]:
            assert set(horse) == {
                "nom",
                "nom_query",
                "numPmu_query",
                "cribles",
                "prob",
                "rel_prob",
            }
            assert len(horse["prob"]) == 2
            assert len(horse["rel_prob"]) == 2
            assert all(isinstance(p, (int, float)) for p in horse["prob"])
            assert all(isinstance(p, int) for p in horse["rel_prob"])


def test_as_int_convertit_floats() -> None:
    """Les numéros lus en float par pandas (1.0) doivent redevenir int → URLs r1/c3."""
    assert _as_int(1.0) == 1
    assert _as_int("2.0") == 2
    assert _as_int(3) == 3
    # NaN réel : renvoyer la valeur brute (ici float nan) plutôt que de planter
    assert math.isnan(_as_int(float("nan")))


def test_rel_prob_coherent(response: dict) -> None:
    """rel_prob = int(prob / somme_du_circuit * 100) et total_prob = sommes."""
    for race in (c for r in response.values() for c in r.values()):
        total0 = sum(h["prob"][0] for h in race["horses"])
        total1 = sum(h["prob"][1] for h in race["horses"])
        assert race["total_prob"] == pytest.approx([total0, total1])
        for horse in race["horses"]:
            assert horse["rel_prob"][0] == int(horse["prob"][0] / total0 * 100)
            assert horse["rel_prob"][1] == int(horse["prob"][1] / total1 * 100)
