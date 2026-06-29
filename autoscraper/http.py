"""Kleine HTTP-helper: gedeelde sessie, beleefde pauzes, retry met backoff."""

from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
}


class Http:
    """Wrapt een requests.Session met rate limiting en retries."""

    def __init__(
        self,
        *,
        min_delay: float = 1.5,
        max_delay: float = 3.5,
        timeout: float = 20.0,
        max_retries: int = 3,
        headers: dict | None = None,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        if headers:
            self.session.headers.update(headers)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> requests.Response:
        return self._request("GET", url, params=params, headers=headers)

    def post(self, url: str, json: dict | None = None, headers: dict | None = None) -> requests.Response:
        return self._request("POST", url, json=json, headers=headers)

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._sleep()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("request mislukt (%s/%s): %s", attempt, self.max_retries, exc)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt
                log.warning("HTTP %s, %ss wachten (%s/%s)", resp.status_code, wait, attempt, self.max_retries)
                time.sleep(wait)
                continue
            return resp
        if last_exc:
            raise last_exc
        raise RuntimeError(f"opgegeven na {self.max_retries} pogingen voor {url}")
