"""Génération de bethistory.html depuis les résultats du ROI.

Le tableau (chevaux joués, gains, URL des circuits) et le graphique candle
sont injectés dans le template `bethistory-template.html` via le marqueur
`{%MAINCASE%}` (philosophie d'injection de l'application d'origine).
"""
from __future__ import annotations

import logging

from canasson import config
from canasson.evaluate.roi import DayResult

logger = logging.getLogger("canasson.evaluate.bethistory")


def render(results: list[DayResult]) -> None:
    """Remplit le template et écrit data_test/bethistory.html (plus récent en premier)."""
    rows = "".join(result.row_html for result in reversed(results))
    maincase = '<table><tr><td>Chevaux joués</td><td>Gains</td><td>URL Circuits</td></tr>'
    maincase += rows + "</table>"
    maincase = '<img src="/candle.png" alt="candle chart"/>' + maincase

    template = config.TEMPLATES_DIR / "bethistory-template.html"
    html = template.read_text(encoding="utf-8").replace("{%MAINCASE%}", maincase)

    config.ARTIFACT_BETHISTORY.parent.mkdir(parents=True, exist_ok=True)
    config.ARTIFACT_BETHISTORY.write_text(html, encoding="utf-8")
    logger.info("bethistory.html écrit (%d jour(s)).", len(results))
