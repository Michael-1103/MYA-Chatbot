"""
MYA — Serveur web FastAPI
─────────────────────────
- Sert le frontend statique
- /api/chat       POST → SSE streaming
- /api/stats      GET  → infos sur les données & le modèle
- /api/reload     POST → recharge les destinations en mémoire
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")
DESTINATIONS_FILE = DATA_DIR / "destinations.json"
FRONTEND_DIR = Path("frontend")

PROVIDER = os.getenv("PROVIDER", "claude").lower()
MODEL_ENV = os.getenv("MODEL", "")
DEFAULTS = {
    "claude":  "claude-sonnet-4-6",
    "openai":  "gpt-4o",
    "mistral": "mistral-small-latest",
}
MODEL = MODEL_ENV or DEFAULTS.get(PROVIDER, "claude-sonnet-4-6")

MAX_CONTEXT_CHARS = 80_000
MAX_DEST_PER_QUERY = 15

SYSTEM_PROMPT = """Tu es MYA, un assistant spécialisé dans les programmes d'échange internationaux pour les étudiants d'Epitech.

Tu as accès à des données scrappées depuis epitech.globalcampus.app sur les destinations partenaires.

Tes capacités :
- Répondre aux questions sur les destinations (université, pays, ville, langue, places, durée...)
- Comparer des destinations entre elles
- Donner des conseils pratiques sur la vie dans un pays (culture, coût de la vie, visa, logement...)
- Expliquer les démarches administratives pour un échange
- Tu peux te baser sur ta connaissance générale du monde quand les données scrappées ne suffisent pas

Si des données scrappées sont fournies, base-toi en priorité sur elles.
Réponds toujours en français sauf si l'utilisateur parle une autre langue.
Utilise du markdown pour structurer tes réponses quand c'est pertinent."""

# ── Données ───────────────────────────────────────────────────────────────────

_destinations: list[dict] = []


def load_destinations() -> list[dict]:
    global _destinations
    if not DESTINATIONS_FILE.exists():
        _destinations = []
        return []
    raw = json.loads(DESTINATIONS_FILE.read_text())
    if isinstance(raw, dict):
        _destinations = raw.get("destinations", [])
    elif isinstance(raw, list):
        _destinations = raw
    else:
        _destinations = []
    return _destinations


def dest_to_text(dest: dict) -> str:
    parts = []
    for key in ["university_name", "country", "city", "language", "spots",
                "duration", "level", "semester", "url"]:
        if dest.get(key):
            parts.append(f"{key}: {dest[key]}")
    if dest.get("full_text"):
        parts.append(dest["full_text"][:2000])
    if dest.get("tables"):
        for table in dest["tables"][:2]:
            for row in table:
                parts.append(" | ".join(row))
    return "\n".join(parts)


def score_destination(dest: dict, query: str) -> int:
    words = set(re.findall(r"\w+", query.lower()))
    text = dest_to_text(dest).lower()
    priority = (dest.get("country", "") + dest.get("city", "") +
                dest.get("university_name", "")).lower()
    score = sum(3 if w in priority else 1
                for w in words if len(w) > 2 and w in text)
    return score


def build_context(query: str) -> str:
    if not _destinations:
        return ""
    scored = sorted(
        [(score_destination(d, query), d) for d in _destinations],
        key=lambda x: x[0], reverse=True
    )
    selected, total = [], 0
    for score, dest in scored:
        if len(selected) >= MAX_DEST_PER_QUERY:
            break
        t = dest_to_text(dest)
        if total + len(t) > MAX_CONTEXT_CHARS:
            break
        selected.append(dest)
        total += len(t)
    if not selected:
        return ""
    parts = [f"=== DESTINATION {i+1} ===\n{dest_to_text(d)}"
             for i, d in enumerate(selected)]
    return "\n\n".join(parts)


# ── Scraper intégré ───────────────────────────────────────────────────────────

_scrape_state: dict = {
    "running": False,
    "last_run": None,
    "last_count": 0,
    "error": None,
}


async def _run_scraper():
    global _scrape_state, _destinations
    _scrape_state["running"] = True
    _scrape_state["error"] = None
    try:
        from scraper import fetch_all_programs
        destinations = await fetch_all_programs()
        output = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": "https://epitech.globalcampus.app/programs/",
            "count": len(destinations),
            "destinations": destinations,
        }
        DESTINATIONS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        _destinations = destinations
        _scrape_state["last_count"] = len(destinations)
        _scrape_state["last_run"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        _scrape_state["error"] = str(e)
    finally:
        _scrape_state["running"] = False


# ── Clients LLM ───────────────────────────────────────────────────────────────

async def stream_claude(messages: list[dict]) -> AsyncGenerator[str, None]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    async with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def stream_openai(messages: list[dict]) -> AsyncGenerator[str, None]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    stream = await client.chat.completions.create(
        model=MODEL, messages=full_messages, stream=True, max_tokens=2048,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def stream_mistral(messages: list[dict]) -> AsyncGenerator[str, None]:
    from mistralai.client import Mistral
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    stream = await client.chat.stream_async(model=MODEL, messages=full_messages, max_tokens=2048)
    async for chunk in stream:
        delta = chunk.data.choices[0].delta.content
        if delta:
            yield delta


async def stream_llm(messages: list[dict]) -> AsyncGenerator[str, None]:
    if PROVIDER == "claude":
        async for t in stream_claude(messages):
            yield t
    elif PROVIDER == "openai":
        async for t in stream_openai(messages):
            yield t
    elif PROVIDER == "mistral":
        async for t in stream_mistral(messages):
            yield t
    else:
        yield f"Provider inconnu : {PROVIDER}"


# ── App FastAPI ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_destinations()
    yield


app = FastAPI(title="MYA", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ── Routes API ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[dict]   # [{"role": "user"|"assistant", "content": "..."}]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats():
    return {
        "destinations_count": len(_destinations),
        "provider": PROVIDER,
        "model": MODEL,
        "data_available": DESTINATIONS_FILE.exists(),
        "scrape_running": _scrape_state["running"],
        "scrape_last_run": _scrape_state["last_run"],
    }


@app.post("/api/scrape")
async def trigger_scrape():
    if _scrape_state["running"]:
        return {"status": "already_running"}
    asyncio.create_task(_run_scraper())
    return {"status": "started"}


@app.get("/api/scrape/status")
def scrape_status():
    return {
        "running": _scrape_state["running"],
        "last_run": _scrape_state["last_run"],
        "last_count": _scrape_state["last_count"],
        "error": _scrape_state["error"],
    }


@app.post("/api/reload")
def reload_data():
    load_destinations()
    return {"destinations_count": len(_destinations)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    messages = req.messages
    if not messages:
        return {"error": "No messages"}

    # Enrichit le dernier message utilisateur avec le contexte
    last_user_idx = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i]["role"] == "user"),
        None
    )
    augmented_messages = [m.copy() for m in messages]
    if last_user_idx is not None:
        query = messages[last_user_idx]["content"]
        context = build_context(query)
        if context:
            augmented_messages[last_user_idx] = {
                "role": "user",
                "content": (
                    f"[DONNÉES DESTINATIONS DISPONIBLES]\n{context}\n\n"
                    f"[QUESTION]\n{query}"
                )
            }

    async def event_generator():
        try:
            async for token in stream_llm(augmented_messages):
                # SSE format
                data = json.dumps({"token": token})
                yield f"data: {data}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ── Frontend statique ─────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
