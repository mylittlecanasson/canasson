"""Tests des filtres métier et du ciblage (reminder.txt de l'application d'origine)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from canasson import config
from canasson.model.features import _filter, build_target, get_factors, load_train


def test_get_factors() -> None:
    """Grille quasi-carrée : tous les diviseurs entiers de n."""
    assert get_factors(12) == [1, 2, 3, 4, 6, 12]
    assert get_factors(1) == [1]


def test_filter_discipline_et_courses() -> None:
    """Seuls PLAT, 8-12 partants déclarés, 1500-2100 m sont conservés."""
    df = pd.DataFrame(
        {
            "discipline": ["PLAT", "OBSTACLE", "PLAT", "PLAT", "PLAT"],
            "nombreDeclaresPartants": [10, 10, 6, 14, 10],
            "distance": [1800, 1800, 1800, 1800, 1200],
            "ordreArrivee": [0, 1, 2, 3, 4],
        }
    )
    kept = _filter(df)
    assert len(kept) == 1
    assert kept.iloc[0]["discipline"] == "PLAT"
    assert kept.iloc[0]["nombreDeclaresPartants"] == 10
    assert kept.iloc[0]["distance"] == 1800


def test_filter_types_mixtes() -> None:
    """Un « nan » en chaîne dans `distance` ne doit pas faire planter le filtre."""
    df = pd.DataFrame(
        {
            "discipline": ["PLAT", "PLAT"],
            "nombreDeclaresPartants": ["10", "10"],      # str
            "distance": ["1800", "nan"],                  # str, l'un non numérique
            "ordreArrivee": ["1", "2"],                   # str
        }
    )
    kept = _filter(df)
    # la ligne « nan » est écartée (distance inconnue), l'autre conservée
    assert len(kept) == 1
    assert int(kept.iloc[0]["distance"]) == 1800


def test_build_target_top_place() -> None:
    """Cible = 1 pour les places 1/2/3 (ordreArrivee < TOP_PLACE), sinon 0."""
    df = pd.DataFrame({"ordreArrivee": [0, 1, 2, 3, 4, 5]})
    target = build_target(df)
    expected = [1 if i < config.TOP_PLACE else 0 for i in df["ordreArrivee"]]
    assert target.tolist() == expected


def test_load_train_ref_date_pas_de_fuite(tmp_path, monkeypatch) -> None:
    """Backtest : load_train(ref_date) n'utilise jamais les jours postérieurs à ref_date."""
    train_dir = tmp_path / "data_train"
    train_dir.mkdir(parents=True)
    monkeypatch.setattr(config, "DATA_TRAIN_DIR", train_dir)

    ref = date(2026, 3, 1)
    inside = (ref - timedelta(days=10)).strftime("%d%m%Y")   # 19022026 — avant la référence
    outside = (ref + timedelta(days=5)).strftime("%d%m%Y")   # 06032026 — après la référence

    cols = "nom,ordreArrivee,discipline,nombreDeclaresPartants,distance\n"
    (train_dir / f"{inside}.csv").write_text(cols + "cheval,1,PLAT,10,1800\n")
    (train_dir / f"{outside}.csv").write_text(cols + "cheval,2,PLAT,10,1800\n")

    df = load_train(days=60, ref_date=ref)
    # seul le jour antérieur à la référence est chargé → aucune fuite d'information
    assert len(df) == 1
    assert df.iloc[0]["ordreArrivee"] == 1
