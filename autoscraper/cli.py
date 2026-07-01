"""Command line voor de auto-scraper."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import sources
from .brands import canonical_make
from .models import Car
from .report import render
from .score import score_breakdown
from .storage import dedup, save_csv, save_json

log = logging.getLogger("autoscraper")


def _fmt(car: Car) -> str:
    price = ("€" + f"{car.price:,}".replace(",", ".")) if car.price else "?"
    return " | ".join([
        f"{car.score if car.score is not None else '--':>3}",
        f"{car.title} {car.version}".strip()[:46].ljust(46),
        price.rjust(9),
        str(car.year or "?"),
        f"{(car.mileage_km or 0):,}".replace(",", ".").rjust(8) + " km",
        f"{car.range_km or '?'} km".rjust(7),
        (car.location or "")[:20],
    ])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autoscraper", description="Zoek tweedehands elektrische autos.")
    p.add_argument("--price-from", type=int, default=20000, help="minimumprijs (standaard 20000)")
    p.add_argument("--price-to", type=int, default=43000, help="maximumprijs (standaard 43000)")
    p.add_argument("--min-range", type=int, default=450, help="minimaal rijbereik in km (standaard 300)")
    p.add_argument("--max-mileage", type=int, default=None, help="maximale kilometerstand")
    p.add_argument("--min-year", type=int, default=None, help="minimaal bouwjaar")
    p.add_argument("-n", "--limit", type=int, default=1000, help="max aantal autos per bron (standaard 1000)")
    p.add_argument("-s", "--source", default="all",
                   choices=[*sources.available(), "dealers", "all"],
                   help="bron of groep: dealers (standaard, erkende BE-dealers), all (ook NL/DE/FR), of een bronnaam")
    p.add_argument("-o", "--out", default="output", help="uitvoermap")
    p.add_argument("-f", "--format", default="both", choices=["json", "csv", "both"], help="uitvoerformaat")
    p.add_argument("-v", "--verbose", action="store_true", help="uitgebreide logging")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    groups = {"dealers": ["autoscout", "gocar", "autohero"], "all": sources.available()}
    src_names = groups.get(args.source, [args.source])
    log.info("zoek: elektrisch, €%s-%s, bereik >= %s km, bronnen: %s",
             args.price_from, args.price_to, args.min_range, ", ".join(src_names))

    all_cars: list[Car] = []
    for name in src_names:
        scraper = sources.get_scraper(name)
        try:
            cars = list(scraper.search(
                price_from=args.price_from, price_to=args.price_to, min_range=args.min_range,
                max_mileage=args.max_mileage, min_year=args.min_year, limit=args.limit))
            log.info("  %s: %s autos", name, len(cars))
            all_cars.extend(cars)
        except Exception as exc:
            log.warning("  %s faalde: %s", name, exc)

    for car in all_cars:
        car.make = canonical_make(car.make)  # zelfde merk, zelfde naam over bronnen heen
    cars = dedup(all_cars)
    for car in cars:
        bd = score_breakdown(car)
        if bd:
            car.score = bd["score"]
            car.score_parts = bd["components"]
    log.info("%s autos gevonden (na ontdubbelen)", len(cars))
    if not cars:
        log.warning("geen autos gevonden")
        return 1

    cars.sort(key=lambda c: (-(c.score or 0), -(c.range_km or 0)))
    out = Path(args.out)
    if args.format in ("json", "both"):
        save_json(cars, out / "ev.json")
    if args.format in ("csv", "both"):
        save_csv(cars, out / "ev.csv")

    country = {"autoscout": "BE", "gocar": "BE", "autohero": "BE", "autoscout-nl": "NL",
               "autoscout-de": "DE", "autoscout-fr": "FR"}
    markets = sorted({country.get(s, "?") for s in src_names})
    mtext = "België" if markets == ["BE"] else "/".join(markets)
    subtitle = f"elektrisch · €{args.price_from:,}–€{args.price_to:,} · ≥ {args.min_range} km · {mtext}".replace(",", ".")
    report = render(cars, out / "ev.html", title="EV-occasies voor Mattias", subtitle=subtitle)
    log.info("rapport: %s", report)

    for car in cars[:25]:
        print(_fmt(car))
    if len(cars) > 25:
        print(f"... en nog {len(cars) - 25} meer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
