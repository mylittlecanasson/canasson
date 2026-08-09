# 📘 Guide d'onboarding — Canasson

## 1. Vue d'ensemble du projet

**Canasson** est un système de prédiction hippique (PMU) : il collecte les données de course, entraîne un modèle d'apprentissage automatique, calcule le ROI d'une stratégie de jeu et génère un site statique publié sur GitHub Pages. Il s'agit de la reconstruction structurée et testée de l'ancienne application **Mylittlecanasson**, avec une philosophie d'implémentation identique mais une seule application propre, exécutable via un simple `docker compose up`.

- **Langages** : Python (principal), HTML, Dockerfile, YAML, TOML, JSON, Markdown
- **Frameworks** : Docker, Docker Compose, pytest
- **Pipeline** : `collect → predict → evaluate → site → publish`

## 2. Architecture — 9 couches

| Couche | Rôle | Fichiers clés |
|---|---|---|
| **Noyau & Orchestration** | CLI orchestrant tout le pipeline, API publique, config partagée | `cli.py`, `config.py`, `__init__.py` |
| **Collecte de données** | Ingestion API PMU + scraping Canalturf, sérialisé en CSV | `collect/pmu.py`, `collect/canalturf.py` |
| **Modèle & Prédiction** | Ingénierie de features + RandomForest | `model/features.py`, `model/predict.py` |
| **Évaluation & ROI** | Stratégie CRAZY BET, ROI journalier, artefacts | `evaluate/roi.py`, `bethistory.py`, `chart.py` |
| **Génération du site** | `index.html` + pages statiques par injection `{%MAINCASE%}` | `site/generate.py`, `templates/*.html` |
| **Publication** | Clone/push GitHub Pages, échecs gracieux | `publish/github.py` |
| **Tests** | Schéma, filtres, stratégie, templates (pytest) | `tests/*.py`, `fixtures/response.json` |
| **Infrastructure** | Conteneurisation + orchestration Compose | `Dockerfile`, `docker-compose.yml`, `.env.example` |
| **Configuration & Documentation** | Packaging, plugin, README | `pyproject.toml`, `README.md` |

## 3. Concepts clés

- **Stratégie « CRAZY BET »** — jouer le cheval le plus qualitatif de la course la plus sûre : la course est choisie sur l'écart maximal `rel_prob[1]` (cheval n°1 vs n°2) ; le cheval joué est celui au `prob[1]` maximal. Ticket de 5 € en simple placé.
- **Schéma `response.json`** — le contrat de données central : `{r1: {c5: {url, commentaire, total_prob, horses:[{nom, nom_query, numPmu_query, cribles, prob, rel_prob}]}}}`. Produit par `predict`, consommé par l'évaluation et le site, verrouillé par `test_schema.py`.
- **`rel_prob` / `total_prob`** — normalisation des probabilités par circuit : chaque cheval est rapporté à la somme des probabilités de sa course (`int(prob/somme*100)`).
- **Filtres d'apprentissage** — discipline `PLAT`, 8–12 partants déclarés, distance 1500–2100 m, **60 jours** d'historique, cible basée sur les places 1/2/3.
- **Sélection de features** — colonnes disposées en grille quasi-carrée (`get_factors`), corrélation à `ordreArrivee` ≥ corrélation de `nom`, exclusion de `paris_*` et `incident_*`.
- **Anti-fuite (data leakage)** — `load_query` supprime les résultats de la requête ; `load_train` prend une `ref_date` pour ne jamais apprendre sur le futur.
- **Injection par marqueur `{%MAINCASE%}`** — pas de moteur de templates : le gabarit contient un marqueur que le Python remplace par le contenu généré.
- **Publication gracieuse** — clone/push GitHub Pages enveloppés dans des `try/except` larges ; un échec loggue et laisse le pipeline continuer.
- **Repli « Archives »** — si les pronostics Canalturf manquent pour une date, le lien bascule sur les archives.

## 4. Visite guidée (12 étapes)

1. **Vue d'ensemble du projet** — `README.md` : philosophie, pipeline, stratégie.
2. **Point d'entrée CLI** — `cli.py` + `pyproject.toml` : console script `canasson.cli:main`, sous-commandes et orchestration.
3. **Configuration et initialisation** — `config.py` (fan-in maximal) + `__init__.py` : constantes métier et chemins.
4. **Collecte des données** — `pmu.py` (API PMU → CSV) et `canalturf.py` (scraping + cache local).
5. **Ingénierie de features** — `features.py` : filtres, encodage, corrélation, cible 1/2/3.
6. **Entraînement et prédiction** — `predict.py` : RandomForest sur 60 jours → `response.json`.
7. **Le contrat de données `response.json`** — `tests/fixtures/response.json` + `test_schema.py` : le schéma verrouillé par les tests.
8. **Stratégie de jeu et ROI** — `roi.py` : CRAZY BET, rapports réels PMU, `DayResult`.
9. **Artefacts d'évaluation** — `bethistory.py` (html) et `chart.py` (`candle.png`).
10. **Génération du site statique** — `generate.py` + `index_template.html` : top 7 jours, Chart.js, liens Canalturf.
11. **Publication GitHub Pages** — `github.py` : clone, copie, commit `comment from python script`, push gracieux.
12. **Infrastructure Docker** — `Dockerfile` + `docker-compose.yml` : image Python 3.11-slim, volumes, `canasson run`.

## 5. Carte des fichiers (par couche)

### Noyau & Orchestration

- **`canasson/cli.py`** — Point d'entrée CLI : sous-commandes `collect`, `predict`, `evaluate`, `site`, `publish`, `backfill`, `rerun`, `run` (pipeline complet lancé par `docker compose up`).
- **`canasson/config.py`** — Constantes métier (filtres, stratégie, endpoints PMU/Canalturf) et chemins pilotés par l'environnement, avec `ensure_dirs()`.
- **`canasson/__init__.py`** — Docstring projet + version 1.0.0.

### Collecte de données

- **`canasson/collect/pmu.py`** *(complex)* — API PMU : programme, participants, pronostics → `data_train/<date>.csv` et `data_test/<date>/query.csv` ; repli gracieux quand l'API throttle.
- **`canasson/collect/canalturf.py`** — Scraping archives canalturf.com (cache local `data_cturf/<date>/`) → `infos.json`.

### Modèle & Prédiction

- **`canasson/model/features.py`** — Filtres, encodage, grille de corrélation (`get_factors`), cible top3, anti-fuite. Porte fidèle de `process_final_v0.1.py`.
- **`canasson/model/predict.py`** *(complex)* — RandomForest sur 60 jours → `response.json` + `heatmap.png` + `confusionmatrix.png`.

### Évaluation & ROI

- **`canasson/evaluate/roi.py`** *(complex)* — ROI journalier CRAZY BET via rapports réels PMU, ticket 5 € simple placé, dataclass `DayResult`.
- **`canasson/evaluate/bethistory.py`** — `bethistory.html` par injection `{%MAINCASE%}`.
- **`canasson/evaluate/chart.py`** — `candle.png` : chandelier par jour (vert/rouge) + courbe ROI cumulé.

### Génération du site

- **`canasson/site/generate.py`** — `index.html` : top 7 jours, écart maximal `rel_prob[1]`, Chart.js, liens Canalturf.
- **`templates/`** — `index_template.html` (fonction `drawBarChart`), `bethistory-template.html`, `about.html`, `race.html`, `contact.html`.

### Publication

- **`canasson/publish/github.py`** — Clone du dépôt GitHub Pages, copie des artefacts, commit `comment from python script`, push gracieux.

### Infrastructure

- **`Dockerfile`** — `python:3.11-slim` + git + openssh-client ; `ENTRYPOINT canasson` / `CMD run`.
- **`docker-compose.yml`** — volume `./data`, SSH en lecture seule, `GIT_REPO_URL`, exécution puis arrêt propre.
- **`.env.example`** — `GIT_REPO_URL`, `CANASSON_DATA_DIR`, `SSH_DIR`.

### Tests

- **`tests/conftest.py`** — fixture de session `response` chargeant `fixtures/response.json`.
- **`tests/test_schema.py`** — structure et cohérence numérique de `response.json`.
- **`tests/test_filters.py`** — `get_factors`, filtres PLAT/partants/distance, cible, anti-fuite.
- **`tests/test_strategy.py`** — sélection maxRatioDelta, cheval qualitatif, ROI.
- **`tests/test_template.py`** — `{%MAINCASE%}`, liens Canalturf, bloc HTML d'un jour.

### Configuration & Documentation

- **`pyproject.toml`** — packaging, dépendances (pandas, scikit-learn, matplotlib, seaborn, requests, beautifulsoup4, GitPython), console script.
- **`README.md`** — philosophie, pipeline, CLI, backtest, déploiement.

## 6. Zones de complexité (à aborder prudemment)

Trois modules sont marqués **complex** et concentrent la logique métier à maîtriser en premier :

| Module | Pourquoi c'est complexe |
|---|---|
| **`collect/pmu.py`** | Normalisation du JSON PMU, structure de données imbriquée, gestion du throttling et des replis gracieux. |
| **`model/predict.py`** | Pipeline complet d'entraînement + inférence, normalisation par circuit, génération des artefacts. |
| **`evaluate/roi.py`** | Stratégie de jeu, agrégation des rapports réels PMU, calcul du ROI et dataclass `DayResult`. |

Le reste du projet est **moderate/simple** (11 fichiers moderate, le reste simple) — l'estimation globale est **moderate**. `config.py` est le nœud le plus importé (fan-in maximal) : tout part de là.

---

📌 **Prêt à démarrer** : `docker compose up` (pipeline complet), ou `canasson run --no-publish` pour tester sans pousser. Pour les tests : `python -m pip install -e '.[test]' && python -m pytest`.
