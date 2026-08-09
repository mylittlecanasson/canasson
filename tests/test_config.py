"""Tests du modèle de configuration : persistance, validation, badge, snapshots."""
from __future__ import annotations

import json

import pytest

from canasson import config
from canasson.model import features


@pytest.fixture
def settings_env(monkeypatch, tmp_path):
    """Redirige les chemins vers un tmp_path et restaure les constantes du module."""
    saved = {entry["const"]: getattr(config, entry["const"]) for entry in config.SETTINGS_SPEC}
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_TRAIN_DIR", tmp_path / "data_train")
    monkeypatch.setattr(config, "DATA_TEST_DIR", tmp_path / "data_test")
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "config.json")
    yield
    # _apply surcharge les globals directement (hors monkeypatch) → restauration manuelle.
    for const, value in saved.items():
        setattr(config, const, value)


def _payload(**overrides) -> dict:
    payload = config.default_settings()
    payload.update(overrides)
    return payload


def test_defaults_without_file(settings_env) -> None:
    """Aucun fichier → défauts, sans erreur (« no configuration » impossible)."""
    assert config.current_settings() == config.default_settings()
    config.load_settings()
    assert config.TRAIN_DAYS == 60
    assert config.DISCIPLINE == "PLAT"


def test_save_valid_applies_and_persists(settings_env) -> None:
    settings = config.save_settings(_payload(training_days=30, min_distance=1200))
    assert settings["training_days"] == 30
    assert config.TRAIN_DAYS == 30          # constantes du module surchargées
    assert config.MIN_DISTANCE == 1200
    saved = json.loads(config.SETTINGS_FILE.read_text(encoding="utf-8"))
    assert saved["training_days"] == 30
    assert saved["max_distance"] == 2100    # autres réglages = défauts


def test_load_applies_saved_file(settings_env) -> None:
    config.SETTINGS_FILE.write_text(json.dumps(_payload(training_days=45)), encoding="utf-8")
    config.load_settings()
    assert config.TRAIN_DAYS == 45
    assert config.MIN_DECLARES_PARTANTS == 8


def test_save_rejects_invalid(settings_env) -> None:
    with pytest.raises(ValueError, match="Partants min"):
        config.save_settings(_payload(min_partants=15, max_partants=10))
    with pytest.raises(ValueError, match="Distance min"):
        config.save_settings(_payload(min_distance=3000, max_distance=1500))
    with pytest.raises(ValueError, match="compris entre"):
        config.save_settings(_payload(training_days=0))
    with pytest.raises(ValueError, match="entier"):
        config.save_settings(_payload(top_place="abc"))
    assert not config.SETTINGS_FILE.exists()  # échec → aucune écriture


def test_corrupt_file_falls_back_to_defaults(settings_env) -> None:
    config.SETTINGS_FILE.write_text("{ pas du json", encoding="utf-8")
    assert config.current_settings() == config.default_settings()


def test_out_of_range_field_falls_back_to_default(settings_env) -> None:
    config.SETTINGS_FILE.write_text(json.dumps(_payload(training_days=9999)), encoding="utf-8")
    settings = config.current_settings()
    assert settings["training_days"] == 60  # défaut rétabli
    assert settings["top_place"] == 3


def test_incoherent_bounds_fall_back(settings_env) -> None:
    config.SETTINGS_FILE.write_text(
        json.dumps(_payload(min_distance=3500, max_distance=1500)), encoding="utf-8"
    )
    settings = config.current_settings()
    assert (settings["min_distance"], settings["max_distance"]) == (1500, 2100)


def test_badge_html_clickable_and_contains_values(settings_env) -> None:
    badge = config.config_badge_html()
    assert "<details" in badge and "<summary" in badge
    assert "60 j d'apprentissage" in badge
    assert "PLAT" in badge
    assert "8-12 partants" in badge
    assert "1500-2100 m" in badge
    assert "5 €" in badge


def test_settings_for_date_snapshot(settings_env) -> None:
    # pas de snapshot → réglages courants (défauts ici)
    assert config.settings_for_date("01012026") == config.current_settings()
    # snapshot présent → valeurs du snapshot
    config.save_settings(_payload(training_days=21))
    target = config.DATA_TEST_DIR / "01012026"
    target.mkdir(parents=True)
    (target / "config.json").write_text(json.dumps(config.current_settings()), encoding="utf-8")
    assert config.settings_for_date("01012026")["training_days"] == 21


def test_save_snapshot_writes_effective(settings_env) -> None:
    config.save_settings(_payload(training_days=33))
    config.save_snapshot("02022026")
    path = config.DATA_TEST_DIR / "02022026" / "config.json"
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["training_days"] == 33


def test_load_train_default_not_frozen_at_import() -> None:
    """Le défaut de load_train est résolu à l'appel (config.TRAIN_DAYS dynamique)."""
    assert features.load_train.__defaults__[0] is None
