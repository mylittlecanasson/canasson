"""Évaluation des prédictions : ROI (CRAZY BET), bethistory.html et candle.png."""
from __future__ import annotations

import logging

from canasson.evaluate import bethistory, chart, roi

logger = logging.getLogger("canasson.evaluate")


def run() -> None:
    """Calcule le ROI de chaque jour, puis régénère bethistory.html et candle.png."""
    results = roi.evaluate_all()
    bethistory.render(results)
    chart.render(results)
    logger.info("Évaluation terminée : %d jour(s) analysé(s).", len(results))
