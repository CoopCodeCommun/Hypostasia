# =============================================================================
# Makefile — Hypostasia V3
#
# POURQUOI CE FICHIER EXISTE (14 aout 2026)
#
# Le lancement de dev a derive pendant des semaines sans que personne ne
# le voie : un worker Celery unique tirait `-Q celery,ingestion_docling`
# a concurrence 2, la ou la production declare un worker DEDIE a
# concurrence 1. La commande exacte vivait dans une passation Markdown —
# un document qu'on lit, pas qu'on execute. Ce Makefile la rend
# EXECUTABLE : ce qui se tape ne peut plus diverger de ce qui est ecrit.
# / The dev launch had silently drifted because the exact command lived
# in a Markdown handover — a document you read, not one you run.
#
# TOUT SE LANCE DEPUIS L'HOTE, jamais depuis l'interieur du conteneur :
# chaque cible passe par `docker exec`. On tape `make dev` depuis la
# racine du depot, pas apres un `docker exec -it bash`.
# / Everything runs from the host through docker exec.
#
# Le nom du conteneur est surchargeable, et il le faut : le fichier
# `docker-compose-prod.yml` nomme ses conteneurs `hypostasia_dev_web`
# (nommage trompeur, mais c'est ainsi). Sur une machine de production :
#     make prod-status CONTENEUR=hypostasia_dev_web
# / The container name is overridable: the prod compose file names its
# containers `hypostasia_dev_web`.
# =============================================================================

CONTENEUR ?= hypostasia_web
SETTINGS_TEST ?= hypostasia.settings_test_opus

CONF_DEV := /app/supervisord-dev.conf
CONF_PROD := /app/supervisord.conf

# La socket declaree par supervisord-dev.conf. Sa PRESENCE est le seul
# signe fiable que supervisord tourne : le code de retour de
# `supervisorctl status` est non nul des qu'UN programme n'est pas
# RUNNING — s'y fier ferait refuser `make restart` exactement quand un
# service est tombe, c'est-a-dire quand on en a besoin.
# / The socket's presence is the reliable signal: supervisorctl's exit
# code is non-zero as soon as one program is down, which would make
# `make restart` refuse precisely when it is needed.
SOCKET_DEV := /tmp/supervisor-dev.sock

# Raccourcis : `DANS` execute une commande dans /app du conteneur,
# `SUPERVISORCTL` pilote les services de dev.
# / Shorthands: run in the container, and drive the dev services.
DANS := docker exec -w /app $(CONTENEUR)
DANS_INTERACTIF := docker exec -it -w /app $(CONTENEUR)
SUPERVISORCTL := docker exec $(CONTENEUR) supervisorctl -c $(CONF_DEV)

# Les tests coûteux sont TOUS opt-in, et par deux mecanismes distincts :
# une variable d'environnement (TESTS_DOCLING, TESTS_LLM_REELS) ET un
# tag Django. Il faut les deux — le tag seul ne suffit pas a les lancer,
# la variable seule ne suffit pas a les isoler.
# / Costly tests are opt-in through BOTH an env var and a Django tag.
EXCLUSIONS_RAPIDES := --exclude-tag=e2e --exclude-tag=docling --exclude-tag=llm_reel

# Les scripts de demarrage vivent dans bin/ et s'executent DANS le
# conteneur. Ce Makefile ne recopie jamais leurs commandes : il les
# appelle. Deux definitions d'une meme sequence finissent toujours par
# diverger — c'est ce qui a produit les deux dernieres pannes.
# / The Makefile calls the scripts in bin/, never duplicates them.
SCRIPT_D_INSTALLATION := bin/install.sh

.DEFAULT_GOAL := aide

.PHONY: aide install dev status stop restart logs shell check fixtures \
        collectstatic fixtures-llm test test-rapide test-suite test-e2e test-docling \
        test-llm test-tout prod-update prod-status .verif-services .verif-docker

# Ce Makefile PILOTE Docker, il ne l'installe pas. Sans lui, chaque
# cible echouerait sur un « command not found » qui ne dit pas quoi
# faire. / This Makefile drives Docker; it does not install it.
.verif-docker:
	@command -v docker >/dev/null 2>&1 || { \
		echo ""; \
		echo "  Docker est introuvable sur cette machine."; \
		echo "  Ce Makefile pilote Docker depuis l'hote — il ne"; \
		echo "  l'installe pas. Voir https://docs.docker.com/engine/install/"; \
		echo ""; \
		exit 1; \
	}

aide:  ## Affiche cette aide
	@echo ""
	@echo "  Hypostasia — cibles disponibles"
	@echo "  --------------------------------"
	@# Les CHIFFRES comptent dans la classe : sans eux, `test-e2e` etait
	@# absent de cette aide sans que rien ne le signale.
	@# / Digits matter: without them, `test-e2e` silently vanished here.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / \
		{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Options : S=<cible>   pour restart, logs et les tests"
	@echo "            CONTENEUR=<nom>  si le conteneur n'est pas $(CONTENEUR)"
	@echo ""

# -----------------------------------------------------------------------------
# Cycle de vie — developpement
# -----------------------------------------------------------------------------

install: .verif-docker  ## Demarre tout : conteneurs, installation, services
	@# Le conteneur lance lui-meme bin/start-dev.sh (ou start-prod.sh
	@# selon DEBUG), qui enchaine bin/install.sh puis supervisord : il
	@# n'y a qu'une commande a taper.
	@# / The container runs bin/start-dev.sh by itself.
	docker compose up -d
	@echo "--- attente des services (premiere install : ~3 min, conversions PDF) ---"
	@until docker exec $(CONTENEUR) test -S $(SOCKET_DEV) 2>/dev/null; do sleep 3; done
	@$(SUPERVISORCTL) status
	@echo ""
	@echo "Le site : https://h.localhost/   —   les journaux : make logs"

dev: install  ## Synonyme d'install : le conteneur demarre tout lui-meme
	@:

status: .verif-docker  ## Etat des services de dev
	@if docker exec $(CONTENEUR) test -S $(SOCKET_DEV) 2>/dev/null; then \
		$(SUPERVISORCTL) status; \
	else \
		echo "Les services ne tournent pas. Les demarrer : make dev"; \
	fi

# Garde-fou des cibles qui n'ont aucun sens sans supervisord. Sans lui,
# elles rendaient un message brut de supervisorctl — « no such file » sur
# un chemin de socket — qui ne dit pas quoi faire.
# / Guard for the targets that make no sense without supervisord: the
# raw supervisorctl error names a socket path but not the next step.
.verif-services: .verif-docker
	@docker exec $(CONTENEUR) test -S $(SOCKET_DEV) 2>/dev/null || { \
		echo "Les services ne tournent pas. Les demarrer : make dev"; \
		exit 1; \
	}

stop: .verif-services  ## Arrete tous les services de dev
	@$(SUPERVISORCTL) shutdown

restart: .verif-services  ## Redemarre tout, ou un service : make restart S=runserver
	@if [ -n "$(S)" ]; then $(SUPERVISORCTL) restart $(S); \
	else $(SUPERVISORCTL) restart all; fi

logs:  ## Suit tous les journaux (DEBUG), ou filtre : make logs S=docling
	@# Les trois services ecrivent sur la sortie standard du conteneur :
	@# un seul flux, celui que montre `docker compose logs -f`. Filtrer
	@# par service se fait au grep, faute de prefixe pose par supervisord.
	@# / All three write to the container's stdout: one stream.
	@if [ -n "$(S)" ]; then \
		docker compose logs -f web 2>&1 | grep -i --line-buffered "$(S)"; \
	else \
		docker compose logs -f web; \
	fi

shell:  ## Ouvre un shell dans le conteneur
	@$(DANS_INTERACTIF) bash

# -----------------------------------------------------------------------------
# Commandes Django
# -----------------------------------------------------------------------------

check: .verif-docker  ## Verification Django (manage.py check)
	@$(DANS) python manage.py check

fixtures:  ## (Re)charge la demo : documents de sample/ + extractions
	@# On APPELLE l'etape du script d'installation, on ne recopie pas ses
	@# commandes : la sequence n'existe qu'a un seul endroit. Ne relance
	@# PAS l'analyse LLM facturee — pour cela, `make fixtures-llm`.
	@# / Call the installer's step; never duplicate its commands.
	@$(DANS) bash $(SCRIPT_D_INSTALLATION) fixtures

fixtures-llm:  ## Rejoue l'analyse par le VRAI LLM — APPELS FACTURES
	@# `--reset` et non l'etape `llm` du script : celle-ci porte
	@# `--si-absent`, qui ne referait justement rien. Ici on veut tout
	@# rejouer, et c'est pour cela qu'on demande confirmation.
	@# / --reset, not the installer's guarded step: here we want it redone.
	@if [ "$(CONFIRME)" != "oui" ]; then \
		echo ""; \
		echo "  ATTENTION : refait de VRAIS appels au modele configure."; \
		echo "  Ils sont FACTURES."; \
		echo ""; \
		printf "  Taper 'oui' pour continuer : "; \
		read reponse; \
		[ "$$reponse" = "oui" ] || { echo "  Annule."; exit 1; }; \
	fi
	$(DANS) python manage.py charger_fixtures_llm_reel --reset --asynchrone

collectstatic:  ## Collecte les statiques — utile AVANT un deploiement
	@echo "Rappel : inutile en dev (nginx/dev.conf ne sert pas /static/,"
	@echo "le runserver les sert via les finders quand DEBUG=true)."
	@$(DANS) bash $(SCRIPT_D_INSTALLATION) statiques

# -----------------------------------------------------------------------------
# Tests — une suite a la fois, JAMAIS --parallel
#
# La base de test est PARTAGEE ($(SETTINGS_TEST) -> une seule base) :
# deux executions simultanees se detruisent mutuellement la base en plein
# vol. C'est arrive le 14 aout 2026 entre deux sessions. D'ou `--noinput`
# partout, et aucune cible qui lance deux suites de front.
# / The test database is shared: two concurrent runs destroy each other.
# -----------------------------------------------------------------------------

test:  ## Aide des cibles de test et de leur cout
	@echo ""
	@echo "  make test-rapide      tout sauf e2e/docling/llm"
	@echo "                        1722 tests, ~7 min 30 (mesure du 14 aout 2026)"
	@echo "  make test-suite S=... une suite precise — quelques secondes"
	@echo "                        ex: S=front.tests.test_taches_ingestion"
	@echo "  make test-e2e         30 fichiers Playwright, plusieurs minutes"
	@echo "                        ex: make test-e2e S=test_09_alignement"
	@echo "  make test-docling     conversions Docling REELLES (~85 s)"
	@echo "  make test-llm         appels LLM REELS — FACTURES, demande confirmation"
	@echo "  make test-tout        rapide + e2e + docling (PAS le LLM payant)"
	@echo ""

test-rapide:  ## Tous les tests sauf e2e/docling/llm — 1722 tests, ~7 min 30
	$(DANS) python manage.py test $(EXCLUSIONS_RAPIDES) \
		--settings=$(SETTINGS_TEST) --noinput

test-suite:  ## Une suite precise : make test-suite S=front.tests.test_x
	@if [ -z "$(S)" ]; then \
		echo "Usage : make test-suite S=front.tests.test_taches_ingestion"; \
		exit 1; \
	fi
	$(DANS) python manage.py test $(S) --settings=$(SETTINGS_TEST) --noinput

test-e2e:  ## Tests navigateur Playwright : make test-e2e [S=test_09_alignement]
	$(DANS) python manage.py test front.tests.e2e$(if $(S),.$(S)) \
		--settings=$(SETTINGS_TEST) --noinput --keepdb

test-docling:  ## Conversions Docling reelles (~85 s, opt-in)
	docker exec -w /app -e TESTS_DOCLING=1 $(CONTENEUR) \
		python manage.py test hypostasis_extractor --tag=docling \
		--settings=$(SETTINGS_TEST) --noinput

test-llm:  ## Appels LLM REELS — FACTURES (CONFIRME=oui pour sauter la question)
	@if [ "$(CONFIRME)" != "oui" ]; then \
		echo ""; \
		echo "  ATTENTION : ces tests appellent REELLEMENT les API des"; \
		echo "  fournisseurs de modeles. Ils sont FACTURES."; \
		echo ""; \
		printf "  Taper 'oui' pour continuer : "; \
		read reponse; \
		[ "$$reponse" = "oui" ] || { echo "  Annule."; exit 1; }; \
	fi
	docker exec -w /app -e TESTS_LLM_REELS=1 $(CONTENEUR) \
		python manage.py test hypostasis_extractor --tag=llm_reel \
		--settings=$(SETTINGS_TEST) --noinput

test-tout:  ## rapide + e2e + docling, dans cet ordre. Sans le LLM payant.
	@echo "=== 1/3 — suite rapide ==="
	@$(MAKE) --no-print-directory test-rapide
	@echo "=== 2/3 — navigateur ==="
	@$(MAKE) --no-print-directory test-e2e
	@echo "=== 3/3 — Docling reel ==="
	@$(MAKE) --no-print-directory test-docling
	@echo ""
	@echo "Le LLM reel n'est PAS inclus (il est facture) : make test-llm"

# -----------------------------------------------------------------------------
# Production
#
# Ces deux cibles ne s'executent QUE sur la machine de production. Le
# garde-fou lit DEBUG dans .env : sur un poste de dev (DEBUG=true), elles
# refusent de tourner plutot que de faire des degats a moitie.
# / These two run on the production machine only; the guard reads DEBUG.
# -----------------------------------------------------------------------------

prod-update:  ## Met a jour la prod (refuse si DEBUG=true dans .env)
	@if [ ! -f .env ]; then \
		echo "REFUS : pas de .env — impossible de verifier ou l'on est."; \
		exit 1; \
	fi
	@if grep -qiE '^[[:space:]]*DEBUG[[:space:]]*=[[:space:]]*(true|1|yes)' .env; then \
		echo ""; \
		echo "  REFUS : .env porte DEBUG=true — cette machine est un poste"; \
		echo "  de developpement. Sur un poste de dev, utiliser : make dev"; \
		echo ""; \
		exit 1; \
	fi
	git pull
	$(DANS) uv sync
	$(DANS) python manage.py migrate
	$(DANS) python manage.py collectstatic --noinput
	docker exec $(CONTENEUR) supervisorctl -c $(CONF_PROD) restart \
		gunicorn daphne celery_worker celery_worker_docling
	@docker exec $(CONTENEUR) supervisorctl -c $(CONF_PROD) status

prod-status:  ## Etat des 4 programmes de production
	@docker exec $(CONTENEUR) supervisorctl -c $(CONF_PROD) status
