"""Playwright-fetcher voor sites met JS-rendering of bot-bescherming.

Echte Chromium-browser met realistische fingerprint en menselijke pauzes, zodat
Cloudflare/Akamai-checks vanzelf opgelost raken. Playwright wordt lui
geimporteerd, zodat de lichte bronnen het pakket niet nodig hebben.
"""

from __future__ import annotations

import logging
import random
import time

from .http import Http

log = logging.getLogger(__name__)

CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
_STEALTH_JS = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    "Object.defineProperty(navigator, 'languages', {get: () => ['nl-BE','nl','en']});"
    "window.chrome = window.chrome || { runtime: {} };"
)
_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]


class BrowserFetcher:
    """Haalt pagina's op met een echte browser. Gebruik als context manager."""

    def __init__(self, *, headless: bool = True, locale: str = "nl-BE",
                 timezone: str = "Europe/Brussels", timeout: float = 30000,
                 user_agent: str | None = None, min_gap: float = 0.8, max_gap: float = 2.2) -> None:
        self.headless = headless
        self.locale = locale
        self.timezone = timezone
        self.timeout = timeout
        self.user_agent = user_agent or CHROME_UA
        self.min_gap = min_gap
        self.max_gap = max_gap
        self._pw = self._browser = self._context = None

    def __enter__(self) -> "BrowserFetcher":
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Playwright ontbreekt. Activeer de .venv of installeer met: "
                "pip install playwright && playwright install chromium"
            ) from exc
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless, args=_LAUNCH_ARGS)
        self._context = self._browser.new_context(
            user_agent=self.user_agent, locale=self.locale, timezone_id=self.timezone,
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8"},
        )
        self._context.add_init_script(_STEALTH_JS)
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass

    def fetch(self, url: str, *, wait_selector: str | None = None, wait_until: str = "load",
              extra_wait_ms: int = 1200, max_challenge_ms: int = 25000) -> str:
        time.sleep(random.uniform(self.min_gap, self.max_gap))
        page = self._context.new_page()
        try:
            page.goto(url, wait_until=wait_until, timeout=self.timeout)
            self._pass_cloudflare(page, max_challenge_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=self.timeout)
                except Exception:
                    log.warning("selector %r niet gevonden binnen timeout", wait_selector)
            if extra_wait_ms:
                page.wait_for_timeout(extra_wait_ms)
            return page.content()
        finally:
            page.close()

    @staticmethod
    def _pass_cloudflare(page, max_ms: int) -> None:
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""
        if "just a moment" not in title and "even geduld" not in title:
            return
        log.info("Cloudflare-challenge gedetecteerd, wachten...")
        try:
            page.wait_for_function(
                "() => !document.title.toLowerCase().includes('just a moment')"
                " && !document.title.toLowerCase().includes('even geduld')", timeout=max_ms)
        except Exception:
            log.warning("Cloudflare-challenge niet tijdig opgelost")


class HybridFetcher:
    """Probeer eerst gewone HTTP; val terug op een echte browser bij blokkades."""

    def __init__(self, http: Http | None = None, *, headless: bool = True) -> None:
        self.http = http or Http()
        self.headless = headless
        self._bf: BrowserFetcher | None = None
        self._use_browser = False

    def __enter__(self) -> "HybridFetcher":
        return self

    def __exit__(self, *exc) -> None:
        if self._bf is not None:
            self._bf.__exit__(*exc)

    def get_html(self, url: str, *, wait_selector: str | None = None) -> str:
        if not self._use_browser:
            try:
                resp = self.http.get(url)
                if resp.status_code == 200 and resp.text:
                    return resp.text
                log.info("HTTP %s op %s; schakel over naar browser", resp.status_code, url[:70])
            except Exception as exc:
                log.info("HTTP-fout op %s (%s); browser", url[:70], exc)
            self._use_browser = True
        if self._bf is None:
            self._bf = BrowserFetcher(headless=self.headless)
            self._bf.__enter__()
        return self._bf.fetch(url, wait_selector=wait_selector, extra_wait_ms=1200)
