"""Schat het WLTP-rijbereik (km) van een EV op basis van merk/model + batterij.

MODELS is batterij-bewust: per model staan de WLTP-bereiken per batterijvariant
(usable-kWh -> km), geresearcht uit officiele opgaves. estimate_range kiest de
variant die het dichtst bij de gevonden kWh ligt; zonder kWh de representatieve
default. FALLBACK_RANGES vangt modellen op die niet in MODELS staan (oudere of
zeldzame). Keywords staan van specifiek (lang) naar algemeen, eerste match wint.
"""

from __future__ import annotations

import re

_FOLD = str.maketrans("àáâäéèêëíîïóôöûüç", "aaaaeeeeiiiooouuc")

# Batterij-bewust: (keyword, [(usable_kwh, wltp_km), ...], default_wltp)
MODELS: list[tuple[str, list[tuple[int, int]], int]] = [
    ('john cooper works', [(54, 371)], 371),
    ('leapmotor design', [(56, 361), (67, 434)], 434),
    ('megane e-tech', [(40, 298), (60, 455)], 455),
    ('urban cruiser', [(61, 426)], 426),
    ('countryman e', [(65, 482)], 462),
    ('dolphin surf', [(30, 220), (43, 310)], 310),
    ('lynk & co 01', [(18, 69)], 69),
    ('q4 sportback', [(52, 350), (55, 357), (77, 540), (82, 540)], 540),
    ('audi e-tron', [(71, 340), (95, 436)], 415),
    ('c3 aircross', [(44, 306), (54, 400)], 306),
    ('c5 aircross', [(74, 520), (97, 680)], 520),
    ('renault r 4', [(52, 409)], 409),
    ('abarth 500', [(37, 265)], 265),
    ('polestar 2', [(63, 478), (69, 546), (78, 540), (82, 600)], 510),
    ('cooper se', [(33, 233), (54, 402)], 402),
    ('grandland', [(73, 523)], 523),
    ('renault 5', [(40, 312), (52, 410)], 410),
    ('volvo c40', [(69, 477), (82, 560)], 490),
    ('byd seal', [(82, 545)], 520),
    ('e-vitara', [(49, 344), (61, 426)], 426),
    ('explorer', [(77, 553), (79, 602)], 590),
    ('fiat 500', [(24, 190), (42, 320)], 320),
    ('fiat 600', [(54, 409)], 409),
    ('frontera', [(44, 305), (54, 408)], 305),
    ('tavascan', [(77, 553)], 550),
    ('townstar', [(45, 285)], 285),
    ('xpeng g6', [(66, 435), (88, 570)], 570),
    ('xpeng p7', [(86, 576)], 576),
    ('avenger', [(51, 400), (54, 400)], 400),
    ('byd han', [(85, 521)], 521),
    ('dolphin', [(45, 340), (60, 427)], 427),
    ('eqa 250', [(67, 493)], 493),
    ('eqa 300', [(67, 432)], 432),
    ('eqa 350', [(66, 430)], 430),
    ('eqb 250', [(67, 470), (70, 520)], 480),
    ('eqb 300', [(66, 423)], 423),
    ('eqb 350', [(66, 423)], 423),
    ('eqc 400', [(80, 420)], 420),
    ('ioniq 5', [(58, 384), (63, 440), (73, 481), (77, 507)], 500),
    ('ioniq 6', [(53, 429), (77, 614)], 614),
    ('model 3', [(58, 513), (75, 560), (79, 629)], 513),
    ('model s', [(75, 490), (100, 630)], 600),
    ('model x', [(100, 543)], 543),
    ('model y', [(60, 480), (75, 540)], 480),
    ('peugeot partner', [(46, 330)], 320),
    ('ypsilon', [(54, 403)], 403),
    ('aceman', [(42, 310), (54, 406)], 406),
    ('atto 3', [(50, 345), (60, 420)], 420),
    ('bmw i3', [(33, 235), (42, 305)], 305),
    ('bmw ix ', [(71, 425), (105, 630)], 425),
    ('bmw x1', [(65, 460)], 460),
    ('e-niro', [(39, 289), (64, 455)], 455),
    ('expert', [(50, 230), (75, 330)], 330),
    ('fortwo', [(17, 130)], 130),
    ('i-pace', [(85, 470)], 470),
    ('inster', [(42, 327), (49, 370)], 370),
    ('junior', [(51, 410)], 410),
    ('mach-e', [(70, 440), (72, 440), (91, 600)], 515),
    ('marvel', [(70, 402)], 400),
    ('megane', [(60, 455)], 455),
    ('rifter', [(46, 320)], 300),
    ('scenic', [(60, 430), (87, 625)], 625),
    ('twingo', [(22, 190)], 190),
    ('vitara', [(49, 344), (61, 426)], 426),
    ('vivaro', [(50, 230), (75, 335)], 335),
    ('ariya', [(63, 404), (87, 533)], 500),
    ('astra', [(54, 416), (58, 454)], 416),
    ('c-hr+', [(58, 458), (77, 607)], 607),
    ('capri', [(77, 627), (79, 592)], 600),
    ('citan', [(45, 285)], 285),
    ('combo', [(50, 280)], 280),
    ('corsa', [(50, 354), (51, 402)], 354),
    ('e-208', [(50, 362), (51, 410)], 362),
    ('elroq', [(55, 375), (63, 430), (82, 570)], 560),
    ('enyaq', [(62, 410), (82, 550)], 520),
    ('gen-e', [(44, 376), (47, 417)], 376),
    ('ioniq', [(53, 429), (73, 481), (77, 510)], 490),
    ('micra', [(40, 317), (52, 416)], 416),
    ('mokka', [(50, 338), (54, 404)], 370),
    ('mx-30', [(18, 85), (36, 200)], 200),
    ('2008', [(50, 343), (54, 406)], 376),
    ('3008', [(73, 527), (97, 700)], 527),
    ('5008', [(73, 502), (97, 668)], 502),
    ('500c', [(42, 313)], 313),
    ('600e', [(54, 409)], 409),
    ('a290', [(52, 380)], 380),
    ('born', [(58, 420), (77, 550)], 420),
    ('bz4x', [(71, 510)], 490),
    ('c-hr', [(77, 600)], 600),
    ('ds 3', [(46, 341), (51, 402)], 341),
    ('e-c3', [(44, 320)], 320),
    ('ec40', [(69, 476), (82, 582)], 582),
    ('ex30', [(51, 344), (69, 476)], 476),
    ('ex40', [(82, 573)], 573),
    ('id.3', [(45, 350), (58, 425), (77, 550)], 425),
    ('id.4', [(52, 350), (77, 540)], 530),
    ('id.5', [(77, 520)], 520),
    ('id.7', [(77, 615), (86, 709)], 615),
    ('kona', [(39, 305), (48, 377), (64, 484), (65, 514)], 484),
    ('niro', [(64, 455), (65, 460)], 460),
    ('polo', [(37, 329), (52, 454)], 454),
    ('puma', [(44, 376), (47, 417)], 376),
    ('xc40', [(69, 460), (82, 540)], 460),
    ('peugeot 208', [(50, 350), (51, 410)], 360),
    ('peugeot 308', [(51, 412), (55, 450)], 410),
    ('peugeot 408', [(58, 453)], 453),
    ('b05', [(67, 482)], 482),
    ('b10', [(56, 361), (67, 434)], 434),
    ('c10', [(67, 420)], 420),
    ('eqa', [(66, 490), (70, 555)], 480),
    ('eqb', [(66, 430), (70, 510)], 430),
    ('eqc', [(80, 420)], 420),
    ('eqe', [(91, 600)], 600),
    ('ev3', [(58, 436), (81, 605)], 600),
    ('ev4', [(58, 439), (81, 625)], 439),
    ('ev5', [(81, 530)], 530),
    ('ev6', [(58, 394), (63, 428), (77, 528)], 528),
    ('id3', [(45, 350), (58, 425), (77, 550)], 425),
    ('ix1', [(65, 456)], 460),
    ('ix3', [(80, 460), (109, 805)], 460),
    ('mg4', [(51, 350), (64, 435)], 400),
    ('mg5', [(61, 400)], 400),
    ('#1', [(66, 440)], 440),
    ('#3', [(66, 455)], 455),
    ('#5', [(76, 540), (100, 590)], 540),
    ('6e', [(69, 479), (80, 552)], 479),
    ('c3', [(44, 320)], 320),
    ('i4', [(70, 460), (84, 540)], 510),
    ('q4', [(52, 341), (77, 530), (80, 510), (82, 537)], 520),
    ('ix2', [(65, 460)], 460),
    ('zs', [(50, 320), (70, 440)], 380),
]

# Vangnet voor modellen die niet in MODELS staan (een enkele waarde).
FALLBACK_RANGES: list[tuple[str, int]] = [
    ("e-tron gt", 480), ("e-tron", 440), ("i7", 590), ("i5", 500), ("i3", 300),
    ("ex90", 580), ("eqs", 620), ("zoe", 390), ("spring", 220), ("leaf", 270),
    ("soul", 440), ("id.buzz", 410), ("buzz", 410), ("e-308", 400), ("mustang", 480),
    ("proace", 300), ("u5", 400), ("u6", 400), ("seal", 520), ("zeekr", 440),
    ("honda e", 220), ("e-up", 260), ("e-golf", 230), ("citigo", 260),
    ("kangoo", 280), ("berlingo", 280), ("ipace", 460), ("mini", 230), ("smart", 130),
]


def estimate_range(*texts: str | None) -> int | None:
    """Geef een geschat WLTP-rijbereik (km), batterij-bewust, of None als onbekend."""
    s = " ".join(t for t in texts if t).lower().translate(_FOLD)
    kwh = parse_kwh(s)
    for keyword, variants, default in MODELS:
        if keyword in s:
            if kwh and variants:
                return min(variants, key=lambda v: abs(v[0] - kwh))[1]
            return default
    for keyword, rng in FALLBACK_RANGES:
        if keyword in s:
            return rng
    return None


# Plausibiliteit. Geen enkele EV haalt ~9,5 km WLTP per kWh batterij; en een
# bereik dat ver boven de modelschatting ligt, is meestal een typfout van de
# verkoper. Beide ankers samen vangen onmogelijke waarden zonder legitieme hoge
# bereiken (efficiente Tesla's, aerodynamische Hyundai's) te verwerpen.
GLOBAL_MAX_RANGE = 850      # km, bovengrens voor om het even welke EV
KM_PER_KWH_MAX = 9.0        # WLTP-bovengrens per kWh batterij
MODEL_TOLERANCE = 1.35      # zoveel boven de modelschatting nog aanvaard


def parse_kwh(text: str | None) -> float | None:
    """Haal de batterijgrootte (kWh) uit een versietekst, indien vermeld."""
    m = re.search(r"(\d{2,3})(?:[.,](\d))?\s*kwh", (text or "").lower())
    if not m:
        return None
    val = float(f"{m.group(1)}.{m.group(2) or 0}")
    return val if 10 <= val <= 250 else None


def plausible_range(dealer: int | None, est: int | None, kwh: float | None) -> tuple[int | None, bool]:
    """Bepaal (bereik, is_geschat).

    Vertrouw de door de verkoper opgegeven `dealer`-waarde enkel als ze onder
    elke beschikbare bovengrens valt. Anders val terug op de modelschatting.
    """
    ceiling = GLOBAL_MAX_RANGE
    if kwh:
        ceiling = min(ceiling, kwh * KM_PER_KWH_MAX)
    if est:
        ceiling = min(ceiling, est * MODEL_TOLERANCE)
    if dealer is not None and 90 <= dealer < ceiling:
        return dealer, False
    if est is not None:
        return est, True
    if kwh:
        return round(kwh * 6.0), True          # ruwe schatting uit batterij
    return (dealer if (dealer and dealer <= GLOBAL_MAX_RANGE) else None), False
