#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TMP_DB="${TMPDIR:-/tmp}/hotel-saas-pos-access-v2.sqlite3"
rm -f "$TMP_DB"

export DATABASE_URL="sqlite:////${TMP_DB#/}"
export DISABLE_SESSION_VERIFIER_LOOP=1
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-hotel_project.settings}"

cleanup() {
  rm -f "$TMP_DB"
}
trap cleanup EXIT

echo "== Django system check =="
python manage.py check

echo "== Migration drift check =="
python manage.py makemigrations --check --dry-run

echo "== Apply migrations on isolated SQLite =="
python manage.py migrate --noinput

echo "== POS access / schedule / scope tests =="
python manage.py test \
  apps.pos.tests.test_access_service \
  apps.pos.tests.test_access_admin_api \
  apps.pos.tests.test_order_scope \
  apps.pos.tests.test_session_verifier_access \
  --verbosity 2

echo "== Payment settlement tests =="
python manage.py test \
  apps.paiements.tests.test_commande_settlement \
  --verbosity 2

echo "== Existing POS regression tests =="
python manage.py test \
  apps.pos.tests.test_parcours_restaurant \
  --verbosity 2

echo "== Restaurant regression tests =="
python manage.py test \
  apps.restaurant.tests \
  --verbosity 2

echo "== POS healthcheck on isolated DB =="
python manage.py pos_healthcheck

echo "VALIDATION POS ACCESS V2: PASS"
