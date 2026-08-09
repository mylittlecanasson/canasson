# Canasson

Système de prédiction hippique (PMU) reconstruit proprement à partir de la
vieille application **Mylittlecanasson**. Même philosophie d'implémentation,
même stratégie de jeu, même site — mais une seule application, structurée,
testée, qui s'exécute avec un simple `docker compose up`.

## Philosophie préservée (inchangée)

La logique métier de l'application d'origine est conservée à l'identique :

- **Stratégie « CRAZY BET »** — jouer le cheval le plus qualitatif de la
  course la plus sûre : la course est choisie sur l'écart maximal de
  `rel_prob[1]` (cheval n°1 vs n°2), le cheval joué est celui au `prob[1]`
  maximal. Ticket de 5 € en simple placé.
- **Schéma `response.json`** — `{r1: {c5: {url, commentaire, total_prob,
  horses:[{nom, nom_query, numPmu_query, cribles, prob, rel_prob}]}}}`.
- **Filtres d'apprentissage** — discipline `PLAT`, 8-12 partants déclarés,
  1500-2100 m, 60 jours d'apprentissage, cible basée sur les places 1/2/3.
- **Sélection de features** — colonnes disposées en grille quasi-carrée
  (`getFactors`), corrélation à `ordreArrivee` ≥ corrélation de `nom`,
  exclusion de `paris_*` et `incident_*`.
- **Génération du site** — HTML statique + Simple.css + Chart.js, injection
  par le marqueur `{%MAINCASE%}`, liens canalturf avec repli « Archives »,
  cheval gagnant et ses cribles, bannières « jeu responsable ».
- **Publication** — clone du dépôt GitHub Pages, copie des artefacts, commit
  `comment from python script`, push. Tout échec est gracieux (le pipeline
  continue sans publication).

## Pipeline

```
collect ──► predict ──► evaluate ──► site ──► publish
  │            │            │           │          │
  PMU +      filtres,     ROI          index.html   clone github.io
  canalturf  RandomForest bethistory   (7 derniers  + push
  ─► data_   ─► response  candle.png    jours)      (gracieux)
    train     .json
```

1. **collect** — API PMU → `data_train/<date>.csv` (60 jours) +
   `data_test/<demain>/query.csv` ; scrape canalturf →
   `data_cturf/<date>/infos.json`.
2. **predict** — filtres, encodage, sélection de features, RandomForest →
   `data_test/<date>/response.json` + `heatmap.png` + `confusionmatrix.png`.
3. **evaluate** — ROI réel via l'API PMU (dividendes du simple placé) →
   `data_test/bethistory.html` + `data_test/candle.png`.
4. **site** — page d'accueil `index.html` (top 7 jours).
5. **publish** — pousse les artefacts sur `mylittlecanasson.github.io`.

## Démarrage rapide

```bash
docker compose up
```

Le conteneur exécute le pipeline complet **une fois** puis s'arrête
proprement. Les données et artefacts sont dans `./data/` (volume monté).

- **Sans publication** : `docker compose run --rm canasson run --no-publish`
  (ou ne pas monter de clé SSH — le push est alors ignoré gracieusement).
- **Avec publication** : monter `~/.ssh` (clé de déploiement GitHub Pages) via
  `SSH_DIR` — voir `.env.example`.

## CLI

```bash
canasson run [--no-publish] [DATE]   # pipeline complet (défaut : docker compose up)
canasson collect                     # données PMU + canalturf
canasson predict [DATE]              # entraînement + prédiction (défaut : demain)
canasson evaluate                    # ROI + bethistory.html + candle.png
canasson site                        # régénère index.html
canasson publish [--no-push]         # publication GitHub Pages
canasson rerun DATE                  # rejoue une date puis recalcule le ROI
canasson backfill [N]                # backtest : prédit les N derniers jours (défaut : 30)
```

## Configuration des réglages

Certains paramètres sont éditables avant le lancement via un **dashboard web** :
fenêtre d'apprentissage, discipline, bornes de partants et de distance, cible
des places, mise, jours affichés à l'accueil. Les **défauts sont les constantes
d'origine** : sans fichier sauvegardé, le pipeline fonctionne exactement comme
avant — aucune erreur « no configuration ».

### Dashboard

```bash
docker compose --profile tools up config
```

Ouvrez **http://localhost:8090**, ajustez les valeurs puis **Enregistrer** — la
configuration est sauvegardée dans `./data/config.json`. Le bouton
« Restaurer les défauts » supprime le fichier. Le service est masqué du
`docker compose up` par le profil `tools` : le pipeline « une fois puis arrêt »
reste inchangé.

### Lancer avec la configuration sauvegardée

```bash
docker compose run --rm canasson run
```

Toute sous-commande (`collect`, `predict`, `evaluate`, `site`, `backfill`…)
applique la configuration sauvegardée au démarrage. Chaque prédiction mémorise
la config utilisée dans `data_test/<date>/config.json`.

### Provenance sur le site publié

Le site (mylittlecanasson.github.io) affiche sur `index.html` et
`bethistory.html` une **petite boîte cliquable** « ⚙️ Config : … » résumant la
configuration dont proviennent les résultats (fenêtre, discipline, partants,
distance, cible, mise, jours) — dépliée au clic. Elle reflète la config du jour
le plus récent affiché (snapshot écrit au moment de la prédiction).

## Développement

```bash
python -m pip install -e '.[test]'
python -m pytest
```

## Analyse du code — Understand-Anything

Le plugin **Understand-Anything** analyse le dépôt et produit un **graphe de
connaissances** du code (structure, imports, couches d'architecture, flux
métier), explorable via un dashboard interactif. Les artefacts sont générés
dans `.ua/` (versionné) :

- `knowledge-graph.json` — graphe complet : 111 nœuds (fichiers, fonctions,
  classes, configs, services), 279 arêtes (imports, appels, dépendances,
  tests), 9 couches d'architecture et une visite guidée en 12 étapes.
- `domain-graph.json` — graphe du domaine métier : 5 domaines, 9 flux
  (collecte, prédiction, évaluation, site, publication), 45 étapes.
- `meta.json` / `fingerprints.json` — métadonnées d'analyse et empreintes
  structurelles (permettent les mises à jour incrémentales automatiques).
- `.understandignore` — motifs exclus de l'analyse ; `config.json` — langue
  de sortie des contenus générés (fr).

Commandes (depuis la racine du projet, dans Claude Code) :

```bash
/understand-anything:understand            # analyse complète → knowledge-graph.json
/understand-anything:understand-domain     # domaine métier → domain-graph.json
/understand-anything:understand-onboard    # guide d'onboarding → docs/ONBOARDING.md
/understand-anything:understand-dashboard  # dashboard interactif local
```

Le dashboard démarre en local (serveur Vite) et s'ouvre sur une URL avec
token d'accès ; il détecte automatiquement `domain-graph.json` pour afficher
la vue métier. Rejouer `/understand-anything:understand` après une
modification met à jour le graphe de façon incrémentale.

## Structure

```
canasson/
├── canasson/
│   ├── cli.py          # point d'entrée (console script `canasson`)
│   ├── config.py       # constantes métier + chemins pilotés par l'environnement
│   ├── collect/        # pmu.py (API PMU), canalturf.py (scraper)
│   ├── model/          # features.py (filtres + corrélation), predict.py (RandomForest)
│   ├── evaluate/       # roi.py (CRAZY BET), bethistory.py, chart.py (candle.png)
│   ├── site/           # generate.py (index.html) + templates/ (verbatim)
│   └── publish/        # github.py (clone + commit + push, skip gracieux)
├── data/               # runtime (VOLUME, gitignoré)
└── tests/              # stratégie, schéma, templates, filtres
```

## Déploiement

1. Copier `.env.example` → `.env` et renseigner `GIT_REPO_URL` (défaut :
   `git@github.com:mylittlecanasson/mylittlecanasson.github.io.git`) et
   `SSH_DIR` (défaut : `~/.ssh`, la clé de déploiement).
2. `docker compose up` — le site `mylittlecanasson.github.io` est mis à jour.

## Changements volontaires (hors philosophie)

- Publication consolidée en **une seule étape** (l'originale en faisait deux,
  moteur puis site, en parallèle). Message de commit et résultat identiques.
- `canasson predict <date>` prédit **exactement** cette date (l'ancienne
  application ajoutait un jour à la date fournie).
- Python moderne (3.11), TensorFlow abandonné (jamais importé par l'original) ;
  la logique ML est un RandomForest scikit-learn identique.
- Robustesse : l'API PMU throttle sporadiquement (HTTP 420) — la collecte
  réessaie (3 tentatives avec backoff) puis **ignore le jour** au lieu de
  faire planter tout le pipeline ; canalturf est ignoré gracieusement en cas
  de panne réseau (le site replie alors sur « Archives »).
- **Backtest sans fuite d'information** : `canasson backfill [N]` prédit les N
  derniers jours. Pour chaque date passée, l'apprentissage n'utilise que les
  données disponibles **au moment** de la prédiction (`load_train(ref_date)`
  charge `[date-60, date-1]`) — jamais les jours postérieurs. L'historique
  d'apprentissage est étendu en conséquence (`60 + N` jours de collecte).
- **URL API PMU** : `programme/{jour}` **sans slash final** (un slash de fin
  fait répondre l'API en HTTP 420). Les sous-URL par course (`/R{r}/C{c}/…`)
  sont inchangées.
