"""Ingénierie de features : chargement, filtres et sélection par corrélation.

Port fidèle de `process_final_v0.1.py`. La sélection de features conserve la
philosophie d'origine : les colonnes sont disposées en grille quasi-carrée
(getFactors) et seules celles dont la corrélation à `ordreArrivee` est
supérieure ou égale à celle de `nom` sont conservées (hors `paris_*` et
`incident_*`).
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from canasson import config

logger = logging.getLogger("canasson.model.features")

# Features exclues de la sélection (identiques à l'application d'origine).
EXCLUDED_FEATURES = (re.compile(r"paris_.*"), re.compile(r"^incident.*"))


def get_factors(n: int) -> list[int]:
    """Retourne tous les diviseurs entiers de n (grille quasi-carrée)."""
    return [i for i in range(1, n + 1) if n % i == 0]


def _filter(df: pd.DataFrame) -> pd.DataFrame:
    """Applique les filtres métier : PLAT, 8-12 partants déclarés, 1500-2100 m."""
    # Types mixtes possibles dans les CSV (un « nan » en chaîne rend toute la
    # colonne « object ») → on force le numérique avant les comparaisons ; les
    # valeurs non numériques deviennent NaN et la ligne est écartée (>= NaN = False).
    for column in ("nombreDeclaresPartants", "distance", "ordreArrivee"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df[
        (df["discipline"] == config.DISCIPLINE)
        & (df["nombreDeclaresPartants"] >= config.MIN_DECLARES_PARTANTS)
        & (df["nombreDeclaresPartants"] <= config.MAX_DECLARES_PARTANTS)
        & (df["distance"] >= config.MIN_DISTANCE)
        & (df["distance"] <= config.MAX_DISTANCE)
    ]


def load_train(days: int = config.TRAIN_DAYS, ref_date: date | None = None) -> pd.DataFrame:
    """Charge et filtre les `days` jours d'apprentissage précédant `ref_date`.

    Par défaut (run quotidien), on part d'aujourd'hui — comportement d'origine.
    Pour prédire une date passée (backtest), on part de cette date afin de
    n'utiliser que les données disponibles **au moment** de la prédiction
    (pas de fuite d'information : les jours postérieurs sont exclus).
    """
    frames = []
    today = ref_date or date.today()
    for offset in range(days, 0, -1):
        strday = (today - timedelta(days=offset)).strftime("%d%m%Y")
        path = config.DATA_TRAIN_DIR / (strday + ".csv")
        if not path.is_file():
            logger.warning("Jour d'apprentissage manquant : %s", path)
            continue
        try:
            # low_memory=False : dtype inféré sur la colonne entière (sinon
            # DtypeWarning + types mixtes par chunks) ; `_filter` coerce ensuite.
            frames.append(_filter(pd.read_csv(path, low_memory=False)))
        except Exception as exc:
            logger.warning("Jour ignoré pour l'apprentissage (%s) : %s", path, exc)
    if not frames:
        raise FileNotFoundError(f"Aucune donnée d'apprentissage dans {config.DATA_TRAIN_DIR}")
    return pd.concat(frames, ignore_index=True)


def load_query(date_query: str) -> pd.DataFrame:
    """Charge et filtre la course cible depuis data_test/<date>/query.csv."""
    path = config.DATA_TEST_DIR / date_query / "query.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Requête introuvable : {path}")
    return _filter(pd.read_csv(path)).reset_index(drop=True)


def encode(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    """Encode toutes les colonnes : int quand possible, sinon str, puis LabelEncoder."""
    merged = df.copy()
    for column in merged.columns:
        try:
            merged[column] = merged[column].astype(int)
        except (TypeError, ValueError):
            merged[column] = merged[column].astype(str)

    encoders: dict[str, LabelEncoder] = {}
    for column in merged.columns:
        encoder = LabelEncoder()
        merged[column] = encoder.fit_transform(merged[column])
        encoders[column] = encoder
    return merged, encoders


def build_target(df_train: pd.DataFrame) -> pd.Series:
    """Cible : 1 pour les places 1/2/3 (ordreArrivee < 3), sinon 0."""
    return df_train.apply(lambda x: 1 if x["ordreArrivee"] < config.TOP_PLACE else 0, axis=1)


def select_features(
    encoded_df_train: pd.DataFrame, encoded_df_query: pd.DataFrame, df_train: pd.DataFrame
) -> list[str]:
    """Sélectionne les colonnes corrélées à l'ordre d'arrivée (grille quasi-carrée)."""
    # cible : places 1/2/3 → 1
    encoded_df_train["ordreArrivee"] = build_target(df_train)

    listsize = len(encoded_df_query.columns)
    factors = get_factors(listsize)

    reshape_x = factors[0]
    reshape_y = listsize / factors[0]
    deltareshape = 9999
    for factor in factors:
        if deltareshape > abs(factor - (listsize / factor)):
            reshape_y = factor
            reshape_x = listsize / factor
            deltareshape = abs(reshape_x - reshape_y)

    grid = np.array(encoded_df_query.columns.tolist()).reshape(int(reshape_x), int(reshape_y))

    pertinent_index: list[str] = []
    for explore in grid:
        explore = explore.tolist()
        if "ordreArrivee" not in explore:
            explore.append("ordreArrivee")
        if "nom" not in explore:
            explore.append("nom")

        matrix = encoded_df_train[explore].corr().round(2)
        for index, value in matrix["ordreArrivee"].items():
            # ne garder que les arguments plus corrélés que nom:ordreArrivee
            if value >= matrix["nom"]["ordreArrivee"] and index not in ("ordreArrivee", "nom"):
                pertinent_index.append(str(index))

    pertinent_index = [i for i in pertinent_index if not EXCLUDED_FEATURES[0].match(i)]
    pertinent_index = [i for i in pertinent_index if not EXCLUDED_FEATURES[1].match(i)]
    if "nom" not in pertinent_index:
        pertinent_index.insert(0, "nom")

    logger.info("Sélection de %d feature(s) corrélées.", len(pertinent_index))
    logger.debug("pertinent_index : %s", pertinent_index)
    return pertinent_index
