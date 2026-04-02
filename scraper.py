"""
Scraper pour epitech.globalcampus.app/programs/
─────────────────────────────────────────────────
Extrait toutes les destinations disponibles (site public, pas de login requis).

Usage:
    python scraper.py
    python scraper.py --visible   # affiche le navigateur (debug)
"""

import asyncio
import json
import sys
import re
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

console = Console()
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = DATA_DIR / "destinations.json"
BASE_URL = "https://epitech.globalcampus.app"
PROGRAMS_URL = BASE_URL + "/programs/"


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ── Extraction d'une destination ──────────────────────────────────────────────

async def extract_destination_detail(page, url: str) -> dict:
    """Extrait toutes les infos d'une page de destination."""
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except PWTimeout:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    await page.wait_for_timeout(1000)

    data = {"url": url, "scraped_at": datetime.utcnow().isoformat()}

    # Titre / nom de l'université
    for sel in ["h1", "[class*='title']", "[class*='name']", "[class*='university']"]:
        el = page.locator(sel).first
        if await el.count() > 0:
            data["university_name"] = clean(await el.inner_text())
            break

    # Texte complet de la page
    body_text = clean(await page.locator("body").inner_text())
    data["full_text"] = body_text[:8000]

    # Extraction structurée par patterns de texte
    patterns = {
        "country": r"(?:pays|country)[:\s]+([^\n\r,]+)",
        "city": r"(?:ville|city)[:\s]+([^\n\r,]+)",
        "language": r"(?:langue|language)[:\s]+([^\n\r,]+)",
        "spots": r"(?:places?|spots?|nb[_\s]places?)[:\s]+(\d+)",
        "duration": r"(?:durée?|duration)[:\s]+([^\n\r,]+)",
        "level": r"(?:niveau|level)[:\s]+([^\n\r,]+)",
        "semester": r"(?:semestre?|semester)[:\s]+([^\n\r,]+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, body_text, re.IGNORECASE)
        if m:
            data[key] = clean(m.group(1))

    # Tableaux
    tables = await page.locator("table").all()
    table_data = []
    for table in tables[:5]:
        rows = await table.locator("tr").all()
        t = []
        for row in rows:
            cells = await row.locator("td, th").all()
            t.append([clean(await c.inner_text()) for c in cells])
        table_data.append(t)
    if table_data:
        data["tables"] = table_data

    # Images
    imgs = await page.locator("img[src]").all()
    data["images"] = [await img.get_attribute("src") for img in imgs[:10]]

    return data


# ── Listing de toutes les destinations ───────────────────────────────────────

async def scrape_all_destinations(page) -> list[dict]:
    """Navigue sur /programs/ et collecte toutes les destinations (pagination incluse)."""
    destinations = []
    api_data = []
    captured_urls = set()

    async def handle_response(response):
        url = response.url
        if any(kw in url for kw in ["destination", "partner", "universit", "api", "data", "program"]):
            if url not in captured_urls and "json" in response.headers.get("content-type", ""):
                captured_urls.add(url)
                try:
                    body = await response.json()
                    api_data.append({"url": url, "data": body})
                    console.print(f"[green]API interceptée : {url}[/green]")
                except Exception:
                    pass

    page.on("response", handle_response)

    # Charge la page initiale
    console.print(f"[dim]Chargement de {PROGRAMS_URL}[/dim]")
    await page.goto(PROGRAMS_URL, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3000)

    # Scroll pour déclencher le lazy loading
    for _ in range(10):
        await page.keyboard.press("End")
        await page.wait_for_timeout(500)

    # Gestion de la pagination : clique sur "suivant" tant que possible
    page_num = 1
    while True:
        # Collecte les liens de destinations sur la page courante
        links = await page.locator("a[href]").all()
        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            if href.startswith("/"):
                href = BASE_URL + href
            if BASE_URL in href and any(
                kw in href.lower()
                for kw in ["destination", "partner", "universit", "school", "exchange", "program", "/d/", "/p/"]
            ):
                captured_urls.add(href)

        # Cherche un bouton "page suivante"
        next_btn = page.locator(
            "a[rel='next'], button[aria-label*='next'], button[aria-label*='suivant'], "
            "[class*='next']:not([disabled]), [class*='pagination'] a:last-child"
        ).first
        if await next_btn.count() == 0 or not await next_btn.is_enabled():
            break

        page_num += 1
        console.print(f"[dim]Page {page_num}...[/dim]")
        await next_btn.click()
        await page.wait_for_timeout(2000)
        for _ in range(5):
            await page.keyboard.press("End")
            await page.wait_for_timeout(300)

    # URLs de destinations collectées (sans la page de listing elle-même)
    dest_urls = {
        u for u in captured_urls
        if u != PROGRAMS_URL and u != BASE_URL + "/"
    }

    # Si des données API ont été capturées, on les utilise directement
    if api_data:
        console.print(f"[green]{len(api_data)} réponses API capturées[/green]")
        for entry in api_data:
            raw = entry["data"]
            if isinstance(raw, list):
                destinations.extend(raw)
            elif isinstance(raw, dict):
                for key in ["data", "results", "items", "destinations", "universities", "programs"]:
                    if key in raw and isinstance(raw[key], list):
                        destinations.extend(raw[key])
                        break
                else:
                    destinations.append(raw)

    # Scrape chaque page de destination individuelle
    console.print(f"[cyan]{len(dest_urls)} pages de destinations trouvées[/cyan]")

    if dest_urls:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scraping destinations...", total=len(dest_urls))
            for url in dest_urls:
                progress.update(task, description=f"[cyan]{url[-60:]}[/cyan]")
                try:
                    detail = await extract_destination_detail(page, url)
                    destinations.append(detail)
                except Exception as e:
                    console.print(f"[red]Erreur {url}: {e}[/red]")
                progress.advance(task)
    elif not destinations:
        # Fallback : texte complet de la page
        text = clean(await page.locator("body").inner_text())
        destinations.append({
            "url": PROGRAMS_URL,
            "full_text": text[:10000],
            "scraped_at": datetime.utcnow().isoformat(),
            "note": "Page complète (pas de détails individuels trouvés)"
        })

    return destinations


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    headless = "--visible" not in sys.argv

    console.print(Panel.fit(
        "[bold cyan]MYA-Chatbot — Epitech GlobalCampus[/bold cyan]\n"
        "Scraper de destinations internationales",
        border_style="cyan"
    ))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        console.print("\n[bold green]Démarrage du scraping...[/bold green]")
        destinations = await scrape_all_destinations(page)

        output = {
            "scraped_at": datetime.utcnow().isoformat(),
            "source": PROGRAMS_URL,
            "count": len(destinations),
            "destinations": destinations,
        }
        OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        console.print(
            f"\n[bold green]✓ {len(destinations)} destinations sauvegardées → {OUTPUT_FILE}[/bold green]"
        )

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
