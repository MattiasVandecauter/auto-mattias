"""Basisklasse die elke bron-scraper implementeert."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from .models import Car


class BaseCarScraper(ABC):
    name: str = "base"

    @abstractmethod
    def search(
        self,
        *,
        price_from: int,
        price_to: int,
        min_range: int = 0,
        max_mileage: int | None = None,
        min_year: int | None = None,
        limit: int = 50,
    ) -> Iterator[Car]:
        """Levert tot `limit` autos op die aan de criteria voldoen."""
        raise NotImplementedError
