"""AutoScout24.be-scraper.

AutoScout24 is een Next.js-app: de zoekresultaten staan als JSON in het
__NEXT_DATA__-script van de pagina. We filteren elektrisch + prijs via de URL en
het rijbereik/km/bouwjaar client-side uit de geparste data.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ..base import BaseCarScraper
from ..estimate import estimate_range, parse_kwh, plausible_range
from ..http import Http
from ..models import Car

log = logging.getLogger(__name__)


class AutoScoutScraper(BaseCarScraper):
    name = "autoscout"
    BASE = "https://www.autoscout24.be"
    PATH = "/nl/lst"
    MAX_PAGES = 20
    CUSTTYPE = "D"  # enkel erkende dealers (D), geen particulieren (P)

    def __init__(self, http: Http | None = None) -> None:
        self.http = http or Http()

    def search(self, *, price_from, price_to, min_range=0, max_mileage=None,
               min_year=None, limit=50) -> Iterator[Car]:
        seen: set[str] = set()
        collected = 0
        page = 1
        while collected < limit and page <= self.MAX_PAGES:
            params = {
                "atype": "C", "fuel": "E", "ustate": "U", "custtype": self.CUSTTYPE,
                "pricefrom": int(price_from), "priceto": int(price_to),
                "sort": "age", "desc": 1, "page": page,
            }
            try:
                resp = self.http.get(self.BASE + self.PATH, params=params)
            except Exception as exc:
                log.warning("AutoScout: ophalen pagina %s faalde: %s", page, exc)
                break
            if resp.status_code != 200:
                log.warning("AutoScout: onverwachte HTTP %s", resp.status_code)
                break

            cars = self._parse(resp.text)
            if not cars:
                break
            new = 0
            for car in cars:
                if car.car_id in seen:
                    continue
                seen.add(car.car_id)
                new += 1
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
            page += 1

    def _parse(self, html: str) -> list[Car]:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find("script", id="__NEXT_DATA__")
        if node is None or not node.string:
            return []
        try:
            data = json.loads(node.string)
        except ValueError:
            return []
        listings = (data.get("props", {}).get("pageProps", {}) or {}).get("listings") or []
        cars = [self._to_car(item) for item in listings]
        return [c for c in cars if c is not None]

    def _to_car(self, item: dict) -> Car | None:
        vehicle = item.get("vehicle") or {}
        make = vehicle.get("make") or ""
        model = vehicle.get("model") or ""
        car_id = str(item.get("id") or "")
        if not (car_id and (make or model)):
            return None

        details = item.get("vehicleDetails") or []
        tracking = item.get("tracking") or {}
        location = item.get("location") or {}
        url = item.get("url") or ""
        images = item.get("images") or []

        year = None
        m = re.search(r"(\d{4})", tracking.get("firstRegistration") or "")
        if m:
            year = int(m.group(1))

        # Het 'distance'-veld is door de verkoper ingetypt en soms onrealistisch
        # (bv. een IONIQ 5 met 710 km). Aanvaard het enkel als het plausibel is.
        version = vehicle.get("modelVersionInput")
        dealer_range = self._num(self._by_icon(details, "distance"))
        est = estimate_range(make, model, version)
        range_km, range_est = plausible_range(dealer_range, est, parse_kwh(version))

        return Car(
            source=self.name,
            car_id=car_id,
            make=make,
            model=model,
            version=(version or "").strip()[:160],
            price=(item.get("price") or {}).get("priceRaw"),
            year=year,
            mileage_km=self._num(tracking.get("mileage")) or self._num(self._by_icon(details, "mileage_odometer")),
            range_km=range_km,
            range_estimated=range_est,
            power_kw=self._num(self._by_icon(details, "speedometer")),
            fuel=vehicle.get("fuel") or "",
            transmission=vehicle.get("transmission") or "",
            location=" ".join(x for x in (location.get("zip"), location.get("city")) if x),
            url=self.BASE + url if url.startswith("/") else url,
            image_url=images[0] if images else None,
            images=images[:8],
            seller=(item.get("seller") or {}).get("companyName"),
        )

    @staticmethod
    def _by_icon(details: list, icon: str) -> str:
        # iconName is taal-onafhankelijk (distance/mileage_odometer/speedometer),
        # de ariaLabel/data niet (actieradius vs Reichweite).
        for d in details:
            if d.get("iconName") == icon:
                return d.get("data") or ""
        return ""

    @staticmethod
    def _num(text) -> int | None:
        m = re.search(r"\d[\d.\s]*", str(text or ""))
        if not m:
            return None
        digits = re.sub(r"[.\s]", "", m.group())
        return int(digits) if digits else None


class AutoScoutNL(AutoScoutScraper):
    name = "autoscout-nl"
    BASE = "https://www.autoscout24.nl"
    PATH = "/lst"


class AutoScoutDE(AutoScoutScraper):
    name = "autoscout-de"
    BASE = "https://www.autoscout24.de"
    PATH = "/lst"


class AutoScoutFR(AutoScoutScraper):
    name = "autoscout-fr"
    BASE = "https://www.autoscout24.fr"
    PATH = "/lst"
