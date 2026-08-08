"""Scraping des liens pronostics / résultats sur canalturf.com.

Port fidèle de `shortcut_canalturf.py` : pour chaque jour (demain → 59
jours en arrière), la page d'archives est récupérée (avec cache local dans
`data_cturf/<date>/infos.html`) et les liens « Pronos » / « Résultats »
de chaque course sont extraits dans `data_cturf/<date>/infos.json`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from canasson import config

logger = logging.getLogger("canasson.collect.canalturf")


def _parse_archive(page_html: str) -> dict:
    """Extrait, pour chaque réunion (rX) et course (cY), les liens canalturf."""
    output_json = {}
    soup = BeautifulSoup(page_html, "html.parser")

    for panel in soup.find_all("div", class_="panel panel-bordered panel-dark"):
        reunion = panel.find_all("span", class_="text-lg")
        if not reunion:
            continue
        formatreunion = "r" + re.findall(r"\d+", reunion[0].text)[-1]

        for row in panel.find_all("li", class_="list-group-item list-item-sm text-overflow"):
            circuit = row.find_all("span", class_="badge")
            pronos = row.find_all("a", class_="btn btn-sm btn-primary mar-btm")
            resultats = row.find_all("a", class_="btn btn-sm btn-danger")
            if not (circuit and pronos and resultats):
                continue

            formatcircuit = "c" + circuit[0].text
            output_json.setdefault(formatreunion, {}).setdefault(formatcircuit, {}).update(
                {"pronos": pronos[0].get("href"), "resultats": resultats[0].get("href")}
            )

    return output_json


def run() -> None:
    """Scrape les archives canalturf (demain → 59 jours en arrière)."""
    config.ensure_dirs()
    for i in range(-1, 60):
        day = date.today() - timedelta(days=i)
        rawdate = day.strftime("%d%m%Y")

        day_dir = config.DATA_CTURF_DIR / rawdate
        day_dir.mkdir(parents=True, exist_ok=True)

        # cache HTML local (un seul téléchargement par jour)
        infos_html = day_dir / "infos.html"
        if infos_html.exists():
            logger.debug("%s cached", rawdate)
            page = infos_html.read_text(encoding="utf-8", errors="replace")
        else:
            logger.info("canalturf %s remote", rawdate)
            url = config.CANALTURF_ARCHIVES_URL.format(iso_date=day.isoformat())
            try:
                page = requests.get(url).text
            except requests.RequestException as exc:
                logger.warning("canalturf indisponible pour %s (%s)", rawdate, exc)
                page = ""
            infos_html.write_text(page, encoding="utf-8")

        output_json = _parse_archive(page)
        with open(day_dir / "infos.json", "w", encoding="utf-8") as handle:
            json.dump(output_json, handle, ensure_ascii=False, indent=4)
