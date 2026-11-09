FROM python:3.14-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.5.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Installation des dépendances système
# apt-get upgrade: security fixes not yet in the base image
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Up-to-date pip (the base image's pip vendors outdated urllib3/msgpack)
RUN pip install --no-cache-dir --upgrade pip

# Installation de Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="${POETRY_HOME}/bin:${PATH}"

# Répertoire de travail
WORKDIR /app

# Copie des fichiers Poetry
COPY pyproject.toml poetry.lock* ./

# Installation des dépendances
RUN poetry install --no-root

# Copie du projet
COPY . .

# Exposition du port Django
EXPOSE 80

# Commande par défaut
CMD ["python", "manage.py", "runserver", "0.0.0.0:80"]