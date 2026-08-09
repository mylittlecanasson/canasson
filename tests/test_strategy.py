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


def test_race_outcome_refreshes_stale_empty_cache(tmp_path, monkeypatch) -> None:
    """Un cache de rapports vide (course pas encore courue au premier appel)
    est rafraîchi dès que la course est attendue — le dividende réel du simple
    placé est pris en compte au lieu d'un ROI nul (régression R2C6 du 09/08/2026)."""
    from canasson.evaluate import roi

    calls: list[bool] = []

    def fake_get(url: str, cache_path, refresh: bool = False):
        calls.append(refresh)
        if "performances" in url:
            return {"participants": [{"numPmu": 1, "nomCheval": "GAMMA"}]}
        if "rapports" in url:
            if refresh:
                return [{"typePari": "E_SIMPLE_PLACE", "rapports": [{"combinaison": [1], "dividende": 280}]}]
            return [{"typePari": "EB5", "rapports": []}]  # cache périmé d'avant-course
        return {"incidents": []}

    monkeypatch.setattr(roi, "_cached_get_json", fake_get)
    race = {"url": "https://www.pmu.fr/turf/01012025/r1/c5"}
    horsetodividende = roi._race_outcome(race, tmp_path)
    assert horsetodividende == {
        "GAMMA": 280 * (config.TICKET_VALUE_CENTS / 100) - config.TICKET_VALUE_CENTS
    }
    # le refresh n'a été déclenché qu'une seule fois (le rapport simple placé)
    assert calls.count(True) == 1


def test_race_outcome_no_refresh_for_future_race(tmp_path, monkeypatch) -> None:
    """Course pas encore attendue → le cache vide n'est pas rafraîchi (inutile
    d'interroger l'API pour une course pas encore courue)."""
    from canasson.evaluate import roi

    def fake_get(url: str, cache_path, refresh: bool = False):
        if refresh:
            raise AssertionError("pas de refresh attendu pour une course future")
        if "performances" in url:
            return {"participants": [{"numPmu": 1, "nomCheval": "GAMMA"}]}
        if "rapports" in url:
            return [{"typePari": "EB5", "rapports": []}]
        return {"incidents": []}

    monkeypatch.setattr(roi, "_race_due", lambda day: False)
    monkeypatch.setattr(roi, "_cached_get_json", fake_get)
    race = {"url": "https://www.pmu.fr/turf/01012025/r1/c5"}
    assert roi._race_outcome(race, tmp_path) == {}
