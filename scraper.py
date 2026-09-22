"""
Scraper pour mya.epitech.eu
─────────────────────────────────────────────────
Appelle directement l'API publique de MYA (pas de login, pas de navigateur requis)
et extrait toutes les destinations partenaires avec leurs métadonnées structurées
et le détail complet de chaque fiche (overview, administratif, logement, cours, coût...).

Usage:
    python scraper.py
"""

import asyncio
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.panel import Panel

console = Console()
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "destinations.json"

API_BASE = "https://mya.epitech.eu/api"
SITE_BASE = "https://mya.epitech.eu"
CONCURRENCY = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": SITE_BASE,
    "Referer": f"{SITE_BASE}/programs",
}


# ── Conversion HTML (Quill) → texte brut ───────────────────────────────────────

_BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "blockquote", "h1", "h2", "h3", "h4"}


class _HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.chunks.append("\n")
        elif tag == "li":
            self.chunks.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")
        elif tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.chunks.append(f" ({self._href})")
            self._href = None
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        self.chunks.append(data)

    def get_text(self) -> str:
        text = "".join(self.chunks)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
        return text.strip()


def html_to_text(field) -> str:
    if not field or not isinstance(field, str):
        return ""
    parser = _HTMLToText()
    parser.feed(field)
    return parser.get_text()


# ── Extraction structurée d'une université ─────────────────────────────────────

def parse_university(raw: dict) -> dict:
    text_parts = []
    for key, label in [
        ("overview", "Présentation"),
        ("administrative", "Démarches administratives (dossier, visa, assurance)"),
        ("accomodation", "Logement"),
        ("courses", "Cours et calendrier académique"),
        ("cost", "Coût de la vie / budget"),
    ]:
        text = html_to_text(raw.get(key))
        if text:
            text_parts.append(f"### {label}\n{text}")
    full_text = "\n\n".join(text_parts)

    dest = {
        "id": raw.get("id"),
        "url": f"{SITE_BASE}/university/{raw.get('id')}",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "university_name": (raw.get("name") or "").strip(),
        "country": raw.get("country"),
        "language": raw.get("language"),
        "diploma": raw.get("diploma"),
        "spots": raw.get("spots"),
        "gpa_requirement": raw.get("gpa"),
        "extra_charge_cents": raw.get("extracharge"),
        "erasmus": raw.get("erasmus"),
        "semester": raw.get("semester"),
        "specializations": raw.get("specializations") or [],
        "display": raw.get("display"),
        "updated_at": raw.get("updatedAt"),
        "images": [img for img in (raw.get("image1"), raw.get("image2"), raw.get("image3")) if img],
        "full_text": full_text,
    }
    return {k: v for k, v in dest.items() if v is not None and v != "" and v != []}


# ── Appels API ──────────────────────────────────────────────────────────────────

async def fetch_all_universities() -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(f"{API_BASE}/universities")
        resp.raise_for_status()
        listing = resp.json()
        console.print(f"[cyan]{len(listing)} universités trouvées, récupération du détail de chacune...[/cyan]")

        destinations = [None] * len(listing)
        semaphore = asyncio.Semaphore(CONCURRENCY)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Récupération des fiches détaillées...", total=len(listing))

            async def fetch_one(index: int, uid: int):
                async with semaphore:
                    try:
                        r = await client.get(f"{API_BASE}/universities/{uid}")
                        r.raise_for_status()
                        destinations[index] = parse_university(r.json())
                    except Exception as exc:
                        console.print(f"[red]Échec pour l'université {uid}: {exc}[/red]")
                        destinations[index] = parse_university({"id": uid, **{
                            k: v for k, v in listing[index].items()
                        }})
                    progress.advance(task)

            await asyncio.gather(*(
                fetch_one(i, item["id"]) for i, item in enumerate(listing)
            ))

    return [d for d in destinations if d]


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    console.print(Panel.fit(
        "[bold cyan]MYA-Chatbot — mya.epitech.eu[/bold cyan]\n"
        "Scraper de destinations internationales",
        border_style="cyan"
    ))

    console.print("\n[bold green]Démarrage du scraping via API...[/bold green]")
    destinations = await fetch_all_universities()

    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": f"{SITE_BASE}/programs",
        "count": len(destinations),
        "destinations": destinations,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    console.print(
        f"\n[bold green]✓ {len(destinations)} destinations sauvegardées → {OUTPUT_FILE}[/bold green]"
    )


if __name__ == "__main__":
    asyncio.run(main())
