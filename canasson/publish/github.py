"""Publication des artefacts sur mylittlecanasson.github.io.

Port consolidé de `winrate_mylittlecanasson.py` et de `web/app/app.py` : on
clone le dépôt GitHub Pages dans `generated`, on copie l'ensemble des
artefacts (index, bethistory, candle, pages annexes) puis on commite avec le
message historique « comment from python script » et on pousse. Tout échec
(clone, commit, push) est **gracieux** : on loggue et on continue sans faire
planter le pipeline — c'est le comportement des applications d'origine.
"""
from __future__ import annotations

import logging
import shutil

from git import Repo
from git.exc import GitError

from canasson import config

logger = logging.getLogger("canasson.publish.github")


def _copy_artifacts() -> None:
    """Copie les artefacts générés dans le worktree du dépôt GitHub Pages."""
    shutil.copyfile(config.ARTIFACT_INDEX, config.WORKTREE_DIR / "index.html")
    shutil.copyfile(config.ARTIFACT_BETHISTORY, config.WORKTREE_DIR / "bethistory.html")
    shutil.copyfile(config.ARTIFACT_CANDLE, config.WORKTREE_DIR / "candle.png")

    # Pages annexes du site (copiées verbatim depuis les templates).
    for page in ("about.html", "race.html", "contact.html"):
        shutil.copyfile(config.TEMPLATES_DIR / page, config.WORKTREE_DIR / page)


def _git_push() -> None:
    """Commit « comment from python script » et push de tous les changements."""
    repo = Repo(config.WORKTREE_DIR)
    repo.git.add("--all")
    repo.index.commit(config.COMMIT_MESSAGE)
    repo.remote("origin").push()
    logger.info("Changements poussés sur %s.", config.GIT_REPO_URL)


def run(no_push: bool = False) -> None:
    """Clone le dépôt GitHub Pages, copie les artefacts, commit et pousse.

    `no_push` simule la publication (copie locale) sans toucher au dépôt
    distant — utile pour tester sans clé SSH.
    """
    config.ensure_dirs()
    shutil.rmtree(config.WORKTREE_DIR, ignore_errors=True)

    try:
        Repo.clone_from(config.GIT_REPO_URL, config.WORKTREE_DIR)
    except GitError as exc:
        # Skip gracieux : pas de clé SSH ou dépôt indisponible — on continue.
        logger.warning("Clone du dépôt GitHub Pages impossible, publication ignorée (%s).", exc)
        return

    try:
        _copy_artifacts()
    except OSError as exc:
        logger.warning("Artefacts manquants, publication ignorée (%s).", exc)
        return

    if no_push:
        logger.info("--no-push : artefacts copiés dans %s, push ignoré.", config.WORKTREE_DIR)
        return

    try:
        _git_push()
    except GitError as exc:
        # Le push est une vraie action qui échoue : c'est une erreur, pas un skip.
        logger.error("Échec du push vers %s : %s", config.GIT_REPO_URL, exc)
