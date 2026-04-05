.PHONY: help build up stop logs clean

CYAN  := \033[0;36m
RESET := \033[0m

help: ## Affiche cette aide
	@echo ""
	@echo "  $(CYAN)MYA-Chatbot$(RESET) — Production"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-8s$(RESET) %s\n", $$1, $$2}'
	@echo ""

build: ## Build l'image Docker
	docker compose build

up: ## Lance le serveur sur http://localhost:8080
	docker compose up -d

stop: ## Stoppe le serveur
	docker compose down

logs: ## Affiche les logs en temps réel
	docker compose logs -f

clean: ## Supprime les données scrapées
	docker compose exec mya rm -f /app/data/destinations.json
