"""Configuration centrale de Canasson.

Regroupe les constantes métier issues de l'application d'origine
(philosophie d'implémentation inchangée) et les chemins de données
pilotés par l'environnement (compose).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("canasson.config")

# ---------------------------------------------------------------------------
# Chemins (données runtime, montées en volume par docker compose)
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.getenv("CANASSON_DATA_DIR", "./data")).expanduser()
DATA_TRAIN_DIR = DATA_DIR / "data_train"
DATA_TEST_DIR = DATA_DIR / "data_test"
DATA_CTURF_DIR = DATA_DIR / "data_cturf"
DATA_GAIN_DIR = DATA_DIR / "data_gain"          # cache des résultats PMU (dividendes, incidents)

# Clone local du repo GitHub Pages (récupéré par le module publish).
WORKTREE_DIR = DATA_DIR / "generated"

# Artefacts générés (copiés dans le worktree par publish).
ARTIFACT_INDEX = DATA_DIR / "index.html"
ARTIFACT_BETHISTORY = DATA_TEST_DIR / "bethistory.html"
ARTIFACT_CANDLE = DATA_TEST_DIR / "candle.png"

# Répertoire du package et des templates HTML (copiés verbatim de l'ancien projet).
PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "site" / "templates"


# ---------------------------------------------------------------------------
# Filtres d'apprentissage (fichier reminder.txt de l'application d'origine)
# ---------------------------------------------------------------------------
DISCIPLINE = "PLAT"
MIN_DECLARES_PARTANTS = 8
MAX_DECLARES_PARTANTS = 12
MIN_DISTANCE = 1500
MAX_DISTANCE = 2100
TRAIN_DAYS = 60          # 60 jours d'apprentissage
TOP_PLACE = 3            # basé sur les places 1/2/3 (arrivée < 3 → 1)

# Sélection de features : corrélation à `ordreArrivee` >= corrélation de `nom`.
EXCLUDED_FEATURES = ("paris_*", "incident_*")


# ---------------------------------------------------------------------------
# Stratégie de jeu
# ---------------------------------------------------------------------------
# « CRAZY BET » : jouer le cheval le plus qualitatif du jour (prob[1] max).
# La course est choisie sur l'écart maximum rel_prob[1] (cheval n°1 vs n°2).
TICKET_VALUE_CENTS = 500   # iplay = 500 centimes = 5 € en simple placé
HISTORY_DAYS_SITE = 7      # nombre de jours de pronostics affichés sur l'accueil


# ---------------------------------------------------------------------------
# Publication GitHub Pages
# ---------------------------------------------------------------------------
GIT_REPO_URL = os.getenv(
    "GIT_REPO_URL",
    "git@github.com:mylittlecanasson/mylittlecanasson.github.io.git",
)
COMMIT_MESSAGE = "comment from python script"


# ---------------------------------------------------------------------------
# Endpoints PMU (mêmes URLs que l'application d'origine, à l'exception du
# slash de fin de `programme/{day}` : l'API renvoie désormais 420 si le jour
# est suivi d'un `/`, 200 sinon).
# ---------------------------------------------------------------------------
PMU_PROGRAMME_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{day}"
CANALTURF_ARCHIVES_URL = "https://www.canalturf.com/courses_archives.php?date={iso_date}"

# Rythme de collecte (secondes) entre deux courses : l'API PMU peut répondre
# HTTP 420/204 en cas de rafale — une courte pause par course la respecte.
PMU_PAUSE = float(os.getenv("CANASSON_PMU_PAUSE", "0.5"))

# Timeout (secondes) par requête HTTP : l'API peut accepter la connexion puis
# ne plus répondre (throttle) — un timeout évite de bloquer la collecte.
PMU_TIMEOUT = float(os.getenv("CANASSON_PMU_TIMEOUT", "20"))
# `reunion` vaut déjà "r1" et `circuit` déjà "c5" (numReunion / numOrdre bruts).
PMU_RACE_URL = "https://www.pmu.fr/turf/{day}/{reunion}/{circuit}"


def ensure_dirs() -> None:
    """Crée les répertoires de données s'ils n'existent pas."""
    for directory in (DATA_DIR, DATA_TRAIN_DIR, DATA_TEST_DIR, DATA_CTURF_DIR, DATA_GAIN_DIR, WORKTREE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Configuration utilisateur (dashboard + CLI)
# ---------------------------------------------------------------------------
# Réglages éditables via le dashboard (`canasson config`). La spec pilote le
# formulaire, la validation et le badge de provenance sur le site. Les défauts
# sont les constantes ci-dessus : sans fichier sauvegardé, rien ne change —
# jamais d'erreur « no configuration ».
SETTINGS_FILE = DATA_DIR / "config.json"

# Disciplines PMU proposées dans le formulaire (la validation accepte toute
# chaîne de 1 à 16 caractères : un fichier édité à la main ne casse jamais).
DISCIPLINES = ("PLAT", "HAIE", "STEEPLE", "CROSS", "ATTELE", "MONTE")


def _fmt_euros(cents: int) -> str:
    """500 → « 5 € », 1250 → « 12.5 € » (simple placé)."""
    return f"{cents / 100:g} €"


# Chaque entrée : clé JSON, constante du module, label FR, défaut, type,
# bornes/choix, libellés de badge et aide du formulaire.
SETTINGS_SPEC: list[dict] = [
    {
        "key": "training_days", "const": "TRAIN_DAYS", "label": "Jours d'apprentissage",
        "default": TRAIN_DAYS, "vtype": "int", "min": 1, "max": 365,
        "fmt": lambda v: f"{v} j",
        "hint": "Fenêtre d'apprentissage en jours avant la date prédite.",
    },
    {
        "key": "discipline", "const": "DISCIPLINE", "label": "Discipline",
        "default": DISCIPLINE, "vtype": "str", "choices": DISCIPLINES,
        "fmt": lambda v: str(v),
        "hint": "Discipline des courses filtrées (PLAT, HAIE, STEEPLE, CROSS, ATTELE, MONTE).",
    },
    {
        "key": "min_partants", "const": "MIN_DECLARES_PARTANTS", "label": "Partants min",
        "default": MIN_DECLARES_PARTANTS, "vtype": "int", "min": 1, "max": 30,
        "fmt": str,
        "hint": "Nombre de partants déclarés — borne inférieure.",
    },
    {
        "key": "max_partants", "const": "MAX_DECLARES_PARTANTS", "label": "Partants max",
        "default": MAX_DECLARES_PARTANTS, "vtype": "int", "min": 1, "max": 30,
        "fmt": str,
        "hint": "Nombre de partants déclarés — borne supérieure (≥ partants min).",
    },
    {
        "key": "min_distance", "const": "MIN_DISTANCE", "label": "Distance min (m)",
        "default": MIN_DISTANCE, "vtype": "int", "min": 100, "max": 5000,
        "fmt": lambda v: f"{v} m",
        "hint": "Distance de course — borne inférieure (mètres).",
    },
    {
        "key": "max_distance", "const": "MAX_DISTANCE", "label": "Distance max (m)",
        "default": MAX_DISTANCE, "vtype": "int", "min": 100, "max": 5000,
        "fmt": lambda v: f"{v} m",
        "hint": "Distance de course — borne supérieure (≥ distance min).",
    },
    {
        "key": "top_place", "const": "TOP_PLACE", "label": "Cible places",
        "default": TOP_PLACE, "vtype": "int", "min": 1, "max": 9,
        "fmt": lambda v: f"1..{v}",
        "hint": "Cible : arrivée dans les N premières places → 1 (défaut : 1/2/3).",
    },
    {
        "key": "ticket_value_cents", "const": "TICKET_VALUE_CENTS", "label": "Mise (simple placé)",
        "default": TICKET_VALUE_CENTS, "vtype": "int", "min": 100, "max": 10000,
        "fmt": _fmt_euros,
        "hint": "Mise unitaire en centimes (500 = 5 €), stratégie CRAZY BET.",
    },
    {
        "key": "history_days_site", "const": "HISTORY_DAYS_SITE", "label": "Jours affichés à l'accueil",
        "default": HISTORY_DAYS_SITE, "vtype": "int", "min": 1, "max": 30,
        "fmt": lambda v: f"{v} j",
        "hint": "Nombre de jours de pronostics affichés sur la page d'accueil.",
    },
]


def default_settings() -> dict:
    """Réglages par défaut (= les constantes d'origine, inchangées)."""
    return {entry["key"]: entry["default"] for entry in SETTINGS_SPEC}


def _coerce_value(entry: dict, value) -> int | str:
    """Convertit et borne une valeur ; lève ValueError (message FR) si invalide."""
    if entry["vtype"] == "int":
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{entry['label']} doit être un entier.") from exc
        if not entry["min"] <= number <= entry["max"]:
            raise ValueError(
                f"{entry['label']} doit être compris entre {entry['min']} et {entry['max']}."
            )
        return number
    text = str(value).strip()
    if not 1 <= len(text) <= 16:
        raise ValueError(f"{entry['label']} doit faire entre 1 et 16 caractères.")
    return text


def _validate(payload: dict) -> dict:
    """Valide un payload complet (toutes clés présentes) et retourne les valeurs coerced."""
    settings = {}
    for entry in SETTINGS_SPEC:
        if entry["key"] not in payload:
            raise ValueError(f"Champ manquant : {entry['label']}.")
        settings[entry["key"]] = _coerce_value(entry, payload[entry["key"]])
    if settings["min_partants"] > settings["max_partants"]:
        raise ValueError("Partants min doit être inférieur ou égal à Partants max.")
    if settings["min_distance"] > settings["max_distance"]:
        raise ValueError("Distance min doit être inférieure ou égale à Distance max.")
    return settings


def spec_payload() -> list[dict]:
    """Vue sérialisable de SETTINGS_SPEC pour le formulaire (sans les callables)."""
    return [
        {key: value for key, value in entry.items() if key != "fmt"}
        for entry in SETTINGS_SPEC
    ]


def _apply(settings: dict) -> None:
    """Surcharge les constantes du module — les consommateurs lisent config.X à l'appel."""
    for entry in SETTINGS_SPEC:
        globals()[entry["const"]] = settings[entry["key"]]


def current_settings() -> dict:
    """Réglages effectifs : fichier sauvegardé fusionné sur les défauts.

    Fichier absent, illisible ou champ invalide → repli silencieux sur le
    défaut correspondant. Ne lève jamais (« no configuration » impossible).
    """
    settings = default_settings()
    raw: dict = {}
    if SETTINGS_FILE.is_file():
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("racine non-objet")
        except Exception as exc:
            logger.warning("Configuration %s illisible (%s) — défauts appliqués.", SETTINGS_FILE, exc)
            raw = {}
    for entry in SETTINGS_SPEC:
        if entry["key"] in raw:
            try:
                settings[entry["key"]] = _coerce_value(entry, raw[entry["key"]])
            except ValueError as exc:
                logger.warning("Réglage %s ignoré (%s).", entry["key"], exc)
    if settings["min_partants"] > settings["max_partants"]:
        logger.warning("Borne partants incohérente — valeurs par défaut rétablies.")
        settings["min_partants"], settings["max_partants"] = (
            default_settings()["min_partants"], default_settings()["max_partants"])
    if settings["min_distance"] > settings["max_distance"]:
        logger.warning("Borne distance incohérente — valeurs par défaut rétablies.")
        settings["min_distance"], settings["max_distance"] = (
            default_settings()["min_distance"], default_settings()["max_distance"])
    return settings


def save_settings(payload: dict) -> dict:
    """Valide et persiste la configuration (écriture atomique), puis l'applique."""
    settings = _validate(payload)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
    _apply(settings)
    logger.info("Configuration enregistrée : %s", SETTINGS_FILE)
    return settings


def load_settings() -> dict:
    """Applique la configuration sauvegardée (ou les défauts) aux constantes du module."""
    settings = current_settings()
    _apply(settings)
    return settings


def save_snapshot(date_str: str) -> None:
    """Mémorise la config effective dans data_test/<date>/config.json (provenance)."""
    target = DATA_TEST_DIR / date_str / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(current_settings(), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def settings_for_date(date_str: str) -> dict:
    """Réglages d'une date (snapshot écrit au predict) sinon les réglages courants."""
    snapshot = DATA_TEST_DIR / date_str / "config.json"
    if snapshot.is_file():
        try:
            raw = json.loads(snapshot.read_text(encoding="utf-8"))
            merged = {**default_settings(), **(raw if isinstance(raw, dict) else {})}
            for entry in SETTINGS_SPEC:
                try:
                    merged[entry["key"]] = _coerce_value(entry, merged[entry["key"]])
                except ValueError:
                    merged[entry["key"]] = entry["default"]
            if merged["min_partants"] > merged["max_partants"]:
                merged["min_partants"], merged["max_partants"] = (
                    default_settings()["min_partants"], default_settings()["max_partants"])
            if merged["min_distance"] > merged["max_distance"]:
                merged["min_distance"], merged["max_distance"] = (
                    default_settings()["min_distance"], default_settings()["max_distance"])
            return merged
        except Exception as exc:
            logger.warning("Snapshot %s illisible (%s) — réglages courants.", snapshot, exc)
    return current_settings()


def _badge_summary(settings: dict) -> str:
    """Une ligne compacte pour la boîte réduite (bornes regroupées)."""
    return " · ".join(
        [
            f"{settings['training_days']} j d'apprentissage",
            str(settings["discipline"]),
            f"{settings['min_partants']}-{settings['max_partants']} partants",
            f"{settings['min_distance']}-{settings['max_distance']} m",
            f"cible 1..{settings['top_place']}",
            _fmt_euros(settings["ticket_value_cents"]),
            f"{settings['history_days_site']} j à l'accueil",
        ]
    )


def config_badge_html(settings: dict | None = None) -> str:
    """Petite boîte cliquable indiquant la configuration d'où viennent les résultats."""
    settings = settings or current_settings()
    summary = _badge_summary(settings)
    rows = "".join(
        f"<li>{entry['label']} : <b>{entry['fmt'](settings[entry['key']])}</b></li>"
        for entry in SETTINGS_SPEC
    )
    return (
        "<style>details.cfg-badge{margin:1rem auto;max-width:640px;border:1px solid "
        "var(--border,#ddd);border-radius:8px;padding:.5rem 1rem;background:"
        "var(--accent-bg,#f8f8f8)}details.cfg-badge summary{cursor:pointer;font-size:.85rem}"
        "details.cfg-badge ul{margin:.5rem 0 0;padding-left:1.2rem;font-size:.85rem}</style>"
        '<details class="cfg-badge">'
        f"<summary>⚙️ Config : {summary}</summary>"
        '<div class="cfg-details"><ul>'
        f"{rows}</ul></div></details>"
    )
