"""Register van beschikbare autobronnen."""

from __future__ import annotations

from ..base import BaseCarScraper
from .autohero import AutoheroScraper
from .autoscout import AutoScoutDE, AutoScoutFR, AutoScoutNL, AutoScoutScraper
from .gocar import GocarScraper

# Enkel erkende dealers. De particuliere kanalen (2dehands, Marktplaats) staan
# nog in tweedehands.py maar zijn bewust niet geregistreerd.
REGISTRY: dict[str, type[BaseCarScraper]] = {
    AutoScoutScraper.name: AutoScoutScraper,
    AutoScoutNL.name: AutoScoutNL,
    AutoScoutDE.name: AutoScoutDE,
    AutoScoutFR.name: AutoScoutFR,
    GocarScraper.name: GocarScraper,
    AutoheroScraper.name: AutoheroScraper,
}


def get_scraper(name: str) -> BaseCarScraper:
    try:
        return REGISTRY[name]()
    except KeyError:
        raise SystemExit(f"onbekende bron '{name}'. beschikbaar: {', '.join(available())}")


def available() -> list[str]:
    return sorted(REGISTRY)
