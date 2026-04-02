# MYA — Assistant Échanges Internationaux Epitech

MYA est un outil en deux parties :

1. **Un scraper** qui extrait toutes les destinations disponibles sur [epitech.globalcampus.app/programs/](https://epitech.globalcampus.app/programs/) (site public, aucun login requis).
2. **Un chatbot web** qui répond à tes questions sur ces destinations en s'appuyant sur les données scrapées, complétées par la connaissance générale du modèle IA choisi.

Le tout tourne dans Docker, et tu peux choisir librement entre Claude (Anthropic), GPT (OpenAI) ou Mistral.

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

---

## Prérequis

| Outil | Version minimale | Vérification |
|---|---|---|
| Docker | 24+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Clé API | au moins une (Claude, OpenAI ou Mistral) | — |

Le scraper appelle directement l'API publique du site — aucun navigateur, aucun affichage requis.

---

## Installation

```bash
git clone <url-du-repo>
cd MYA-Chatbot

# Crée ton fichier de configuration
cp .env.example .env

# Build l'image Docker
make build
```

---

## Démarrage rapide

```bash
# 1. Scraper les destinations (headless, aucun login requis)
make scrape

# 2. Configurer la clé API dans .env
#    (édite .env, renseigne ANTHROPIC_API_KEY ou autre)

# 3. Lancer l'interface web
make web
# → Ouvre http://localhost:8080
```

---

## Étape 1 — Scraper les destinations

```bash
make scrape
```

Ce que ça fait :

1. Appelle l'API publique `epitech.campuscommunity.app/api/v2/public/programs` avec pagination
2. Récupère les 143 destinations sur 6 pages
3. Extrait les données structurées (pays, langue, places, spécialisations…) directement depuis le JSON
4. Sauvegarde dans `data/destinations.json`

### Ce que le scraper collecte

Pour chaque destination, il tente d'extraire :

| Champ | Description |
|---|---|
| `university_name` | Nom de l'université partenaire |
| `country` | Pays |
| `city` | Ville |
| `language` | Langue d'enseignement |
| `spots` | Nombre de places disponibles |
| `duration` | Durée (`Semester` / `Academic Year`) |
| `program_type` | Type (`Erasmus+`, `Fee-Paying`, `All Other Programs`) |
| `specializations` | Liste de spécialisations |
| `gpa_requirement` | GPA requis |
| `language_test_required` | Test de langue obligatoire |
| `dual_degree` | Double diplôme proposé |
| `price_cents` | Prix en centimes (0 = gratuit) |
| `full_text` | Description + itinéraire (jusqu'à 10 000 caractères) |
| `url` | URL de la page source |
| `scraped_at` | Horodatage du scraping |

### Stratégie de scraping

Le scraper appelle directement l'API REST publique `epitech.campuscommunity.app/api/v2/public/programs` avec pagination (25 programmes par page). Les données sont extraites proprement depuis le JSON retourné — pas de parsing HTML, pas de regex fragile.

### Format de `data/destinations.json`

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

Édite le fichier `.env` avec ta clé API et le provider de ton choix :

```bash
# Provider : claude | openai | mistral
PROVIDER=claude
MODEL=claude-sonnet-4-6

ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

### Lancement

```bash
make web
```

Le serveur démarre sur **http://localhost:8080**.

### Utilisation de l'interface

L'interface se compose de deux zones :

**Sidebar gauche**
- Nom du modèle actif
- Nombre de destinations chargées en mémoire
- Bouton **Recharger** pour prendre en compte un nouveau scraping sans redémarrer
- **Suggestions** de questions prêtes à l'emploi

**Zone de chat**
- Tape ta question et appuie sur **Entrée** (ou Shift+Entrée pour un saut de ligne)
- La réponse s'affiche en **streaming** token par token
- Le markdown est rendu : titres, listes, tableaux, code, etc.
- **Nouvelle conversation** remet l'historique à zéro

### Exemples de questions

```
Quelles destinations anglophones sont disponibles ?
Compare les universités en Asie
Quelle est la meilleure destination pour quelqu'un qui parle espagnol ?
Combien de places y a-t-il à Tokyo ?
Quels documents faut-il préparer pour un échange en Australie ?
Quel est le coût de la vie à Montréal ?
Explique-moi les démarches pour partir en échange au semestre 7
```

---

## Configuration des modèles

### Variables d'environnement

| Variable | Valeur | Description |
|---|---|---|
| `PROVIDER` | `claude` / `openai` / `mistral` | Provider LLM à utiliser |
| `MODEL` | voir tableau ci-dessous | Nom exact du modèle (optionnel) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Clé API Anthropic |
| `OPENAI_API_KEY` | `sk-...` | Clé API OpenAI |
| `MISTRAL_API_KEY` | `...` | Clé API Mistral |
| `OPENAI_BASE_URL` | URL | Base URL custom (Ollama, proxy…) |

### Modèles disponibles par défaut

| Provider | Modèle par défaut | Alternatives |
|---|---|---|
| `claude` | `claude-sonnet-4-6` | `claude-opus-4-6`, `claude-haiku-4-5-20251001` |
| `openai` | `gpt-4o` | `gpt-4o-mini`, `gpt-4-turbo` |
| `mistral` | `mistral-small-latest` | `mistral-large-latest`, `open-mistral-7b` |

### Exemples de configurations

**Claude Haiku (rapide et économique)**
```bash
PROVIDER=claude
MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
```

**GPT-4o mini (OpenAI, économique)**
```bash
PROVIDER=openai
MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

**Modèle local via Ollama**
```bash
PROVIDER=openai
MODEL=llama3.2
OPENAI_API_KEY=ollama         # valeur arbitraire, non vérifiée
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

> Pour qu'un modèle Ollama soit accessible depuis Docker, utilise `host.docker.internal` à la place de `localhost`.

---

## Structure du projet

```
MYA-Chatbot/
│
├── scraper.py              Scraper Playwright (login interactif + extraction)
├── server.py               Backend FastAPI (API REST + SSE + frontend statique)
│
├── frontend/
│   ├── index.html          Structure HTML de l'interface
│   ├── style.css           Thème sombre, layout, composants
│   └── app.js              Logique chat, streaming SSE, rendu Markdown
│
├── data/                   Volume Docker — données persistées
│   ├── destinations.json   Résultat du scraping (créé par scraper.py)
│   └── session_cookies.json  Session Epitech sauvegardée (créé par scraper.py)
│
├── Dockerfile              Image basée sur mcr.microsoft.com/playwright/python
├── docker-compose.yml      Services : scraper (profil) + web (profil)
├── requirements.txt        Dépendances Python
├── .env.example            Template de configuration
├── .env                    Ta configuration (à créer, non versionné)
├── .gitignore              Exclut .env et data/
└── Makefile                Commandes simplifiées
```

---

## Architecture technique

```
┌─────────────────────────────────────────────────────┐
│                     Docker                          │
│                                                     │
│  ┌──────────────┐         ┌──────────────────────┐  │
│  │  scraper.py  │         │      server.py       │  │
│  │              │         │  (FastAPI + uvicorn)  │  │
│  │  Playwright  │  data/  │                      │  │
│  │  Chromium    ├────────►│  RAG : scoring +     │  │
│  │              │  JSON   │  injection contexte  │  │
│  │  Headless    │         │                      │  │
│  │  /programs/  │         │  SSE streaming       │  │
│  └──────────────┘         └──────────┬───────────┘  │
│                                      │ :8080         │
└──────────────────────────────────────┼──────────────┘
                                       │
                         ┌─────────────▼──────────────┐
                         │      Navigateur             │
                         │   frontend/ (HTML/CSS/JS)   │
                         │   marked.js (Markdown)      │
                         └─────────────┬──────────────┘
                                       │ HTTPS
                         ┌─────────────▼──────────────┐
                         │       API LLM              │
                         │  Anthropic / OpenAI /      │
                         │  Mistral                   │
                         └────────────────────────────┘
```

### Fonctionnement du RAG (Retrieval-Augmented Generation)

Quand tu envoies un message, le serveur ne passe pas toutes les destinations au modèle d'un coup. Il sélectionne les plus pertinentes via un **scoring par mots-clés** :

1. Les mots de ta question sont extraits (longueur > 2 caractères)
2. Chaque destination reçoit un score : **×3** si le mot apparaît dans le nom de l'université, la ville ou le pays ; **×1** sinon
3. Les destinations sont triées par score décroissant
4. Les 15 meilleures sont sélectionnées, dans la limite de 80 000 caractères de contexte
5. Ce contexte est injecté dans le message utilisateur avant envoi au modèle

Le modèle reçoit ainsi les données les plus pertinentes pour répondre, sans dépasser les limites de contexte.

### Streaming SSE

Les réponses du modèle sont transmises en [Server-Sent Events](https://developer.mozilla.org/fr/docs/Web/API/Server-sent_events). Chaque token est envoyé dès qu'il est généré :

```
data: {"token": "Voici"}
data: {"token": " les"}
data: {"token": " destinations"}
...
data: [DONE]
```

Le frontend lit ce flux et met à jour l'interface en temps réel, token par token.

---

## Référence API

Le serveur expose trois endpoints REST :

### `GET /api/stats`

Retourne l'état actuel du serveur.

```json
{
  "destinations_count": 142,
  "provider": "claude",
  "model": "claude-sonnet-4-6",
  "data_available": true
}
```

### `POST /api/reload`

Recharge `data/destinations.json` en mémoire sans redémarrer le serveur. Utile après un nouveau scraping.

```json
{ "destinations_count": 156 }
```

### `POST /api/chat`

Envoie un historique de conversation et reçoit la réponse en streaming SSE.

**Corps de la requête :**
```json
{
  "messages": [
    { "role": "user", "content": "Quelles destinations en Asie ?" },
    { "role": "assistant", "content": "Il y a plusieurs destinations..." },
    { "role": "user", "content": "Et au Japon spécifiquement ?" }
  ]
}
```

**Réponse :** `text/event-stream`
```
data: {"token": "Au"}
data: {"token": " Japon"}
data: {"token": ","}
...
data: [DONE]
```

En cas d'erreur :
```
data: {"error": "Invalid API key"}
data: [DONE]
```

---

## Référence Makefile

| Commande | Description |
|---|---|
| `make help` | Affiche toutes les commandes disponibles |
| `make build` | Build l'image Docker |
| `make scrape` | Lance le scraper (API directe, pas de navigateur) |
| `make web` | Lance l'interface web sur http://localhost:8080 |
| `make clean` | Supprime `destinations.json` |
| `make clean-all` | Supprime les données ET les images Docker |

---

## Dépannage

### `make web` : "Aucune donnée — lance le scraper"

Le fichier `data/destinations.json` n'existe pas encore. Lance d'abord le scraper :

```bash
make scrape
```

Si tu viens de scraper et que le chatbot ne voit toujours rien, clique sur **Recharger** dans la sidebar de l'interface web, ou relance `make web`.

---

### Erreur `Invalid API key`

Vérifie que ton `.env` contient bien la bonne clé pour le provider configuré :

```bash
# Si PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...   # doit commencer par sk-ant-

# Si PROVIDER=openai
OPENAI_API_KEY=sk-...          # doit commencer par sk-

# Si PROVIDER=mistral
MISTRAL_API_KEY=...
```

---

### Port 8080 déjà utilisé

Change le port dans `docker-compose.yml` :

```yaml
ports:
  - "3000:8080"   # accessible sur http://localhost:3000
```

---

### Le scraper ne trouve aucune destination

Le scraper appelle directement l'API publique. Si le résultat est vide :

1. Vérifie ta connexion internet
2. L'API a peut-être changé d'URL — inspecte le trafic réseau sur `epitech.globalcampus.app/programs/` dans les DevTools du navigateur (onglet Network, filtre `api/v2/public/programs`)
3. Regarde le message d'erreur dans le terminal pour diagnostiquer

---

### Utiliser un modèle local (Ollama)

```bash
# Lance Ollama sur la machine hôte
ollama serve
ollama pull llama3.2

# Dans .env
PROVIDER=openai
MODEL=llama3.2
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

`host.docker.internal` est le hostname qui permet au container Docker d'atteindre `localhost` de la machine hôte.
