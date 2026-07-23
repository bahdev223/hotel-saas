# Checklist Déploiement Production

## Serveur
- Ubuntu 22.04
- Python 3.12
- PostgreSQL
- Redis
- Nginx
- Gunicorn

## Sécurité
- HTTPS activé
- Firewall UFW
- Sauvegarde automatique
- Variables .env sécurisées

## Django
- DEBUG=False
- ALLOWED_HOSTS configuré
- collectstatic exécuté
- migrations appliquées

## Monitoring
- Logs Gunicorn
- Logs Nginx
- Monitoring uptime
- Sauvegarde base données


