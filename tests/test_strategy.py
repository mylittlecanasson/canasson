"""Tests de la stratégie de jeu : sélection de course et de cheval.

Vérifie que « CRAZY BET » est préservé : la course est choisie sur l'écart
maximal de `rel_prob[1]` et le cheval joué est le plus qualitatif
(`prob[1]` maximal de la course choisie).
"""
from __future__ import annotations

import json
from pathlib import Path

from canasson import config
from canasson.evaluate.roi import choose_course, evaluate_day, pick_horse


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


def _setup_gain(tmp_path, response: dict, placed: dict) -> Path:
    """Prépare data_test/<date>/response.json + rapports cachés → date_dir."""
    test_dir = tmp_path / "data_test"
    (test_dir / "01012025").mkdir(parents=True)
    (test_dir / "01012025" / "response.json").write_text(
        json.dumps(response, ensure_ascii=False), encoding="utf-8"
    )
    gain_dir = tmp_path / "data_gain"
    base = gain_dir / "01012025" / "01012025R2C7"
    base.parent.mkdir(parents=True, exist_ok=True)
    # performances → numPmu ↔ nomCheval (les 2 chevaux de la course choisie)
    Path(str(base) + "performances_detaillees_pretty.json").write_text(json.dumps({
        "participants": [{"numPmu": 1, "nomCheval": "GAMMA"}, {"numPmu": 2, "nomCheval": "DELTA"}]
    }))
    # rapports définitifs → chevaux placés du simple placé (dividende en centimes / 1 €)
    Path(str(base) + "rapports-definitifs.json").write_text(json.dumps([
        {"typePari": "E_SIMPLE_PLACE", "rapports": [
            {"combinaison": [num], "dividende": div} for num, div in placed.items()
        ]}
    ]))
    return gain_dir


def test_evaluate_day_perte_comptee_sans_pronostics(tmp_path, monkeypatch, response) -> None:
    """Un cheval non placé dans une course qui a couru = -500, même si l'API
    pronostics ne fournit aucun texte (HTTP 204 sur les anciennes dates)."""
    gain_dir = _setup_gain(tmp_path, response, placed={2: 280})  # DELTA placé, GAMMA non
    monkeypatch.setattr(config, "DATA_TEST_DIR", tmp_path / "data_test")
    monkeypatch.setattr(config, "DATA_GAIN_DIR", gain_dir)

    result = evaluate_day("01012025")
    # le pick est GAMMA (r2/c7), DELTA est placé → ticket perdu
    assert result is not None
    assert result.roi == -config.TICKET_VALUE_CENTS


def test_evaluate_day_gain_place(tmp_path, monkeypatch, response) -> None:
    """Un cheval placé empoche le dividende net du simple placé (5 €)."""
    gain_dir = _setup_gain(tmp_path, response, placed={1: 280})  # GAMMA placé
    monkeypatch.setattr(config, "DATA_TEST_DIR", tmp_path / "data_test")
    monkeypatch.setattr(config, "DATA_GAIN_DIR", gain_dir)

    result = evaluate_day("01012025")
    assert result is not None
    assert result.roi == 280 * (config.TICKET_VALUE_CENTS / 100) - config.TICKET_VALUE_CENTS
