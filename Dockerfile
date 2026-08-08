# Canasson — image d'exécution du pipeline (collecte, ML, ROI, site, publication).
# Python moderne (l'app d'origine tournait sur 3.7 sans jamais importer TensorFlow :
# la logique ML est un RandomForest scikit-learn, ici scikit-learn moderne).
FROM python:3.11-slim

# git + openssh-client : nécessaires au clone/push du dépôt GitHub Pages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY canasson/ ./canasson/
RUN pip install --no-cache-dir .

ENTRYPOINT ["canasson"]
CMD ["run"]
