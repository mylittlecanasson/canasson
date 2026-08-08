"""Configuration centrale de Canasson.

Regroupe les constantes métier issues de l'application d'origine
(philosophie d'implémentation inchangée) et les chemins de données
pilotés par l'environnement (compose).
"""
from __future__ import annotations

import os
from pathlib import Path

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
