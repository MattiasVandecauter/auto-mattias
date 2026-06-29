"""Gocar.be-scraper via de Meilisearch-zoek-API (JSON).

Gocar is een marktplaats van erkende Belgische dealers: de frontend praat met
een Meilisearch-index (`search.gocar.be/multi-search`) met een publieke
search-only sleutel. We filteren op erkende verkopers (Professioneel),
elektrisch en prijs in de query; bereik schatten we uit merk/model
(estimate.py), want Gocar geeft geen WLTP-bereik mee.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from ..base import BaseCarScraper
from ..estimate import estimate_range
from ..http import Http
from ..models import Car

log = logging.getLogger(__name__)


class GocarScraper(BaseCarScraper):
    name = "gocar"
    API = "https://search.gocar.be/multi-search"
    BASE = "https://gocar.be"
    INDEX = "prod_vehicles_index_nl"
    # Publieke search-only Meilisearch-sleutel uit de gocar.be-frontend.
    KEY = "5e8d520f3d3918d16f9a79b1b964977612c1b7f738d4530a078cfd8bcdc485bd"
    PER_PAGE = 50
    MAX_PAGES = 20

    def __init__(self, http: Http | None = None) -> None:
        self.http = http or Http()
        self.headers = {
            "Authorization": "Bearer " + self.KEY,
            "Origin": self.BASE,
            "Referer": self.BASE + "/",
            "Accept": "application/json",
        }

    def search(self, *, price_from, price_to, min_range=0, max_mileage=None,
               min_year=None, limit=50) -> Iterator[Car]:
        seen: set[str] = set()
        collected = 0
        offset = 0
        for _ in range(self.MAX_PAGES):
            if collected >= limit:
                return
            payload = {"queries": [{
                "indexUid": self.INDEX,
                "filter": [
                    ['"condition"="tweedehands"'],
                    ['"vehicle_type"="auto"'],
                    ['"point_of_sale_type"="Professioneel"'],  # enkel erkende dealers
                    ['"fuel_type"="Elektrisch"'],
                    f'"price.for_filtering" >= {int(price_from)}',
                    f'"price.for_filtering" <= {int(price_to)}',
                ],
                "limit": self.PER_PAGE,
                "offset": offset,
            }]}
            try:
                resp = self.http.post(self.API, json=payload, headers=self.headers)
            except Exception as exc:
                log.warning("Gocar: ophalen faalde (offset %s): %s", offset, exc)
                return
            if resp.status_code != 200:
                log.warning("Gocar: HTTP %s", resp.status_code)
                return
            try:
                hits = (resp.json().get("results") or [{}])[0].get("hits") or []
            except ValueError:
                return
            if not hits:
                return

            for item in hits:
                car = self._to_car(item)
                if car is None or car.car_id in seen:
                    continue
                seen.add(car.car_id)
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
            if len(hits) < self.PER_PAGE:
                return
            offset += self.PER_PAGE

    def _to_car(self, item: dict) -> Car | None:
        car_id = str(item.get("id") or "")
        make = item.get("brand_name") or ""
        model = item.get("model_name") or ""
        if not (car_id and (make or model)):
            return None

        version = (item.get("version") or "").strip()
        prefix = f"{make} {model}".strip().lower()
        if version.lower().startswith(prefix):
            version = version[len(prefix):].lstrip(" -|·").strip()

        rng = estimate_range(make, model, item.get("version"))
        cover = item.get("cover")
        city = item.get("point_of_sale_city") or ""
        zip_ = str(item.get("point_of_sale_zip") or "").strip()

        return Car(
            source=self.name,
            car_id=car_id,
            make=make,
            model=model,
            version=version[:160],
            price=self._int(item.get("price")),
            year=self._int(item.get("first_registration_year")),
            mileage_km=self._int(item.get("kilometers")),
            range_km=rng,
            range_estimated=rng is not None,
            power_kw=self._int(item.get("engine_power_kw")),
            fuel="Elektrisch",
            transmission=item.get("gearbox") or "",
            location=" ".join(x for x in (zip_, city) if x),
            url=item.get("url") or f"{self.BASE}/nl/autos/id/{car_id}",
            image_url=cover,
            images=[cover] if cover else [],
            seller=item.get("point_of_sale_name"),
        )

    @staticmethod
    def _int(value) -> int | None:
        if isinstance(value, dict):  # price-object: {"for_filtering": 41999, ...}
            value = value.get("for_filtering") or value.get("unformatted")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
