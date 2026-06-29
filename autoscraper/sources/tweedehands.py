"""2dehands.be-scraper via de publieke LRP-zoek-API (JSON).

2dehands geeft geen rijbereik mee, dus dat schatten we uit merk/model
(estimate.py). Elektrisch wordt via de API gefilterd, prijs/km/bouwjaar
client-side.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from ..base import BaseCarScraper
from ..estimate import estimate_range
from ..http import Http
from ..models import Car

log = logging.getLogger(__name__)

_MAKE_FIX = {
    "Bmw": "BMW", "Mg": "MG", "Ds": "DS", "Mini": "MINI", "Cupra": "CUPRA",
    "Seat": "SEAT", "Byd": "BYD", "Kia": "Kia", "Byton": "Byton",
}

# Meerwoordige merken eerst, zodat 'Mercedes-Benz' vóór 'Mercedes' matcht.
_BRANDS = [
    "Mercedes-Benz", "Alfa Romeo", "Land Rover", "Lynk & Co",
    "Tesla", "Volkswagen", "Audi", "BMW", "Volvo", "Polestar", "Cupra", "Seat",
    "Skoda", "Renault", "Peugeot", "Citroën", "Citroen", "Opel", "Fiat",
    "Hyundai", "Kia", "Nissan", "Toyota", "Honda", "Mazda", "Ford", "MG", "BYD",
    "Aiways", "Xpeng", "Zeekr", "Leapmotor", "Nio", "Smart", "Mini", "Jaguar",
    "Porsche", "Lexus", "Subaru", "Mitsubishi", "Dacia", "Mercedes", "Maserati",
    "Lucid", "Genesis", "Lotus", "VinFast", "Maxus", "Microlino", "DS",
]


def _parse_make_model(title: str) -> tuple[str, str]:
    """Haal merk + model uit de advertentietitel (die het betrouwbaar bevat)."""
    t = (title or "").strip()
    low = t.lower()
    for brand in _BRANDS:
        bl = brand.lower()
        if low == bl or low.startswith(bl + " "):
            rest = t[len(brand):].strip()
            return brand, (rest.split(" ", 1)[0] if rest else "")
    parts = t.split()
    return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")


class TweedehandsScraper(BaseCarScraper):
    name = "tweedehands"
    API = "https://www.2dehands.be/lrp/api/search"
    BASE = "https://www.2dehands.be"
    PER_PAGE = 30
    MAX_PAGES = 12

    def __init__(self, http: Http | None = None) -> None:
        self.http = http or Http()

    def search(self, *, price_from, price_to, min_range=0, max_mileage=None,
               min_year=None, limit=50) -> Iterator[Car]:
        seen: set[str] = set()
        collected = 0
        offset = 0
        page = 0
        while collected < limit and page < self.MAX_PAGES:
            params = {
                "l1CategoryId": 91,
                "attributesByKey[]": "fuel:Elektrisch",
                "limit": self.PER_PAGE,
                "offset": offset,
            }
            try:
                resp = self.http.get(self.API, params=params, headers={"Accept": "application/json"})
            except Exception as exc:
                log.warning("2dehands: ophalen faalde (offset %s): %s", offset, exc)
                break
            if resp.status_code != 200:
                log.warning("2dehands: HTTP %s", resp.status_code)
                break
            try:
                listings = resp.json().get("listings") or []
            except ValueError:
                break
            if not listings:
                break

            new = 0
            for item in listings:
                car = self._to_car(item)
                if car is None or car.car_id in seen:
                    continue
                seen.add(car.car_id)
                new += 1
                if car.price is None or car.price < price_from or car.price > price_to:
                    continue
                if min_range and car.range_km is not None and car.range_km < min_range:
                    continue
                if max_mileage and (car.mileage_km or 0) > max_mileage:
                    continue
                if min_year and (car.year or 0) < min_year:
                    continue
                yield car
                collected += 1
                if collected >= limit:
                    return
            if new == 0:
                break
            offset += self.PER_PAGE
            page += 1

    def _to_car(self, item: dict) -> Car | None:
        attrs: dict[str, str] = {}
        for a in (item.get("attributes") or []) + (item.get("extendedAttributes") or []):
            attrs.setdefault(a.get("key"), a.get("value"))
        car_id = str(item.get("itemId") or "")
        vip = item.get("vipUrl") or ""
        make, model = _parse_make_model(item.get("title") or "")
        if make not in _BRANDS:
            url_make = self._make_from_url(vip)
            if url_make and "overige" not in url_make.lower():
                make, model = url_make, (model or attrs.get("model") or "")
        if not (car_id and make):
            return None

        version = (item.get("title") or "").strip()
        prefix = f"{make} {model}".strip().lower()
        if prefix and version.lower().startswith(prefix):
            version = version[len(prefix):].lstrip(" -|·").strip()

        pc = (item.get("priceInfo") or {}).get("priceCents")
        price = pc // 100 if isinstance(pc, int) and pc > 0 else None
        rng = estimate_range(make, model, item.get("title"))
        images = [("https:" + u if u.startswith("//") else u) for u in (item.get("imageUrls") or [])]
        location = item.get("location") or {}

        return Car(
            source=self.name,
            car_id=car_id,
            make=make,
            model=model,
            version=version[:160],
            price=price,
            year=self._num(attrs.get("constructionYear")),
            mileage_km=self._num(attrs.get("mileage")),
            range_km=rng,
            range_estimated=rng is not None,
            power_kw=self._num(attrs.get("enginePowerKW")),
            fuel="Elektrisch",
            transmission=attrs.get("transmission") or "",
            location=location.get("cityName") or "",
            url=self.BASE + vip if vip.startswith("/") else vip,
            image_url=images[0] if images else None,
            images=images[:8],
            seller=(item.get("sellerInformation") or {}).get("sellerName"),
        )

    @staticmethod
    def _make_from_url(vip: str) -> str:
        # /v/auto-s/<merk>/<id>-...
        parts = [p for p in vip.split("/") if p]
        if "auto-s" in parts:
            i = parts.index("auto-s")
            if i + 1 < len(parts):
                raw = parts[i + 1].replace("-", " ").title()
                return _MAKE_FIX.get(raw, raw)
        return ""

    @staticmethod
    def _num(text) -> int | None:
        m = re.search(r"\d[\d.\s]*", str(text or ""))
        if not m:
            return None
        digits = re.sub(r"[.\s]", "", m.group())
        return int(digits) if digits else None


class MarktplaatsScraper(TweedehandsScraper):
    name = "marktplaats"
    API = "https://www.marktplaats.nl/lrp/api/search"
    BASE = "https://www.marktplaats.nl"
