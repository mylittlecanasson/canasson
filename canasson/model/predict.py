"""Entraînement du RandomForest et inférence sur la course cible → response.json.

Port fidèle de `process_final_v0.1.py`. Chaque cheval reçoit une probabilité
(`prob[0]`, `prob[1]`) normalisée par circuit (`rel_prob`, `total_prob`) et
le résultat est sérialisé dans `data_test/<date>/response.json`.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn import metrics, model_selection, preprocessing
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import ConfusionMatrixDisplay

from canasson import config
from canasson.model import features

logger = logging.getLogger("canasson.model.predict")


def default_date() -> str:
    """Date cible par défaut : demain."""
    return (date.today() + timedelta(days=1)).strftime("%d%m%Y")


def _as_int(value):
    """Convertit un entier que pandas lit en float (1.0) vers un int.

    normalize_json comble les clés manquantes par NaN : dès qu'une colonne
    contient un « nan », pandas la lit en float64 et str(1.0) donne "1.0",
    ce qui casserait les URLs PMU et l'affichage des numéros. En cas de NaN
    réel, on renvoie la valeur brute plutôt que de faire planter l'inférence.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return value


def _save_heatmap(encoded_df_train: pd.DataFrame, pertinent_index: list[str], date_query: str) -> None:
    heatmap_columns = encoded_df_train[pertinent_index].copy()
    heatmap_columns["ordreArrivee"] = encoded_df_train["ordreArrivee"]
    matrix = heatmap_columns.corr().round(2)

    _, ax = plt.subplots(figsize=(len(pertinent_index), len(pertinent_index) / 2))
    sns.heatmap(matrix, annot=True, linewidths=0.1, cmap="YlGnBu", ax=ax)
    plt.savefig(config.DATA_TEST_DIR / date_query / "heatmap.png", bbox_inches="tight")
    plt.close()


def _predict_rows(
    model: RandomForestClassifier,
    min_max_scaler,
    encoders: dict,
    encoded_df_query: pd.DataFrame,
    df_query: pd.DataFrame,
    date_query: str,
    pertinent_index: list[str],
) -> dict:
    """Inférence cheval par cheval → structure todump (schéma response.json)."""
    todump: dict = {}
    try:
        scaled = min_max_scaler.transform(encoded_df_query[pertinent_index])
    except ValueError:
        # si le filtre laisse 0 course, l'exception « Found array with 0 sample(s) »
        # est attendue : on ne prédit alors rien.
        logger.warning("0 échantillon(s) à prédire pour %s.", date_query)
        return todump

    for rowite, row in enumerate(scaled):
        prob = model.predict_proba([row])[0].tolist()

        # des valeurs scalées vers les valeurs encodées puis lisibles
        inverse_scaler = min_max_scaler.inverse_transform([row])
        df_inverse = pd.DataFrame(inverse_scaler, index=[0], columns=pertinent_index).astype(np.int32)
        readable = {
            column: encoders[column].inverse_transform(df_inverse[column].values)[0]
            for column in df_inverse.columns
        }

        # on retrouve les infos de contexte depuis le fichier query
        row_query = df_query.loc[[rowite]]
        # numReunion/numOrdre/numPmu sont des entiers lus parfois en float (NaN) :
        # on les re-convertit en int pour des URLs PMU propres (r1/c3, pas r1.0/c3.0).
        num_reunion = "r" + str(_as_int(row_query["numReunion"].values[0]))
        num_ordre = "c" + str(_as_int(row_query["numOrdre"].values[0]))
        nom_verify = str(row_query["nom"].values[0])
        num_pmu_verify = str(_as_int(row_query["numPmu"].values[0]))
        commentaire = str(row_query["commentaire"].values[0])
        cribles = str(row_query["cribles"].values[0])
        url = config.PMU_RACE_URL.format(day=date_query, reunion=num_reunion, circuit=num_ordre)

        todump.setdefault(num_reunion, {}).setdefault(
            num_ordre, {"url": url, "commentaire": commentaire, "horses": []}
        )
        todump[num_reunion][num_ordre]["horses"].append(
            {
                "nom": readable["nom"],
                "nom_query": nom_verify,
                "numPmu_query": num_pmu_verify,
                "cribles": cribles,
                "prob": prob,
            }
        )
    return todump


def _normalize_winrates(todump: dict) -> dict:
    """Normalise chaque cheval sur la somme du circuit → rel_prob, total_prob."""
    circuit_winrate: dict = {}
    for reunion, circuits in todump.items():
        for circuit, data in circuits.items():
            total = [0, 0]
            for horse in data["horses"]:
                total[0] += horse["prob"][0]
                total[1] += horse["prob"][1]
            circuit_winrate.setdefault(reunion, {})[circuit] = total

    for reunion, circuits in todump.items():
        for circuit, data in circuits.items():
            total = circuit_winrate[reunion][circuit]
            data["total_prob"] = total
            for horse in data["horses"]:
                horse["rel_prob"] = [
                    int((horse["prob"][0] / total[0]) * 100),
                    int((horse["prob"][1] / total[1]) * 100),
                ]
    return todump


def run(date_str: str | None = None) -> None:
    """Entraîne le modèle sur 60 jours et prédit la date cible (défaut : demain).

    Quand une date passée est prédite (backtest/rerun), l'apprentissage se
    réfère à cette date (ref_date) pour n'utiliser que les données disponibles
    à l'époque — jamais les jours suivants (pas de fuite d'information).
    """
    config.ensure_dirs()
    date_query = date_str or default_date()
    logger.info("Prédiction pour %s", date_query)

    ref_date = datetime.strptime(date_query, "%d%m%Y").date() if date_str else None
    df_train = features.load_train(ref_date=ref_date)
    df_query = features.load_query(date_query)

    # encodage commun train + query (mêmes encoders)
    encoded_merge, encoders = features.encode(pd.concat([df_train, df_query], ignore_index=True))
    encoded_df_train = encoded_merge.iloc[: len(df_train)]
    encoded_df_query = encoded_merge.iloc[len(df_train):]

    pertinent_index = features.select_features(encoded_df_train, encoded_df_query, df_train)
    _save_heatmap(encoded_df_train, pertinent_index, date_query)

    y = encoded_df_train["ordreArrivee"]
    min_max_scaler = preprocessing.MinMaxScaler()
    x = min_max_scaler.fit_transform(encoded_df_train[pertinent_index])

    train_x, test_x, train_y, test_y = model_selection.train_test_split(
        x, y, test_size=0.2, random_state=1, shuffle=False
    )

    model = RandomForestClassifier(max_depth=20)
    model.fit(train_x, train_y)

    y_pred = model.predict(test_x)
    cm = metrics.confusion_matrix(y_pred, test_y)
    total = sum(sum(cm))
    accuracy = (cm[0][0] + cm[1][1]) / total
    specificity = cm[0][0] / (cm[0][0] + cm[0][1])
    logger.info("Accuracy: %.3f -- Specificity: %.3f -- Confusion: %s", accuracy, specificity, cm)

    ConfusionMatrixDisplay.from_estimator(model, test_x, test_y)
    plt.savefig(config.DATA_TEST_DIR / date_query / "confusionmatrix.png", bbox_inches="tight")
    plt.close()

    todump = _predict_rows(
        model, min_max_scaler, encoders, encoded_df_query, df_query, date_query, pertinent_index
    )
    todump = _normalize_winrates(todump)

    with open(config.DATA_TEST_DIR / date_query / "response.json", "w", encoding="utf-8") as handle:
        json.dump(todump, handle, ensure_ascii=False, indent=4)
    logger.info("response.json écrit pour %s (%d réunion(s)).", date_query, len(todump))
