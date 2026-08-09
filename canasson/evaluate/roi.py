"""Calcul du ROI journalier selon la stratégie « CRAZY BET ».

Port fidèle de `winrate_mylittlecanasson.py`. Pour chaque jour disposant d'un
`response.json`, on récupère les résultats réels auprès de l'API PMU
(performances détaillées, rapports définitifs, incidents) et on joue **le
cheval le plus qualitatif** : celui au `prob[1]` maximal, dans la course à
l'écart de `rel_prob[1]` maximal (cheval n°1 vs n°2). Ticket de 5 € en
simple placé.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import requests

from canasson import config

logger = logging.getLogger("canasson.evaluate.roi")

# Endpoints PMU pour les résultats réels (identiques à l'application d'origine).
_PMU_PERF_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{day}/{reunion}/{circuit}/performances-detaillees/pretty"
_PMU_RAPPORTS_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{day}/{reunion}/{circuit}/rapports-definitifs?specialisation=INTERNET&combinaisonEnTableau=true"
_PMU_INCIDENTS_URL = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{day}/{reunion}/{circuit}?specialisation=INTERNET&combinaisonEnTableau=true"


@dataclass
class DayResult:
    """Résultat de l'évaluation d'un jour."""

    date: str
    roi: int
    row_html: str


def _cached_get_json(url: str, cache_path: Path, refresh: bool = False):
    """GET JSON avec cache local dans data_gain (comme l'application d'origine).

    `refresh=True` ignore le cache et réinterroge l'API : les résultats d'une
    course peuvent être indisponibles au premier appel (avant la course) puis
    arriver plus tard — un cache vide ne doit pas geler l'évaluation.
    """
    if refresh or not cache_path.is_file():
        data = requests.get(url, timeout=config.PMU_TIMEOUT).json()
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
        return data
    return json.load(open(cache_path, encoding="utf-8"))


def _race_due(day: str) -> bool:
    """True si la course est attendue (jour ≤ aujourd'hui) : ses résultats
    doivent être disponibles, un cache vide est alors suspect (à rafraîchir)."""
    try:
        return datetime.strptime(day, "%d%m%Y").date() <= date.today()
    except ValueError:
        return True


def _race_outcome(response_race: dict, date_dir: Path) -> dict:
    """Construit {nomCheval: dividende} pour une course à partir des résultats réels.

    Retourne un dict vide si la course n'est pas terminée / jamais démarrée.
    """
    day, reunion, circuit = response_race["url"].split("/")[-3:]
    reunion, circuit = reunion.upper(), circuit.upper()
    base_path = date_dir / f"{day}{reunion}{circuit}"

    nametonumpmu = {}
    horsetodividende: dict = {}

    # performances détaillées → correspondance numPmu ↔ nomCheval
    try:
        data = _cached_get_json(
            _PMU_PERF_URL.format(day=day, reunion=reunion, circuit=circuit),
            Path(str(base_path) + "performances_detaillees_pretty.json"),
        )
        for participant in data["participants"]:
            nametonumpmu[participant["numPmu"]] = participant["nomCheval"]
    except Exception as exc:
        logger.debug("performances indisponibles %s (%s)", base_path, exc)

    # rapports définitifs → dividende du simple placé (gagnant)
    try:
        rapports_path = Path(str(base_path) + "rapports-definitifs.json")
        data = _cached_get_json(
            _PMU_RAPPORTS_URL.format(day=day, reunion=reunion, circuit=circuit),
            rapports_path,
        )
        # Cache vide car la course n'était pas finie au premier appel (résultat
        # capturé trop tôt, puis jamais rafraîchi) : si la course est attendue,
        # on réinterroge une fois pour prendre en compte le résultat réel.
        entries = data if isinstance(data, list) else []
        has_simple_place = any(
            "E_SIMPLE_PLACE" in t.get("typePari", "")
            or "SIMPLE_PLACE_INTERNATIONAL" in t.get("typePari", "")
            for t in entries
        )
        if not has_simple_place and _race_due(day):
            data = _cached_get_json(
                _PMU_RAPPORTS_URL.format(day=day, reunion=reunion, circuit=circuit),
                rapports_path,
                refresh=True,
            )
        for typepari in data:
            if "E_SIMPLE_PLACE" in typepari["typePari"] or "SIMPLE_PLACE_INTERNATIONAL" in typepari["typePari"]:
                for rapport in typepari["rapports"]:
                    placedwinner = rapport["combinaison"][0]
                    dividende = (rapport["dividende"] * (config.TICKET_VALUE_CENTS / 100)) - config.TICKET_VALUE_CENTS
                    try:
                        horsetodividende[nametonumpmu[placedwinner]] = int(dividende)
                    except (KeyError, ValueError):
                        logger.debug("gagnant %s non résolu", placedwinner)
    except Exception as exc:
        logger.debug("rapports indisponibles %s (%s)", base_path, exc)

    # incidents → NON_PARTANT = dividende nul
    try:
        data = _cached_get_json(
            _PMU_INCIDENTS_URL.format(day=day, reunion=reunion, circuit=circuit),
            Path(str(base_path) + "incidents.json"),
        )
        for incidentsbytype in data["incidents"]:
            if "NON_PARTANT" in incidentsbytype["type"]:
                for numincident in incidentsbytype["numeroParticipants"]:
                    try:
                        horsetodividende[nametonumpmu[numincident]] = 0
                    except KeyError:
                        logger.debug("incident %s non résolu", numincident)
    except Exception as exc:
        logger.debug("incidents indisponibles %s (%s)", base_path, exc)

    return horsetodividende


def choose_course(response: dict) -> tuple[str, str]:
    """Choisit la course à jouer : écart maximal rel_prob[1] (cheval n°1 vs n°2).

    Même heuristique que le site (générateur de la page d'accueil).
    """
    max_ratio = 0
    second_max_ratio = 0
    max_ratio_delta = 0
    reunion_to_play = ""
    circuit_to_play = ""

    for reunion, circuits in response.items():
        for circuit, data in circuits.items():
            for horse in data["horses"]:
                if max_ratio < horse["rel_prob"][1]:
                    second_max_ratio = max_ratio
                    max_ratio = horse["rel_prob"][1]
            if max_ratio_delta < max_ratio - second_max_ratio:
                max_ratio_delta = max_ratio - second_max_ratio
                reunion_to_play = reunion
                circuit_to_play = circuit

    return reunion_to_play, circuit_to_play


def pick_horse(response: dict) -> tuple[dict, str, str]:
    """Choisit la course à jouer puis le cheval le plus qualitatif (prob[1] max)."""
    reunion_to_play, circuit_to_play = choose_course(response)
    horses = sorted(
        response[reunion_to_play][circuit_to_play]["horses"],
        key=lambda horse: horse["prob"][1],
        reverse=True,
    )
    return horses[0], reunion_to_play, circuit_to_play


def evaluate_day(datestr: str) -> DayResult | None:
    """Évalue la stratégie CRAZY BET pour un jour donné."""
    response_path = config.DATA_TEST_DIR / datestr / "response.json"
    if not response_path.is_file():
        return None
    try:
        response = json.load(open(response_path, encoding="utf-8"))
    except Exception as exc:
        logger.warning("response.json illisible pour %s (%s)", datestr, exc)
        return None

    date_dir = config.DATA_GAIN_DIR / datestr
    date_dir.mkdir(parents=True, exist_ok=True)

    horsetodividende: dict = {}
    for circuits in response.values():
        for data in circuits.values():
            horsetodividende.update(_race_outcome(data, date_dir))

    try:
        horse, reunionkey, circuitkey = pick_horse(response)
    except (IndexError, KeyError) as exc:
        logger.warning("Pas de cheval jouable pour %s (%s)", datestr, exc)
        return None

    race = response[reunionkey][circuitkey]
    url = race["url"]
    horse_label = f"{horse['numPmu_query']} - {horse['nom_query']}"
    link = f'<a href="{url}" target="_blank">{url}</a>'

    roi = 0
    row_html = ""
    if horse["nom_query"] in horsetodividende:
        # le cheval est arrivé → on empoche (ou non) le dividende du simple placé
        gain = horsetodividende[horse["nom_query"]]
        roi += gain
        row_html = f"<tr><td>{horse_label}</td><td>+{gain}</td><td>{link}</td></tr>"
    elif not horsetodividende:
        # aucun résultat connu → la course n'a jamais démarré
        row_html = f"<tr><td>{horse_label}</td><td>0</td><td>{link}</td></tr>"
    else:
        # le cheval a couru sans être placé → on perd le ticket (5 €), sauf si la
        # course n'a jamais démarré (remboursé, 0). Le signal « la course a
        # couru » = rapports définitifs de CETTE course (pas le texte des
        # pronostics : l'API les renvoie vides en HTTP 204 sur les anciennes
        # dates alors que la course a bien eu lieu — sinon on oublierait la perte).
        if _race_outcome(race, date_dir):
            roi -= config.TICKET_VALUE_CENTS
            row_html = f"<tr><td>{horse_label}</td><td>-{config.TICKET_VALUE_CENTS}</td><td>{link}</td></tr>"

    logger.info("%s: cheval %s → ROI %+d", datestr, horse_label, roi)
    return DayResult(date=datestr, roi=roi, row_html=row_html)


def evaluate_all() -> list[DayResult]:
    """Évalue tous les jours disposant d'un response.json (ordre chronologique)."""
    config.ensure_dirs()
    datedirs = sorted(
        (p.name for p in config.DATA_TEST_DIR.iterdir() if p.is_dir() and p.name.isdigit()),
        key=lambda date_str: datetime.strptime(date_str, "%d%m%Y"),
    )
    results = []
    for datestr in datedirs:
        result = evaluate_day(datestr)
        if result:
            results.append(result)
    return results
