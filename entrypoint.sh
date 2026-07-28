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
    echo "📁 Base SQLite"
    # Garde : si db.sqlite3 a été écrasé par un volume vide, on le restaure
    if [ ! -f db.sqlite3 ] || [ ! -s db.sqlite3 ]; then
        echo "⚠️  db.sqlite3 vide ou manquant → restauration depuis le backup"
        if [ -f /app/db.sqlite3.bak ]; then
            cp /app/db.sqlite3.bak /app/db.sqlite3
            echo "✅ db.sqlite3 restauré depuis le backup"
        else
            echo "❌ Aucun backup disponible — création d'une base vierge"
        fi
    fi
fi

echo "📦 Migration de la base de données..."
python manage.py migrate --noinput

echo "🌱 Seed des données de base (admin/admin123)..."
python manage.py seed_data 2>/dev/null || echo "ℹ️  seed_data ignoré"

echo "🏦 Configuration des caisses (Banque, Orange Money, Moov Money)..."
python manage.py setup_caisses 2>/dev/null || echo "ℹ️  setup_caisses ignoré"

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
