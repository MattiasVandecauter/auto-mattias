"""Autos wegschrijven naar JSON en/of CSV, met de-duplicatie."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from .models import Car

log = logging.getLogger(__name__)

CSV_FIELDS = [
    "source", "car_id", "make", "model", "version", "price", "year",
    "mileage_km", "range_km", "power_kw", "fuel", "transmission",
    "location", "seller", "url", "scraped_at",
]


def _signature(car: Car) -> tuple | None:
    """Vingerafdruk van de fysieke wagen, of None als er te weinig info is.

    Merk + model + bouwjaar + exacte km + prijs. Twee tweedehandswagens met
    identieke kilometerstand én prijs zijn in de praktijk dezelfde auto, ook al
    staan ze op meerdere bronnen (dealers publiceren op AutoScout24 én Gocar).
    """
    if car.year is None or car.mileage_km is None or car.price is None:
        return None
    make = (car.make or "").strip().lower()
    if not make:
        return None
    return (make, (car.model or "").strip().lower(), car.year, car.mileage_km, car.price)


def _quality(car: Car) -> tuple:
    # Bij dezelfde wagen het rijkste record houden: exact bereik wint van geschat,
    # dan meer fotos, dan meer tekst in de versie.
    return (0 if car.range_estimated else 1, len(car.images or []), len(car.version or ""))


def dedup(cars: list[Car]) -> list[Car]:
    """Ontdubbel eerst exact (zelfde bron + advertentie), dan dezelfde wagen over bronnen heen."""
    by_key: dict[str, Car] = {}
    for car in cars:
        by_key.setdefault(car.key, car)  # zelfde advertentie maar 1x

    best: dict[tuple, Car] = {}
    singles: list[Car] = []  # te weinig info om veilig te mergen: houden zoals ze zijn
    for car in by_key.values():
        sig = _signature(car)
        if sig is None:
            singles.append(car)
        elif sig not in best or _quality(car) > _quality(best[sig]):
            best[sig] = car
    return singles + list(best.values())


def save_json(cars: list[Car], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.to_dict() for c in cars], indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("%s autos weggeschreven naar %s", len(cars), path)


def save_csv(cars: list[Car], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for car in cars:
            writer.writerow(car.to_dict())
    log.info("%s autos weggeschreven naar %s", len(cars), path)
