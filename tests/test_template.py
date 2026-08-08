"""Tests des templates HTML et de l'injection {%MAINCASE%} (philosophie d'origine)."""
from __future__ import annotations

from canasson import config
from canasson.site.generate import _article, _cturf_link

MARKER = "{%MAINCASE%}"


def test_templates_contain_marker() -> None:
    """Les deux templates de page conservent le marqueur d'injection."""
    assert MARKER in (config.TEMPLATES_DIR / "index_template.html").read_text(encoding="utf-8")
    assert MARKER in (config.TEMPLATES_DIR / "bethistory-template.html").read_text(encoding="utf-8")


def test_cturf_links_present() -> None:
    """Liens pronostics/résultats construits depuis data_infos."""
    data_infos = {"r2": {"c7": {"pronos": "https://p", "resultats": "https://r"}}}
    link = _cturf_link(data_infos, "r2", "c7", "01012025")
    assert "https://p" in link
    assert "https://r" in link
    assert "Archives" not in link


def test_cturf_archives_fallback() -> None:
    """Sans infos canalturf, lien archives au format ISO (2025-01-01)."""
    link = _cturf_link({}, "r2", "c7", "01012025")
    assert "courses_archives.php?date=2025-01-01" in link


def test_article_builds_chart_and_winner(response: dict) -> None:
    """Le bloc HTML d'un jour contient la course choisie et le graphique Chart.js."""
    article = _article("01012025", response, {})
    assert "<h2 class=\"post-link\">01012025" in article
    assert "r2c7" in article
    assert 'drawBarChart("01012025r2c7Chart"' in article
    assert "GAMMA (1)" in article  # cheval gagnant (rel_prob[1] maximal)
    assert "qualitatif" in article  # cribles du cheval gagnant
    assert MARKER not in article
