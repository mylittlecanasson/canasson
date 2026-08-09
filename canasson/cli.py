"""Point d'entrée CLI de Canasson.

`canasson run` exécute le pipeline complet — collecte, prédiction, ROI,
site, publication — c'est ce que lance `docker compose up`.
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings

from canasson import __version__, config
from canasson import config_ui
from canasson.collect import canalturf, pmu
from canasson.evaluate import run as evaluate_run
from canasson.model import predict
from canasson.publish import github as publish
from canasson.site import generate

logger = logging.getLogger("canasson.cli")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Bruit des dépendances inutile au niveau INFO (fontes matplotlib, urllib3,
    # PIL…) : la signalétique utile provient de canasson.*.
    for noisy_logger in ("matplotlib", "urllib3", "PIL", "numba", "h5py"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    # DtypeWarning pandas (colonnes à types mixtes) : normal sur les CSV PMU,
    # `load_train` lit en low_memory=False et coerce déjà — on masque le bruit.
    warnings.filterwarnings("ignore", message=".*mixed types.*")


def cmd_collect(args: argparse.Namespace) -> int:
    """Collecte les données PMU (60 jours d'apprentissage + demain) et canalturf."""
    pmu.run()
    canalturf.run()
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    """Entraîne le modèle et prédit la probabilité de chaque cheval."""
    predict.run(date_str=args.date)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Calcule le ROI (stratégie CRAZY BET) et régénère bethistory.html + candle.png."""
    evaluate_run()
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    """Régénère la page d'accueil index.html (top 7 jours, course à jouer)."""
    generate.run()
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    """Clone mylittlecanasson.github.io, copie les artefacts et pousse."""
    publish.run(no_push=args.no_push)
    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    """Backtest des `n` derniers jours : prédit chaque jour passé en n'utilisant
    que les données disponibles au moment de la prédiction (pas de fuite)."""
    from datetime import date, timedelta

    # étend l'historique d'apprentissage : le plus vieux jour prédit a besoin
    # de 60 jours de données avant lui (le téléchargement saute l'existant).
    pmu.download_data("train", config.TRAIN_DAYS + args.days, 1)

    for offset in range(args.days, 0, -1):
        datestr = (date.today() - timedelta(days=offset)).strftime("%d%m%Y")
        pmu.download_query(datestr)
        try:
            predict.run(date_str=datestr)
            logger.info("backfill %s : prédiction OK", datestr)
        except Exception as exc:
            logger.warning("backfill %s : échec (%s)", datestr, exc)
    return 0


def cmd_rerun(args: argparse.Namespace) -> int:
    """Rejoue la prédiction d'une date passée puis recalcule le ROI (ancien rerunall.sh)."""
    predict.run(date_str=args.date)
    evaluate_run()
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Dashboard web de configuration des réglages (bloquant, Ctrl+C pour arrêter)."""
    config_ui.run(host=args.host, port=args.port)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Pipeline complet : collect → predict → evaluate → site → publish."""
    pmu.run()
    canalturf.run()
    predict.run(date_str=args.date)
    evaluate_run()
    generate.run()
    if not args.no_publish:
        publish.run(no_push=False)
    else:
        logger.info("Publication ignorée (--no-publish).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canasson",
        description="Système de prédiction hippique PMU — collecte, ML, ROI et site statique.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="journal détaillé")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("collect", help="collecte des données PMU et canalturf")
    sub.add_parser("evaluate", help="calcul du ROI + bethistory.html + candle.png")
    sub.add_parser("site", help="génération de la page d'accueil index.html")

    p_predict = sub.add_parser("predict", help="entraînement + prédiction du modèle")
    p_predict.add_argument("date", nargs="?", default=None,
                           help="date cible au format DDMMYYYY (défaut : demain)")

    p_publish = sub.add_parser("publish", help="publication des artefacts sur GitHub Pages")
    p_publish.add_argument("--no-push", action="store_true",
                           help="clone + copie sans pousser")

    p_backfill = sub.add_parser("backfill", help="backtest : prédit les N derniers jours")
    p_backfill.add_argument("days", nargs="?", type=int, default=30,
                            help="nombre de jours passés à prédire (défaut : 30)")

    p_rerun = sub.add_parser("rerun", help="rejoue une date puis recalcule le ROI")
    p_rerun.add_argument("date", help="date au format DDMMYYYY")

    p_run = sub.add_parser("run", help="pipeline complet (défaut : docker compose up)")
    p_run.add_argument("--no-publish", action="store_true",
                       help="exécute le pipeline sans pousser sur GitHub Pages")
    p_run.add_argument("date", nargs="?", default=None,
                       help="date cible de prédiction au format DDMMYYYY (défaut : demain)")

    p_config = sub.add_parser("config", help="dashboard web de configuration des réglages")
    p_config.add_argument("--host", default="0.0.0.0",
                          help="adresse d'écoute (défaut : 0.0.0.0)")
    p_config.add_argument("--port", type=int, default=8090,
                          help="port d'écoute (défaut : 8090)")

    return parser


_COMMANDS = {
    "collect": cmd_collect,
    "predict": cmd_predict,
    "evaluate": cmd_evaluate,
    "site": cmd_site,
    "publish": cmd_publish,
    "rerun": cmd_rerun,
    "backfill": cmd_backfill,
    "run": cmd_run,
    "config": cmd_config,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)
    # Applique la configuration sauvegardée (défauts si aucun fichier) avant
    # toute commande : collect, predict, evaluate, site, run… utilisent la
    # fenêtre/les filtres configurés via le dashboard.
    config.load_settings()
    try:
        return _COMMANDS[args.command](args)
    except KeyboardInterrupt:
        logger.warning("Interruption.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
