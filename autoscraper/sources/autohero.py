"""Autohero.com-scraper (AUTO1) via de retail-customer GraphQL-gateway.

Autohero koopt wagens op, knapt ze op en verkoopt ze zelf, dus elke advertentie
is een erkende dealer (Autohero zelf). De zoekresultaten komen van een GraphQL-
veld `searchAdV9AdsV2` dat ruwe JSON teruggeeft ({total, data:[...]}). We
filteren land + elektrisch (fuelType 1044) in de query; prijs/km/bouwjaar
client-side. Bereik geeft Autohero niet mee, dus dat schatten we (estimate.py).
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


class AutoheroScraper(BaseCarScraper):
    name = "autohero"
    BASE = "https://www.autohero.com"
    GATEWAY = "https://www.autohero.com/v1/retail-customer-gateway/graphql/SearchAds"
    COUNTRY = "BE"
    LOCALE = "nl-be"
    FUEL_ELECTRIC = 1044  # fuelType-code voor elektrisch (co2 = 0)
    PER_PAGE = 100        # gateway-maximum
    MAX_PAGES = 6

    def __init__(self, http: Http | None = None) -> None:
        self.http = http or Http()
        self.headers = {
            "Accept": "application/json",
            "Origin": self.BASE,
            "Referer": f"{self.BASE}/{self.LOCALE}/auto/",
        }

    def _query(self, offset: int) -> str:
        search = (
            '{filter: {op: "and", value: ['
            f'{{field: "countryCode", op: "eq", value: "{self.COUNTRY}"}}, '
            f'{{field: "fuelType", op: "eq", value: {self.FUEL_ELECTRIC}}}'
            ']}, '
            f'sort: "most_popular", limit: {self.PER_PAGE}, offset: {offset}, '
            'properties: {includeProspective: false}}'
        )
        return "query SearchAds { searchAdV9AdsV2(search: %s) }" % search

    def search(self, *, price_from, price_to, min_range=0, max_mileage=None,
               min_year=None, limit=50) -> Iterator[Car]:
        seen: set[str] = set()
        collected = 0
        offset = 0
        for _ in range(self.MAX_PAGES):
            if collected >= limit:
                return
            payload = {"operationName": "SearchAds", "variables": {}, "query": self._query(offset)}
            try:
                resp = self.http.post(self.GATEWAY, json=payload, headers=self.headers)
            except Exception as exc:
                log.warning("Autohero: ophalen faalde (offset %s): %s", offset, exc)
                return
            if resp.status_code != 200:
                log.warning("Autohero: HTTP %s", resp.status_code)
                return
            try:
                body = resp.json()
                result = (body.get("data") or {}).get("searchAdV9AdsV2") or {}
            except ValueError:
                return
            if body.get("errors"):
                log.warning("Autohero: GraphQL-fout: %s", body["errors"][:1])
                return
            ads = result.get("data") or []
            total = result.get("total") or 0
            if not ads:
                return

            for item in ads:
                car = self._to_car(item)
                if car is None or car.car_id in seen:
                    continue
                seen.add(car.car_id)
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
            offset += self.PER_PAGE
            if offset >= total:
                return

    def _to_car(self, item: dict) -> Car | None:
        car_id = str(item.get("id") or "")
        make = item.get("manufacturer") or ""
        model = item.get("model") or ""
        if not (car_id and (make or model)):
            return None

        version = " ".join(x for x in (item.get("subType"), item.get("subTypeExtra")) if x).strip()
        rng = estimate_range(make, model, version)
        title = item.get("carUrlTitle") or f"{make}-{model}".lower().replace(" ", "-")
        branch = item.get("esBranch") or {}
        location = " ".join(str(x) for x in (branch.get("zipcode"), branch.get("city")) if x)
        image = self._image(item.get("mainImageUrl"))

        return Car(
            source=self.name,
            car_id=car_id,
            make=make,
            model=model,
            version=version[:160],
            price=self._price(item.get("offerPrice")),
            year=item.get("firstRegistrationYear") or self._year(item.get("registration")),
            mileage_km=self._int((item.get("mileage") or {}).get("distance")),
            range_km=rng,
            range_estimated=rng is not None,
            power_kw=self._int(item.get("kw")),
            fuel="Elektrisch",
            transmission="Automaat",  # EV's bij Autohero zijn automaat
            location=location,
            url=f"{self.BASE}/{self.LOCALE}/{title}/id/{car_id}/",
            image_url=image,
            images=[image] if image else [],
            seller="Autohero",
        )

    # Geldige maat-tokens uit de frontend: de bestandsnaam krijgt een prefix.
    # 306x204- is wat de site zelf voor de grid-thumbnails gebruikt.
    IMAGE_SIZE = "306x204-"

    @classmethod
    def _image(cls, url) -> str | None:
        """Vul de {size}-placeholder in de image-URL in, anders blijft de foto leeg."""
        if not url:
            return None
        return url.replace("{size}", cls.IMAGE_SIZE)

    @staticmethod
    def _price(offer) -> int | None:
        if not isinstance(offer, dict):
            return None
        minor = offer.get("amountMinorUnits")
        conv = offer.get("conversionMajor") or 100
        try:
            return int(minor) // int(conv)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _year(text) -> int | None:
        m = re.match(r"(\d{4})", str(text or ""))
        return int(m.group(1)) if m else None

    @staticmethod
    def _int(value) -> int | None:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
