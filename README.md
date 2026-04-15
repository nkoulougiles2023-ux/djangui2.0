# DJANGUI 2.0

Backend Django/DRF pour une application camerounaise de **tontine + prêt instantané + investissement**.

Voir `DJANGUI2_SPEC.md` pour la spécification complète (14 modèles, 8 apps, règles métier).

## Stack

- Django 5.1 + DRF + SimpleJWT
- PostgreSQL + Redis + Celery
- drf-spectacular (OpenAPI)
- Déploiement cible : VPS (Gunicorn + Nginx)

## Endpoints clés

- `/` — landing JSON
- `/api/docs/` — Swagger UI
- `/api/schema/` — OpenAPI JSON
- `/api/v1/auth/...`, `/api/v1/loans/...`, `/api/v1/tontines/...`, etc.
- `/admin/` — Django admin

## Dev local

```bash
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # renseigner DB_*, REDIS_URL, SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Déploiement Vercel (preview uniquement)

⚠️ **Vercel n'est PAS la plateforme cible en production** : Celery workers, Celery beat, Redis, et uploads média ne fonctionneront pas. Cette configuration sert à partager une **preview** de l'API (Swagger, admin) à des relecteurs.

Variables d'environnement requises sur Vercel :

| Variable | Exemple |
|---|---|
| `SECRET_KEY` | valeur aléatoire forte |
| `DEBUG` | `False` |
| `DATABASE_URL` | `postgres://...` (Neon, Supabase, Vercel Postgres) |
| `ALLOWED_HOSTS` | `.vercel.app,mon-domaine.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` |
| `REDIS_URL` | optionnel (sinon cache local) |

Pour la prod réelle, utiliser **Railway / Render / Fly.io** qui supportent Postgres + workers + beat.
