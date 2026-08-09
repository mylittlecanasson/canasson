"""Génération de la page d'accueil index.html.

Port fidèle de `web/app/app.py` : pour les 7 derniers jours disposant d'un
`response.json`, la course à jouer est choisie sur l'écart de `rel_prob[1]`
maximal, puis la page affiche le graphique Chart.js, les liens canalturf (ou
les archives), le commentaire et le cheval gagnant. L'ensemble est injecté
dans `index_template.html` via le marqueur `{%MAINCASE%}`.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from canasson import config
from canasson.evaluate.roi import choose_course

logger = logging.getLogger("canasson.site.generate")


def _cturf_link(data_infos: dict, reunion: str, circuit: str, date_str: str) -> str:
    """Liens canalturf pronostics/résultats, ou lien archives si indisponible."""
    if reunion in data_infos and circuit in data_infos[reunion]:
        return (
            f'<a href="{data_infos[reunion][circuit]["pronos"]}" target="_blank" '
            f'title="Le pronostic de la course">Pronos</a> -- '
            f'<a href="{data_infos[reunion][circuit]["resultats"]}" target="_blank" '
            f'title="Les résultats de la course">Résultats</a>'
        )
    iso_date = f"{date_str[4:8]}-{date_str[2:4]}-{date_str[0:2]}"
    return (
        f'<a href="https://www.canalturf.com/courses_archives.php?date={iso_date}" '
        f'target="_blank" title="Archives des courses">-- Archives --</a>'
    )


def _article(date_str: str, data: dict, data_infos: dict) -> str:
    """Construit le bloc HTML d'un jour (titre, course, graphique, cheval gagnant)."""
    chosen = choose_course(data)
    if not chosen[0]:
        return ""
    reunion, circuit = chosen
    race = data[reunion][circuit]

    cturf_link = _cturf_link(data_infos, reunion, circuit, date_str)
    commentaire = str(race.get("commentaire", "Sans commentaire"))
    url = str(race["url"])

    article = f'<h2 class="post-link">{date_str}</a></h2>'
    article += f'<div><a href="{url}" target="_blank"><b>{reunion}{circuit}</b></a>: {commentaire}<br>{cturf_link}'

    x_values, y_values, bar_colors = [], [], []
    max_ratio = 0
    for horse in race["horses"]:
        x_values.append(horse["numPmu_query"])
        y_values.append(horse["rel_prob"][1])
        max_ratio = max(max_ratio, horse["rel_prob"][1])

    best_horse = None
    for horse in race["horses"]:
        if max_ratio == horse["rel_prob"][1]:
            best_horse = horse
            bar_colors.append("green")
        else:
            bar_colors.append("grey")

    chart_id = f"{date_str}{reunion}{circuit}Chart"
    article += (
        f'<div><canvas id="{chart_id}" style="width:100%;max-width:600px"></canvas>'
        f"<script>"
        f"var xValues = {str(x_values)}; "
        f"var yValues = {str(y_values)}; "
        f"var barColors = {str(bar_colors)}; "
        f'drawBarChart("{chart_id}", "Pronostics IA Canasson", xValues, yValues, barColors)'
        f"</script></div>"
    )

    if best_horse and "cribles" in best_horse:
        article += f"<div><b>{best_horse['nom_query']} ({best_horse['numPmu_query']})</b> - {best_horse['cribles']}</div>"
    else:
        article += "<div>Sans commentaire</div>"

    return article + "</div>"


def run() -> None:
    """Régénère index.html avec les 7 derniers jours de pronostics."""
    config.ensure_dirs()
    datedirs = sorted(
        (p.name for p in config.DATA_TEST_DIR.iterdir() if p.is_dir() and p.name.isdigit()),
        key=lambda date_str: datetime.strptime(date_str, "%d%m%Y"),
        reverse=True,
    )

    main_article = ""
    latest_displayed = None  # date la plus récente réellement affichée (provenance)
    for date_str in datedirs[: config.HISTORY_DAYS_SITE]:
        try:
            data = json.load(open(config.DATA_TEST_DIR / date_str / "response.json", encoding="utf-8"))
        except Exception as exc:
            logger.warning("Impossible de charger %s (%s)", date_str, exc)
            continue

        data_infos = {}
        infos_path = config.DATA_CTURF_DIR / date_str / "infos.json"
        if infos_path.is_file():
            try:
                data_infos = json.load(open(infos_path, encoding="utf-8"))
            except Exception as exc:
                logger.debug("Pas d'infos canalturf pour %s (%s)", date_str, exc)

        article = _article(date_str, data, data_infos)
        if article:
            latest_displayed = date_str
        main_article += article

    # Provenance : config du jour le plus récent affiché (snapshot du predict),
    # sinon réglages courants — jamais d'erreur « no configuration ».
    settings = config.settings_for_date(latest_displayed) if latest_displayed else config.current_settings()
    badge = config.config_badge_html(settings)

    index_html = (
        config.TEMPLATES_DIR / "index_template.html"
    ).read_text(encoding="utf-8").replace("{%CONFIGCASE%}", badge).replace("{%MAINCASE%}", main_article)

    config.ARTIFACT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    config.ARTIFACT_INDEX.write_text(index_html, encoding="utf-8")
    logger.info("index.html écrit (%d jour(s)).", len(main_article) and len(datedirs[: config.HISTORY_DAYS_SITE]))
