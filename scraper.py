"""
Scraper pour epitech.globalcampus.app/programs/
─────────────────────────────────────────────────
Appelle directement l'API publique (pas de login, pas de navigateur requis)
et extrait les 143 destinations avec leurs métadonnées structurées.

Usage:
    python scraper.py
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.panel import Panel

console = Console()
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "destinations.json"

API_BASE = "https://epitech.campuscommunity.app/api/v2/public/programs"
SITE_BASE = "https://epitech.globalcampus.app/programs"
TYPE_IDS = "16,17,3"
PAGE_SIZE = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://epitech.globalcampus.app",
    "Referer": "https://epitech.globalcampus.app/programs/",
}


# ── Extraction du texte riche (format TipTap/ProseMirror) ─────────────────────

def extract_text(node) -> str:
    """Extrait récursivement le texte brut d'un nœud TipTap."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        if node.get("type") == "hardBreak":
            return "\n"
        parts = [extract_text(child) for child in node.get("content", [])]
        sep = "\n" if node.get("type") in ("paragraph", "bulletList", "orderedList", "listItem", "blockquote") else ""
        return sep.join(parts)
    if isinstance(node, list):
        return "\n".join(extract_text(item) for item in node)
    return ""


def richtext_to_str(field) -> str:
    """Convertit un champ rich-text (dict JSON ou string JSON) en texte brut."""
    if not field:
        return ""
    if isinstance(field, str):
        try:
            field = json.loads(field)
        except Exception:
            return field.strip()
    return extract_text(field).strip()


# ── Extraction structurée d'un programme ──────────────────────────────────────

def parse_program(raw: dict) -> dict:
    """Transforme un objet programme brut en dict propre pour le chatbot."""

    # Pays depuis locations
    locations = raw.get("locations") or []
    country = ", ".join(loc["label"] for loc in locations if loc.get("label"))

    # Langue, places, spécialisations, etc. depuis les tags
    language = spots = gpa = lang_test = dual_degree = None
    specializations = []
    for tag in raw.get("tags") or []:
        parent_name = (tag.get("parent") or {}).get("name", "")
        tag_name = tag.get("name", "")
        if parent_name == "Language of instruction":
            language = tag_name
        elif parent_name == "Available Spots":
            spots = tag_name
        elif parent_name == "GPA Requirement":
            gpa = tag_name
        elif parent_name == "Language Test or Tepitech >750 Required":
            lang_test = tag_name
        elif parent_name == "Dual degree/certificate proposed":
            dual_degree = tag_name
        elif parent_name == "Specializations":
            specializations.append(tag_name)

    # Type de programme (Erasmus, Fee-Paying, All Other)
    type_id = raw.get("typeId")
    program_type = {16: "Erasmus+", 17: "Fee-Paying", 3: "All Other Programs"}.get(type_id, str(type_id))

    # Durée — termName peut être top-level ou dans itinerary selon la réponse API
    itinerary = raw.get("itinerary") or {}
    term = raw.get("termName") or itinerary.get("termName") or []
    duration = ", ".join(term) if isinstance(term, list) else str(term)

    # Descriptions textuelles
    description = richtext_to_str(raw.get("description"))

    # Les champs rich-text peuvent être top-level ou dans itinerary
    itinerary_text_parts = []
    for key, label in [
        ("itinerary", "Itinéraire"),
        ("costFunding", "Coût / financement"),
        ("eligibility", "Conditions d'éligibilité"),
        ("housingType", "Logement"),
        ("whatsIncluded", "Ce qui est inclus"),
        ("languageOfInstruction", "Langue d'enseignement"),
    ]:
        val = raw.get(key) or itinerary.get(key)
        if val and isinstance(val, dict) and val.get("type") == "doc":
            text = richtext_to_str(val)
            if text:
                itinerary_text_parts.append(f"### {label}\n{text}")
    itinerary_text = "\n\n".join(itinerary_text_parts)

    full_text = "\n\n".join(filter(None, [description, itinerary_text]))

    dest = {
        "url": f"{SITE_BASE}/{raw['id']}",
        "scraped_at": datetime.utcnow().isoformat(),
        "university_name": raw.get("name", ""),
        "country": country,
        "language": language,
        "spots": spots,
        "duration": duration,
        "program_type": program_type,
        "specializations": specializations,
        "gpa_requirement": gpa,
        "language_test_required": lang_test,
        "dual_degree": dual_degree,
        "price_cents": raw.get("priceCents"),
        "start_date": raw.get("startDate"),
        "end_date": raw.get("endDate"),
        "image_url": raw.get("imageUrl"),
        "full_text": full_text[:10000],
    }
    # Retire les champs None pour garder le JSON propre
    return {k: v for k, v in dest.items() if v is not None and v != "" and v != []}


# ── Appels API paginés ────────────────────────────────────────────────────────

async def fetch_all_programs() -> list[dict]:
    destinations = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        # 1re requête pour connaître le nombre de pages
        params = {"typeId": TYPE_IDS, "term": "", "page": 1, "limit": PAGE_SIZE}
        resp = await client.get(API_BASE, params=params)
        resp.raise_for_status()
        body = resp.json()

        # L'API peut encapsuler dans {"data": {...}} ou répondre à plat
        if "data" in body and isinstance(body["data"], dict):
            root = body["data"]
        else:
            root = body

        meta = root.get("meta", {})
        total_pages = meta.get("totalPages", 1)
        total_items = meta.get("totalItems", "?")
        console.print(f"[cyan]{total_items} programmes trouvés sur {total_pages} pages[/cyan]")

        programs_page1 = root.get("programs", [])

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Récupération des programmes...", total=total_pages)

            # Page 1 déjà chargée
            for raw in programs_page1:
                destinations.append(parse_program(raw))
            progress.advance(task)

            # Pages suivantes
            for page in range(2, total_pages + 1):
                params = {"typeId": TYPE_IDS, "term": "", "page": page, "limit": PAGE_SIZE}
                resp = await client.get(API_BASE, params=params)
                resp.raise_for_status()
                body = resp.json()
                root = body["data"] if "data" in body and isinstance(body["data"], dict) else body
                for raw in root.get("programs", []):
                    destinations.append(parse_program(raw))
                progress.advance(task)

    return destinations


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    console.print(Panel.fit(
        "[bold cyan]MYA-Chatbot — Epitech GlobalCampus[/bold cyan]\n"
        "Scraper de destinations internationales",
        border_style="cyan"
    ))

    console.print("\n[bold green]Démarrage du scraping via API...[/bold green]")
    destinations = await fetch_all_programs()

    output = {
        "scraped_at": datetime.utcnow().isoformat(),
        "source": "https://epitech.globalcampus.app/programs/",
        "count": len(destinations),
        "destinations": destinations,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    console.print(
        f"\n[bold green]✓ {len(destinations)} destinations sauvegardées → {OUTPUT_FILE}[/bold green]"
    )


if __name__ == "__main__":
    asyncio.run(main())
