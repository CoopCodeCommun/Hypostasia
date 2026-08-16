# PHASE-22 — Migration PostgreSQL + Redis

**Complexite** : M | **Mode** : Normal | **Prerequis** : aucun

---

## 1. Contexte

SQLite ne supporte pas les ecritures concurrentes (verrou exclusif sur toute la base), ce qui bloque la Phase 5 (collab) et la Phase 8 (live). Le broker Celery SQLAlchemy+SQLite est marque "experimental / not recommended" par la doc Celery. PostgreSQL est aussi necessaire pour pgvector (Phase 6). Cette phase migre la base de donnees vers PostgreSQL et le broker Celery vers Redis.

**Decision** : PostgreSQL + Redis partout (dev, prod, boitier offline). Pas de fallback SQLite.
L'infra (postgres + redis) tourne dans Docker via `docker-compose.dev.yml`, le code Django tourne en local.

## 2. Prerequis

Aucun. Cette phase est independante.

## 3. Objectifs precis

- [x] Installer PostgreSQL et Redis via Docker (`docker-compose.dev.yml`)
- [x] Configurer `DATABASES` dans `settings.py` pour PostgreSQL (pas de fallback SQLite)
- [x] Migrer le broker Celery de `sqla+sqlite` vers `redis://`
- [x] Mettre a jour `docker-compose.yml` avec les services PostgreSQL et Redis
- [x] Mettre a jour `hypostasia/celery.py` avec le nouveau broker Redis
- [x] Tester : `uv run python manage.py migrate` sur la nouvelle base
- [x] Documenter la procedure de migration des donnees SQLite vers PostgreSQL
- [x] Fix bug JSON key ordering dans `views_alignement.py` (revele par PostgreSQL)

## 4. Fichiers modifies/crees

- `hypostasia/settings.py` — `DATABASES` PostgreSQL, `CELERY_BROKER_URL` Redis, CSRF ports 8123
- `hypostasia/celery.py` — docstring mis a jour
- `docker-compose.yml` — ajout services PostgreSQL + Redis, depends_on healthy, volumes pgdata + media
- `docker-compose.dev.yml` — **cree** — PostgreSQL 17 + Redis 7 pour le dev
- `pyproject.toml` — ajout `psycopg[binary]`, `redis` ; retrait `sqlalchemy`
- `Dockerfile` — ajout `postgresql-client`
- `start.sh` — attente PostgreSQL avant migrate
- `.env.example` — **cree** — reference des variables d'environnement
- `front/views_alignement.py` — fix acces JSON par position → acces par cle explicite

## 5. Criteres de validation

- [x] `uv run python manage.py check` passe
- [x] `uv run python manage.py migrate` s'execute sans erreur sur PostgreSQL
- [x] `uv run python manage.py charger_fixtures_demo` charge les donnees
- [x] 543 tests passent sur PostgreSQL
- [x] Le worker Celery demarre avec le broker Redis : `uv run celery -A hypostasia worker --loglevel=info`
- [x] `docker-compose -f docker-compose.dev.yml up -d` lance PostgreSQL, Redis et Nginx sans erreur
- [ ] L'import audio (transcription) fonctionne toujours via Celery+Redis (non teste)

## 5b. Verification navigateur

> Lancer `docker compose -f docker-compose.dev.yml up -d` puis `uv run python manage.py runserver 0.0.0.0:8123`

1. **Verifier que le serveur demarre sans erreur avec PostgreSQL**
   - **Attendu** : pas d'erreur au lancement, les logs sont propres
2. **Ouvrir http://0.0.0.0:8123/**
   - **Attendu** : l'arbre de dossiers charge, les pages existantes sont la
3. **Importer un document**
   - **Attendu** : il est sauve en PostgreSQL
4. **Lancer une extraction**
   - **Attendu** : Celery fonctionne avec Redis comme broker

## 6. Architecture cible

```
Dev :   docker compose -f docker-compose.dev.yml up -d   (postgres + redis)
        uv run python manage.py runserver 0.0.0.0:8123   (byobu window 1)
        uv run celery -A hypostasia worker                (byobu window 2)

Prod :  docker compose up                                 (tout : postgres + redis + web + nginx)

Boitier offline : docker compose up                       (meme stack que prod)
```
