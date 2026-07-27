# ============================================================
# STAGE 1 : Builder — dépendances Python + assets
# ============================================================
FROM python:3.14-slim AS builder

WORKDIR /app

# Dépendances système pour psycopg2, Pillow, reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le code source (hors .dockerignore)
COPY . .

# Build Tailwind CSS via pytailwindcss (pas de Node.js requis)
RUN python -m pytailwindcss -i theme/static_src/src/styles.css -o theme/static/css/output.css --minify 2>/dev/null \
    || echo "⚠️  Tailwind build via pytailwindcss ignoré"

# Collecte des fichiers statiques
RUN python manage.py collectstatic --noinput --clear 2>/dev/null \
    || echo "⚠️  collectstatic ignoré"

# ============================================================
# STAGE 2 : Runtime — image légère pour la production
# ============================================================
FROM python:3.14-slim

WORKDIR /app

# Librairies runtime uniquement (pas gcc, pas node)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copier les packages Python depuis le builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copier le projet
COPY --from=builder /app /app

# Variables d'environnement production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=hotel_project.settings \
    DEBUG=False \
    PORT=8000

EXPOSE 8000

# Sauvegarde de la base SQLite trackée (restaurée par entrypoint si volume vide)
RUN if [ -f db.sqlite3 ]; then cp db.sqlite3 db.sqlite3.bak; fi

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
