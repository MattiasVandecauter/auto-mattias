"""Datamodel voor een tweedehands auto-advertentie."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Car:
    """Een auto-advertentie, genormaliseerd over bronnen heen."""

    source: str
    car_id: str
    make: str
    model: str
    version: str = ""
    price: int | None = None
    year: int | None = None
    mileage_km: int | None = None
    range_km: int | None = None
    range_estimated: bool = False
    power_kw: int | None = None
    fuel: str = ""
    transmission: str = ""
    location: str = ""
    url: str = ""
    image_url: str | None = None
    images: list | None = None
    seller: str | None = None
    score: int | None = None
    score_parts: list | None = None  # opbouw van de koopscore per factor (voor het rapport)
    scraped_at: str = field(default_factory=_now_iso)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.car_id}"

    @property
    def title(self) -> str:
        return " ".join(x for x in (self.make, self.model) if x)

    def to_dict(self) -> dict:
        return asdict(self)
