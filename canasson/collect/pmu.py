"""Collecte des données depuis l'API PMU.

Port fidèle de `collect_mylittlecanasson.py` : télécharge le programme
des courses, les participants et les pronostics détaillés, puis sérialise
le tout en CSV dans `data_train/<date>.csv` (apprentissage) et
`data_test/<date>/query.csv` (cibles de prédiction).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from urllib.request import urlopen

from canasson import config

logger = logging.getLogger("canasson.collect.pmu")


def flatten_json(value):
    """Aplatit récursivement un objet JSON (dict/list) en clés plates.

    https://towardsdatascience.com/flattening-json-objects-in-python-f5343c794b10
    """
    out = {}

    def _flatten(x, name=""):
        if isinstance(x, dict):
            for key in x:
                _flatten(x[key], name + key + "_")
        elif isinstance(x, list):
            for index, item in enumerate(x):
                _flatten(item, name + str(index) + "_")
        else:
            out[name[:-1]] = x

    _flatten(value)
    return out


def normalize_json(records):
    """Complète chaque enregistrement avec toutes les clés vues (NaN si absent)."""
    keys = {}
    for record in records:
        for key in record:
            keys.setdefault(key, type(record[key]))
    for record in records:
        for key in keys:
            if key not in record:
                record[key] = float("NAN")
    return records


def write_json_in_csv(records, filename):
    """Sérialise une liste de dicts en CSV (les virgules deviennent des points)."""
    with open(filename, "w") as data_file:
        for index, record in enumerate(records):
            if index == 0:
                header = list(record.keys())
                data_file.write(",".join(header) + "\n")
            data_file.write(",".join(str(record[k]).replace(",", ".") for k in header) + "\n")


def _course_with_eparis(course) -> bool:
    """Un course est conservée seulement si elle propose un pari simple (E_)."""
    return any(paris["typePari"].startswith("E_") for paris in course["paris"])


def _collected(path) -> bool:
    """Vrai si la collecte est déjà complète : un CSV à 0 octet signale un
    échec (throttle API) et sera re-tenté au prochain passage."""
    return path.is_file() and path.stat().st_size > 0


def _fetch_json(url: str, attempts: int = 3) -> dict:
    """GET JSON avec quelques tentatives (l'API PMU throttle sporadiquement).

    Renvoie un dict vide si l'API reste inaccessible — le jour est alors
    ignoré, le pipeline continue (philosophie « skip gracieux »).

    Un corps vide (HTTP 204) n'est pas une erreur : c'est le comportement
    normal de `pronostics-detailles` sur les dates anciennes (plus de
    pronostics stockés) — loggé en DEBUG, pas en WARNING.
    """
    for attempt in range(1, attempts + 1):
        try:
            # timeout : l'API peut accepter la connexion puis ne plus répondre
            # (throttle) — sans timeout, urlopen resterait suspendu indéfiniment.
            with urlopen(url, timeout=config.PMU_TIMEOUT) as handle:
                raw = handle.read()
            if not raw:
                logger.debug("pas de contenu (HTTP 204) pour %s", url)
                return {}
            return json.loads(raw.decode())
        except Exception:
            if attempt == attempts:
                logger.warning("API PMU indisponible pour %s (%d tentative(s)).", url, attempts)
                return {}
            time.sleep(attempt * 3)
    return {}


def _download_day(strday: str, context: str) -> None:
    """Télécharge le programme d'un jour précis → CSV train ou query.

    `context="test"` écrit `data_test/<strday>/query.csv` ; `context="train"`
    écrit `data_train/<strday>.csv`. Le skip est contextuel : un jour peut être
    à la fois dans l'historique d'apprentissage et en course cible (backtest).
    """
    if "test" in context:
        if _collected(config.DATA_TEST_DIR / strday / "query.csv"):
            logger.debug("skip: data_test/%s/query.csv", strday)
            return
    elif _collected(config.DATA_TRAIN_DIR / (strday + ".csv")):
        logger.debug("skip: data_train/%s.csv", strday)
        return

    logger.info("Téléchargement %s/%s", context, strday)
    urlday = config.PMU_PROGRAMME_URL.format(day=strday)
    dataday = _fetch_json(urlday)
    if "programme" not in dataday:
        return

    dict_participants = []
    for reunion in dataday["programme"]["reunions"]:
        for course in reunion["courses"]:
            strreunion = str(course["numReunion"])
            strcourse = str(course["numOrdre"])
            if not _course_with_eparis(course):
                continue

            urlcourses = urlday + "/R" + strreunion + "/C" + strcourse + "/"
            datacourses = flatten_json(course)

            urlparticipants = urlcourses + "participants?specialisation=INTERNET"
            urlpronodetaille = urlcourses + "pronostics-detailles"
            # `_fetch_json` réessaie avec backoff pour les participants (données ML
            # essentielles). Les pronostics répondent HTTP 204 « no content » sur les
            # dates anciennes : ce n'est pas transitoire, une seule tentative suffit
            # (le texte/cribles replie alors sur « Sans commentaire »). Une pause
            # courte par course évite de déclencher le throttling de l'API.
            dataparticipants = _fetch_json(urlparticipants)
            datapronodetaille = _fetch_json(urlpronodetaille, attempts=1)
            time.sleep(config.PMU_PAUSE)
            if "participants" not in dataparticipants:
                logger.warning("participants indisponibles : %s/R%s/C%s", strday, strreunion, strcourse)
                continue

            for participant in dataparticipants["participants"]:
                participant = flatten_json(participant)

                # texte funky à côté du cheval
                if "commentaire" in datapronodetaille and "texte" in datapronodetaille["commentaire"]:
                    participant["commentaire"] = datapronodetaille["commentaire"]["texte"]
                else:
                    participant["commentaire"] = "Sans commentaire"

                if "cribles" in datapronodetaille:
                    for onepronodetail in datapronodetaille["cribles"]:
                        if onepronodetail["numPmu"] == participant["numPmu"]:
                            participant["cribles"] = onepronodetail["commentaire"]

                if "cribles" not in participant:
                    participant["cribles"] = "Sans commentaire"

                # fusion course + participant
                participant = {**participant, **datacourses}
                dict_participants.append(participant)

    normalize_json(dict_participants)

    if "test" in context:
        (config.DATA_TEST_DIR / strday).mkdir(parents=True, exist_ok=True)
        strday = strday + "/query"

    outfile = config.DATA_DIR / ("data_" + context) / (strday + ".csv")
    write_json_in_csv(dict_participants, outfile)


def download_data(context: str, delta: int, step: int) -> None:
    """Télécharge `delta` jours espacés de `step` jours.

    - `context="test"`, `step=-1` : la course de demain (query).
    - `context="train"`, `step=1` : l'historique d'apprentissage (60 jours).
    """
    datetime_delta = timedelta(days=step)
    datetime_day = date.today()

    for _ in range(delta):
        # next day
        datetime_day = datetime_day - datetime_delta
        _download_day(datetime_day.strftime("%d%m%Y"), context)


def download_query(date_query: str) -> None:
    """Télécharge le programme d'une date précise → data_test/<date>/query.csv."""
    _download_day(date_query, "test")


def run() -> None:
    """Télécharge la course de demain (test) et 60 jours d'historique (train)."""
    config.ensure_dirs()
    # download tomorrow
    download_data("test", 1, -1)
    # download yesterdays (historique d'apprentissage)
    download_data("train", config.TRAIN_DAYS, 1)
