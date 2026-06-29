"""Beste-koop-score (0-100): waarde voor je geld bij een tweedehands EV.

Combineert rijbereik per euro, absoluut bereik, lage kilometerstand, recent
bouwjaar en (indien vermeld) batterijgezondheid (SOH). Hoger = betere koop.
"""

from __future__ import annotations

import re


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _scale(v, lo, hi):
    """v==lo -> 0, v==hi -> 100. `hi` mag lager zijn dan `lo` (lager is beter)."""
    if v is None:
        return None
    return _clamp((v - lo) / (hi - lo) * 100)


def parse_soh(*texts: str | None) -> int | None:
    """Haal batterijgezondheid (SOH %) uit een titel/omschrijving, indien aanwezig."""
    s = " ".join(t for t in texts if t).lower()
    for pat in (r"soh[^0-9]{0,4}(\d{2,3})\s*%", r"(\d{2,3})\s*%\s*soh",
                r"(\d{2,3})\s*%\s*(?:battery|batterij|gezond|health|sante)"):
        m = re.search(pat, s)
        if m:
            v = int(m.group(1))
            if 60 <= v <= 100:
                return v
    return None


def _nl_int(n) -> str:
    return f"{n:,}".replace(",", ".")


def score_breakdown(car) -> dict | None:
    """Geef de beste-koop-score plus de opbouw per factor, of None zonder prijs/bereik.

    Elke factor levert een deelscore 0-100, een gewicht en een bijdrage
    (deelscore x gewicht). De som van de bijdragen is de eindscore. Zo is in het
    rapport per wagen te zien waarom een score hoog of laag uitvalt.
    """
    if not car.price or not car.range_km:
        return None
    value = car.range_km / (car.price / 1000.0)            # km rijbereik per 1000 euro
    value_s = _scale(value, 8, 22)
    range_s = _scale(car.range_km, 250, 560)
    has_km = car.mileage_km is not None
    mileage_s = _scale(car.mileage_km, 150000, 5000) if has_km else 60.0
    year_s = _scale(car.year, 2018, 2025) if car.year else 55.0
    soh = parse_soh(car.version)
    soh_s = _scale(soh, 85, 100)

    km_txt = f"{_nl_int(car.mileage_km)} km" if has_km else "onbekend (gemiddelde aangenomen)"
    year_txt = str(car.year) if car.year else "onbekend (gemiddelde aangenomen)"
    range_txt = f"{car.range_km} km" + (" (geschat)" if car.range_estimated else "")

    # (sleutel, label, uitleg-detail, deelscore, gewicht). Gewichten verschillen
    # naargelang de batterijgezondheid (SOH) bekend is.
    if soh_s is not None:
        rows = [
            ("value", "Rijbereik per euro", f"{value:.1f} km per €1.000", value_s, 0.30),
            ("range", "Rijbereik", range_txt, range_s, 0.20),
            ("mileage", "Kilometerstand", km_txt, mileage_s, 0.20),
            ("year", "Bouwjaar", year_txt, year_s, 0.14),
            ("soh", "Batterijgezondheid", f"{soh}% SOH", soh_s, 0.16),
        ]
    else:
        rows = [
            ("value", "Rijbereik per euro", f"{value:.1f} km per €1.000", value_s, 0.36),
            ("range", "Rijbereik", range_txt, range_s, 0.24),
            ("mileage", "Kilometerstand", km_txt, mileage_s, 0.22),
            ("year", "Bouwjaar", year_txt, year_s, 0.18),
        ]

    components = [
        {"key": k, "label": lbl, "detail": det,
         "subscore": round(sub), "weight": round(w * 100), "points": round(sub * w, 1)}
        for (k, lbl, det, sub, w) in rows
    ]
    score = round(_clamp(sum(sub * w for (_, _, _, sub, w) in rows)))
    return {"score": score, "components": components}


def best_buy_score(car) -> int | None:
    """Geef een beste-koop-score 0-100, of None als prijs/bereik ontbreken."""
    bd = score_breakdown(car)
    return bd["score"] if bd else None
