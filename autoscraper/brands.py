"""Canonieke merknamen over bronnen heen.

Bronnen spellen merken anders: AutoScout 'CUPRA' vs Gocar 'Cupra', Gocar
'Mercedes' vs 'Mercedes-Benz' elders, 'POLESTAR' vs 'Polestar', 'Smart' vs
'smart', Gocar 'DS' vs 'DS Automobiles'. Daardoor splitst één merk in meerdere
filterchips in het rapport en mist de ontdubbeling dezelfde wagen over bronnen
heen. We mappen elke schrijfwijze naar één canonieke naam.

We nemen de AutoScout24-stijl als referentie (de grote, gestandaardiseerde
marktplaats). Onbekende merken laten we ongewijzigd; ze worden enkel getrimd.
"""

from __future__ import annotations

import re

_FOLD = str.maketrans("àáâäéèêëíîïóôöûüç", "aaaaeeeeiiiooouuc")


def _key(name: str) -> str:
    """Normaliseer tot een vergelijkingssleutel: kleine letters, enkel alfanum."""
    return re.sub(r"[^a-z0-9]", "", name.lower().translate(_FOLD))


# Canonieke weergavenaam -> alle schrijfwijzen die ernaartoe mappen (incl. zichzelf).
# Enkel merken waar bronnen van elkaar verschillen (of dat plausibel kunnen).
_VARIANTS: dict[str, tuple[str, ...]] = {
    "Mercedes-Benz": ("Mercedes-Benz", "Mercedes", "Mercedes Benz", "Mercedes-AMG"),
    "CUPRA": ("CUPRA", "Cupra"),
    "DS Automobiles": ("DS Automobiles", "DS", "DS Automobile"),
    "Polestar": ("Polestar", "POLESTAR"),
    "smart": ("smart", "Smart"),
    "SEAT": ("SEAT", "Seat"),
    "XPENG": ("XPENG", "Xpeng", "X-Peng"),
    "Lynk & Co": ("Lynk & Co", "Lynk&Co", "Lynk Co", "Lynk and Co"),
    "Alfa Romeo": ("Alfa Romeo", "Alfa-Romeo"),
    "Volkswagen": ("Volkswagen", "VW"),
}

_CANON: dict[str, str] = {}
for _canon, _spellings in _VARIANTS.items():
    for _s in _spellings:
        _CANON[_key(_s)] = _canon


def canonical_make(name: str | None) -> str:
    """Geef de canonieke merknaam. Onbekende merken blijven ongewijzigd (getrimd)."""
    if not name:
        return name or ""
    return _CANON.get(_key(name), name.strip())
