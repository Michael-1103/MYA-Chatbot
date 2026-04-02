.PHONY: help build scrape web stop clean clean-all

CYAN  := \033[0;36m
RESET := \033[0m

help: ## Affiche cette aide
	@echo ""
	@echo "  $(CYAN)MYA-Chatbot$(RESET) — Epitech GlobalCampus scraper + chatbot"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-12s$(RESET) %s\n", $$1, $$2}'
	@echo ""

build: ## Build l'image Docker
	docker compose --profile scraper --profile web build

scrape: ## Lance le scraper (appel API direct, pas de navigateur requis)
	docker compose --profile scraper run --rm scraper

web: ## Lance l'interface web sur http://localhost:8080
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "  → .env créé, édite-le avec tes clés API puis relance 'make web'"; \
		exit 1; \
	fi
	docker compose --profile web up web

stop: ## Stoppe tous les containers Docker
	docker compose --profile scraper --profile web down

clean: ## Supprime les données scrapées
	rm -f data/destinations.json
	@echo "  Données supprimées"

clean-all: clean ## Supprime les données ET les images Docker
	docker compose down --rmi local --volumes
