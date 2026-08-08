"""Tests de la stratégie de jeu : sélection de course et de cheval.

Vérifie que « CRAZY BET » est préservé : la course est choisie sur l'écart
maximal de `rel_prob[1]` et le cheval joué est le plus qualitatif
(`prob[1]` maximal de la course choisie).
"""
from __future__ import annotations

from canasson.evaluate.roi import choose_course, pick_horse


def test_choose_course_max_ratio_delta(response: dict) -> None:
    """La course retenue est celle au plus grand écart rel_prob[1]."""
    reunion, circuit = choose_course(response)
    assert reunion == "r2"
    assert circuit == "c7"
    # le cheval n°1 de la course choisie a l'écart maximal (85 vs 30 cumulé)
    assert response[reunion][circuit]["horses"][0]["rel_prob"][1] == 85


def test_pick_horse_most_qualitative(response: dict) -> None:
    """Le cheval joué est celui au prob[1] maximal de la course choisie."""
    horse, reunion, circuit = pick_horse(response)
    assert (reunion, circuit) == ("r2", "c7")
    assert horse["nom_query"] == "GAMMA"
    assert horse["prob"][1] == 0.85


def test_choose_course_empty(response: dict) -> None:
    """Aucune course sélectionnée sur un jeu vide."""
    assert choose_course({}) == ("", "")
