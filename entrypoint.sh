#!/bin/bash
set -e

# Détection du moteur de base de données
DB_URL="${DATABASE_URL:-}"
if echo "$DB_URL" | grep -qi "^postgres"; then
    echo "⏳ Attente de PostgreSQL..."
    for i in $(seq 1 30); do
        if python -c "import psycopg2; psycopg2.connect('${DB_URL}')" 2>/dev/null; then
            echo "✅ PostgreSQL disponible"
            break
        fi
        echo "   tentative $i/30..."
        sleep 1
    done
else
    echo "📁 Base SQLite — aucun attend requis"
fi

echo "📦 Migration de la base de données..."
python manage.py migrate --noinput

echo "📂 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear 2>/dev/null || echo "ℹ️  collectstatic ignoré"

echo "🚀 Démarrage du serveur..."
exec gunicorn hotel_project.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info}
