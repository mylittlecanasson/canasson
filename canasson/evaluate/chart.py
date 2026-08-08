"""Génération de candle.png : chandeliers journaliers + courbe du ROI cumulé.

Port fidèle de la section « candle » de `winrate_mylittlecanasson.py` :
chaque jour est une chandelle verte (gain) ou rouge (perte) sur la base d'un
ticket de 5 €, la courbe illustrant l'accumulation des gains.
"""
from __future__ import annotations

import logging
from itertools import accumulate

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from canasson import config
from canasson.evaluate.roi import DayResult

logger = logging.getLogger("canasson.evaluate.chart")


def render(results: list[DayResult]) -> None:
    """Trace candle.png dans data_test à partir des ROI journaliers."""
    mycurrentroi = {result.date: result.roi for result in results}
    if not mycurrentroi:
        logger.warning("Aucun ROI à tracer.")
        return

    acc_prices = list(accumulate(mycurrentroi.values()))
    prices = pd.DataFrame(
        {
            "open": [0] * len(mycurrentroi),
            "close": list(mycurrentroi.values()),
            "high": list(mycurrentroi.values()),
            "low": [0] * len(mycurrentroi),
        },
        index=list(mycurrentroi.keys()),
    )

    width = 0.4
    width2 = 0.05
    up = prices[prices["close"] >= prices["open"]]
    down = prices[prices["close"] < prices["open"]]

    _, ax = plt.subplots(figsize=(12, 9))
    ax.plot(mycurrentroi.keys(), acc_prices)
    ax.set_title(
        f"From {config.TICKET_VALUE_CENTS / 100}€ to {acc_prices[-1] / 100}€ "
        f"(ROI= x{acc_prices[-1] / config.TICKET_VALUE_CENTS})"
    )

    ax.bar(up.index, up["close"] - up["open"], width, bottom=up["open"], color="green")
    ax.bar(up.index, up["high"] - up["close"], width2, bottom=up["close"], color="green")
    ax.bar(up.index, up["low"] - up["open"], width2, bottom=up["open"], color="green")

    ax.bar(down.index, down["close"] - down["open"], width, bottom=down["open"], color="red")
    ax.bar(down.index, down["high"] - down["open"], width2, bottom=down["open"], color="red")
    ax.bar(down.index, down["low"] - down["close"], width2, bottom=down["close"], color="red")

    plt.xticks(rotation=45, ha="right")

    config.ARTIFACT_CANDLE.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(config.ARTIFACT_CANDLE, bbox_inches="tight")
    plt.close()
    logger.info("candle.png écrit.")
