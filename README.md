# MYA — Epitech International Exchange Assistant

> Chatbot RAG pour explorer les destinations d'échange international Epitech, propulsé par Claude, GPT-4 ou Mistral.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-24+-2496ED?logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Vue d'ensemble

MYA combine un **scraper d'API** et un **chatbot web** pour permettre aux étudiants Epitech d'explorer les ~143 destinations partenaires disponibles sur [epitech.globalcampus.app](https://epitech.globalcampus.app/programs/).

| Composant | Technologie |
|---|---|
| Scraper | Python + httpx, appel API paginé |
| Backend | FastAPI + SSE streaming |
| Frontend | HTML/CSS/JS vanilla, Markdown rendu |
| RAG | Scoring par mots-clés, injection de contexte |
| LLM | Claude (Anthropic), GPT-4o (OpenAI), Mistral |
| Runtime | Docker Compose |

---

## Table des matières

- [Prérequis](#prérequis)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Étape 1 — Scraper les destinations](#étape-1--scraper-les-destinations)
- [Étape 2 — Lancer l'interface web](#étape-2--lancer-linterface-web)
- [Configuration des modèles](#configuration-des-modèles)
- [Structure du projet](#structure-du-projet)
- [Architecture technique](#architecture-technique)
- [Référence API](#référence-api)
- [Référence Makefile](#référence-makefile)
- [Dépannage](#dépannage)
- [Contribuer](#contribuer)

---

## Prérequis

| Outil | Version minimale | Vérification |
|---|---|---|
| Docker | 24+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Clé API LLM | au moins une | Claude / OpenAI / Mistral |

---

## Installation

```bash
git clone https://github.com/Michael-1103/MYA-Chatbot.git
cd MYA-Chatbot

cp .env.example .env   # à éditer avec ta clé API
make build
```

---

## Démarrage rapide

```bash
make scrape   # récupère les destinations depuis l'API Epitech
make web      # lance le chatbot sur http://localhost:8080
make stop     # stoppe les containers
```

---

## Étape 1 — Scraper les destinations

```bash
make scrape
```

Le scraper appelle directement l'API REST publique d'Epitech GlobalCampus avec pagination automatique, sans navigateur ni authentification requise.

**Déroulement :**

1. Appel paginé à `epitech.campuscommunity.app/api/v2/public/programs` (25 programmes/page, 6 pages)
2. Extraction structurée des métadonnées depuis le JSON
3. Sauvegarde dans `data/destinations.json`

### Données collectées

| Champ | Description |
|---|---|
| `university_name` | Nom de l'université partenaire |
| `country` | Pays |
| `language` | Langue d'enseignement |
| `spots` | Nombre de places disponibles |
| `duration` | Durée (`Semester` / `Academic Year`) |
| `program_type` | Type (`Erasmus+`, `Fee-Paying`, `All Other Programs`) |
| `specializations` | Spécialisations disponibles |
| `gpa_requirement` | GPA requis |
| `language_test_required` | Test de langue obligatoire |
| `dual_degree` | Double diplôme proposé |
| `price_cents` | Frais en centimes (0 = gratuit) |
| `full_text` | Description complète + itinéraire (≤ 10 000 caractères) |
| `url` | URL de la fiche sur le site Epitech |
| `scraped_at` | Horodatage |

### Format de sortie

```json
{
  "scraped_at": "2026-04-02T10:00:00",
  "source": "https://epitech.globalcampus.app/programs/",
  "count": 143,
  "destinations": [
    {
      "url": "https://epitech.globalcampus.app/programs/7be45292-...",
      "scraped_at": "2026-04-02T10:01:23",
      "university_name": "Università degli Studi di Modena e Reggio Emilia",
      "country": "Italy",
      "language": "English",
      "spots": "3",
      "duration": "Academic Year",
      "program_type": "Erasmus+",
      "specializations": ["Artificial Intelligence"],
      "gpa_requirement": "None",
      "language_test_required": "No",
      "dual_degree": "No",
      "price_cents": 0,
      "full_text": "..."
    }
  ]
}
```

---

## Étape 2 — Lancer l'interface web

### Configuration

Édite `.env` avec le provider et la clé API de ton choix :

```bash
# Provider : claude | openai | mistral
PROVIDER=claude
MODEL=claude-sonnet-4-6

ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

### Lancement

```bash
make web
# → http://localhost:8080
```

### Interface

**Sidebar**
- Provider et modèle actif
- Nombre de destinations en mémoire
- Bouton **Recharger** (prend en compte un nouveau scraping sans redémarrage)
- Questions suggérées

**Chat**
- Streaming token par token
- Rendu Markdown complet (titres, tableaux, listes, code)
- Bouton **Nouvelle conversation** pour réinitialiser l'historique

**Exemples de questions**

```
Quelles destinations anglophones sont disponibles ?
Compare les universités en Asie
Quelle est la meilleure destination pour quelqu'un qui parle espagnol ?
Combien de places y a-t-il à Tokyo ?
Quels documents faut-il préparer pour un échange en Australie ?
Quel est le coût de la vie à Montréal ?
```

---

## Configuration des modèles

### Variables d'environnement

| Variable | Description |
|---|---|
| `PROVIDER` | Provider LLM : `claude`, `openai` ou `mistral` |
| `MODEL` | Nom du modèle (optionnel, sinon valeur par défaut) |
| `ANTHROPIC_API_KEY` | Clé API Anthropic |
| `OPENAI_API_KEY` | Clé API OpenAI |
| `MISTRAL_API_KEY` | Clé API Mistral |
| `OPENAI_BASE_URL` | Base URL custom (Ollama, proxy, etc.) |

### Modèles par défaut

| Provider | Défaut | Alternatives |
|---|---|---|
| `claude` | `claude-sonnet-4-6` | `claude-opus-4-6`, `claude-haiku-4-5-20251001` |
| `openai` | `gpt-4o` | `gpt-4o-mini`, `gpt-4-turbo` |
| `mistral` | `mistral-small-latest` | `mistral-large-latest`, `open-mistral-7b` |

### Exemples de configuration

**Claude Haiku — rapide et économique**
```bash
PROVIDER=claude
MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

**GPT-4o mini — OpenAI économique**
```bash
PROVIDER=openai
MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

**Modèle local via Ollama**
```bash
PROVIDER=openai
MODEL=llama3.2
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

> `host.docker.internal` permet au container Docker d'atteindre `localhost` de la machine hôte.

---

## Structure du projet

```
MYA-Chatbot/
├── scraper.py              Scraper API (httpx, pagination automatique)
├── server.py               Backend FastAPI (REST + SSE + frontend statique)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/
│   └── destinations.json   Généré par make scrape
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── Makefile
```

---

## Architecture technique

```
┌─────────────────────────────────────────────────────┐
│                     Docker                          │
│                                                     │
│  ┌──────────────┐         ┌──────────────────────┐  │
│  │  scraper.py  │         │      server.py       │  │
│  │              │         │  (FastAPI + uvicorn) │  │
│  │  httpx       │  data/  │                      │  │
│  │  API REST    ├────────►│  RAG scoring +       │  │
│  │  paginée     │  JSON   │  injection contexte  │  │
│  │              │         │  SSE streaming       │  │
│  └──────────────┘         └──────────┬───────────┘  │
│                                      │ :8080        │
└──────────────────────────────────────┼──────────────┘
                                       │
                         ┌─────────────▼──────────────┐
                         │  Navigateur (HTML/CSS/JS)  │
                         │  marked.js — Markdown      │
                         └─────────────┬──────────────┘
                                       │ HTTPS
                         ┌─────────────▼──────────────┐
                         │   API LLM                  │
                         │   Anthropic / OpenAI /     │
                         │   Mistral                  │
                         └────────────────────────────┘
```

### RAG — Retrieval-Augmented Generation

À chaque message, le serveur sélectionne les destinations les plus pertinentes avant d'appeler le LLM :

1. Extraction des mots-clés de la question (longueur > 2 caractères)
2. Scoring : **×3** si le mot apparaît dans le nom de l'université ou le pays, **×1** ailleurs
3. Tri par score décroissant — top 15 sélectionnés (limite : 80 000 caractères)
4. Injection du contexte dans le message avant envoi au modèle

### Streaming SSE

Les tokens sont transmis en temps réel via [Server-Sent Events](https://developer.mozilla.org/fr/docs/Web/API/Server-sent_events) :

```
data: {"token": "Voici"}
data: {"token": " les destinations"}
...
data: [DONE]
```

---

## Référence API

### `GET /api/stats`

```json
{
  "destinations_count": 143,
  "provider": "claude",
  "model": "claude-sonnet-4-6",
  "data_available": true
}
```

### `POST /api/reload`

Recharge `data/destinations.json` en mémoire sans redémarrer le serveur.

```json
{ "destinations_count": 143 }
```

### `POST /api/chat`

**Corps :**
```json
{
  "messages": [
    { "role": "user", "content": "Quelles destinations en Asie ?" },
    { "role": "assistant", "content": "Il y a plusieurs destinations..." },
    { "role": "user", "content": "Et au Japon spécifiquement ?" }
  ]
}
```

**Réponse** — `text/event-stream` :
```
data: {"token": "Au Japon"}
...
data: [DONE]
```

```
data: {"error": "Invalid API key"}
data: [DONE]
```

---

## Référence Makefile

| Commande | Description |
|---|---|
| `make help` | Liste toutes les commandes disponibles |
| `make build` | Build l'image Docker |
| `make scrape` | Lance le scraper |
| `make web` | Lance le chatbot sur http://localhost:8080 |
| `make stop` | Stoppe tous les containers |
| `make clean` | Supprime `data/destinations.json` |
| `make clean-all` | Supprime les données et les images Docker |

---

## Dépannage

### "Aucune donnée — lance le scraper"

`data/destinations.json` n'existe pas. Lance `make scrape` en premier.  
Si le fichier existe mais que le chatbot ne le voit pas, clique sur **Recharger** dans la sidebar.

### Erreur `Invalid API key`

Vérifie que la clé dans `.env` correspond au `PROVIDER` configuré et qu'elle est valide.

### Port 8080 déjà utilisé

Dans `docker-compose.yml`, change le port exposé :
```yaml
ports:
  - "3000:8080"
```

### Le scraper retourne 0 destination

1. Vérifie ta connexion internet
2. L'URL de l'API a peut-être changé — inspecte le trafic réseau sur `epitech.globalcampus.app/programs/` (DevTools → Network → filtre `api/v2/public/programs`)
3. Lis le message d'erreur dans le terminal

### Modèle local avec Ollama

```bash
ollama serve && ollama pull llama3.2
```

```bash
# .env
PROVIDER=openai
MODEL=llama3.2
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

---

## Contribuer

Les contributions sont les bienvenues.

**Workflow :**

1. Fork le dépôt
2. Crée une branche (`git checkout -b feature/ma-feature`)
3. Commit avec un message conventionnel (`feat:`, `fix:`, `docs:`…)
4. Push et ouvre une Pull Request

**Signaler un bug :** ouvre une [issue](../../issues) avec les étapes de reproduction et ton environnement (OS, version Docker).
