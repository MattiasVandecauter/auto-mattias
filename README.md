# Auto scraper (tweedehands EV's bij erkende dealers)

Zoekt tweedehands elektrische auto's bij **erkende autodealers**, schrijft ze
weg naar JSON/CSV, en maakt een interactief HTML-rapport met foto's, een
batterij-bereikmeter en een beste-koop-score. Particuliere kanalen
(2dehands, Marktplaats) worden bewust niet gebruikt.

## Bronnen

| Bron | `--source` | Markt | Bereik | Verkoper |
|------|-----------|-------|--------|----------|
| AutoScout24 BE | `autoscout` | Belgie | exact | enkel dealers (`custtype=D`) |
| Gocar.be | `gocar` | Belgie | geschat | enkel erkende dealers (Professioneel) |
| Autohero | `autohero` | Belgie | geschat | Autohero zelf (koopt/verkoopt) |
| AutoScout24 NL | `autoscout-nl` | Nederland | exact | enkel dealers |
| AutoScout24 DE | `autoscout-de` | Duitsland | exact | enkel dealers |
| AutoScout24 FR | `autoscout-fr` | Frankrijk | geschat | enkel dealers |

Standaard (`--source all`) draaien alle bronnen: de Belgische trio
**AutoScout24.be + Gocar.be + Autohero** plus AutoScout24 NL/DE/FR, allemaal
gefilterd op erkende/professionele verkopers. Met `--source dealers` beperk je
tot enkel de drie Belgische. AutoScout24 is meteen de aggregator van zowat alle
Belgische dealervoorraad (ook Cardoen, My-Way e.a. publiceren daar); Gocar voegt
zijn eigen dealernetwerk toe; Autohero koopt wagens op, knapt ze op en verkoopt
ze zelf (dus altijd een erkende verkoper).

AutoScout24 toont een rijbereik per wagen, maar dat is een door de verkoper
ingetypt vrij tekstveld en soms onrealistisch (een IONIQ 5 van 710 km is
onmogelijk). We vertrouwen het enkel als het plausibel is, anders schatten we
het bereik zelf (zie hieronder). Gocar en Autohero geven geen bereik mee, dus
die schatten we altijd; geschatte bereiken tonen een "~".

Autohero staat trouwens ook als dealer op Gocar, en veel dealers publiceren op
AutoScout24 én Gocar. Dezelfde fysieke wagen verschijnt dus soms op meerdere
bronnen. Die ontdubbelen we (zie hieronder).

**Niet als aparte bron:** Cardoen en My-Way draaien op zwaar afgeschermde
JS-apps (Nuxt/Gatsby) die enkel via een browser-scrape (Playwright) te oogsten
zijn, en hun voorraad zit grotendeels al in AutoScout24. De particuliere bronnen
2dehands/Marktplaats staan nog in `tweedehands.py` maar zijn niet geregistreerd.

## Installatie

```bash
cd auto-mattias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Gebruik

```bash
# Standaard: alle dealerbronnen (BE-trio + AutoScout24 NL/DE/FR)
./run                       # of: python -m autoscraper.cli

# Enkel de Belgische dealers (AutoScout24.be + Gocar.be + Autohero)
./run --source dealers

# Eén bron
./run --source autohero

# Strakker (en sneller: minder pagina's per bron)
./run --price-from 20000 --price-to 43000 \
  --min-range 350 --max-mileage 120000 --min-year 2022 --limit 200
```

Opties: `--price-from`, `--price-to`, `--min-range`, `--max-mileage`,
`--min-year`, `--limit` (per bron), `--source` (`all` standaard, `dealers`, of een bronnaam), `--format`.

Output in `output/`: `ev.json`, `ev.csv` en **`ev.html`** (open in je browser).

## Merknamen gelijktrekken (`brands.py`)

Bronnen spellen merken anders: AutoScout `CUPRA` vs Gocar `Cupra`, Gocar
`Mercedes` vs `Mercedes-Benz` elders, `POLESTAR` vs `Polestar`, `Smart` vs
`smart`, `DS` vs `DS Automobiles`. Daardoor splitste één merk in meerdere
filterchips in het rapport (filteren op Cupra liet de AutoScout-CUPRA's
verdwijnen) en miste de ontdubbeling dezelfde Mercedes over bronnen heen.
`canonical_make()` mapt elke schrijfwijze naar één canonieke naam (AutoScout-stijl
als referentie); onbekende merken blijven ongewijzigd. Dit draait in `cli.py`
vóór het ontdubbelen.

## Ontdubbelen over bronnen heen

Dezelfde wagen kan op meerdere bronnen staan (een dealer op AutoScout24 én Gocar,
of Autohero direct én via Gocar). `storage.py` ontdubbelt in twee stappen: eerst
exact (zelfde bron + advertentie), dan dezelfde fysieke wagen op merk + model +
bouwjaar + kilometerstand + prijs. Bij een match houden we het rijkste record,
en dat is het record met een geverifieerd (niet-geschat) bereik boven een
geschat bereik. Wagens zonder prijs/km/bouwjaar mergen we niet (te weinig
zekerheid).

## Rijbereik (`estimate.py`)

`MODELS` is een batterij-bewuste tabel: per model de officiele WLTP-bereiken per
batterijvariant (`kWh -> km`). `estimate_range` leest de batterij uit de
versietekst en kiest de dichtstbijzijnde variant; zonder batterij een
representatieve default. `FALLBACK_RANGES` vangt zeldzamere modellen op.
Let op: advertenties vermelden bruto (gross) én netto (usable) kWh door elkaar
(bv. een Cupra Born "82 kWh" = 77 kWh netto). De varianten zijn zo gekozen dat
zo'n vermelding niet naar een te hoog bereik leidt.

`plausible_range` beslist welk bereik een AutoScout-wagen krijgt: de door de
verkoper opgegeven waarde wordt enkel vertrouwd als ze onder elke bovengrens
valt (een globale max, de fysieke grens `kWh × 9,0`, en `modelschatting × 1,35`).
Onmogelijke waarden zoals een IONIQ 5 met 710 km vallen zo terug op de schatting
(~507 km).

## Het rapport (`output/ev.html`)

Self-contained, geen server nodig. Elke wagen is een kaart met foto, prijs en
een batterij-bereikmeter (kleur naar bereik). Klik open voor de fotogalerij, de
volledige specs en een link naar de advertentie. Bovenaan een compacte balk met
zoekveld en een inklapbare **Filters**-knop (met een badge voor het aantal
actieve filters). Uitgeklapt: sorteren (standaard **beste koop**), min koopscore
(standaard 80, zodat zwakkere koopjes verborgen zijn; sleep naar 0 voor alles),
en filteren op bereik, prijs en merk.

In het uitgeklapte detail zit een uitklapbaar blok **"hoe berekend?"** dat de
koopscore openbreekt: per factor de deelscore (0-100), het gewicht en de
bijdrage aan het totaal, met een balk gekleurd naar de deelscore. Zo zie je in
één oogopslag wat de score omhoog of omlaag trekt.

## Beste-koop-score (`score.py`)

Een score 0-100 voor waarde-voor-je-geld. Elke factor levert een deelscore
0-100; de eindscore is de gewogen som (gewichten tussen haakjes):
- rijbereik per euro (de kern, 36%),
- absoluut rijbereik (24%),
- lage kilometerstand (22%),
- recent bouwjaar (18%),
- batterijgezondheid (SOH %) als die in de titel staat (dan schuiven de
  gewichten naar 30/20/20/14/16).

`score_breakdown()` geeft die opbouw per factor terug; het rapport toont ze
onder "hoe berekend?". De opbouw zit ook in `ev.json` (veld `score_parts`),
niet in `ev.csv`.

## Dagelijks publiceren (GitHub Actions → Pages)

`.github/workflows/daily-report.yml` draait de scraper elke dag (cron 05:00 UTC,
~07:00 Brussel) op GitHub en publiceert `ev.html` naar GitHub Pages. Zo staat er
elke ochtend een verse pagina klaar, ook als je eigen pc uit staat:
**https://mattiasvandecauter.github.io/auto-mattias/**

Let op: GitHub draait vanaf een datacenter-IP, en Gocar (achter Cloudflare)
blokkeert dat met een 403. De dagelijkse run bevat dus AutoScout24 + Autohero,
maar geen Gocar. Wil je Gocar erbij, draai dan `./run` lokaal (je thuis-IP wordt
niet geblokkeerd); Gocar zit dan in je lokale `output/ev.html`.

## Structuur

```
run              # start-script (gebruikt .venv, geeft opties door)
.github/workflows/daily-report.yml   # dagelijkse GitHub Actions-run → Pages
autoscraper/
  models.py        # Car dataclass
  http.py          # HTTP-sessie (retries + pauzes)
  browser.py       # Playwright-fetcher (voor bronnen achter bot-bescherming)
  base.py          # BaseCarScraper interface
  estimate.py      # batterij-bewust WLTP-bereik + plausibiliteitscontrole
  brands.py        # canonieke merknamen over bronnen heen
  score.py         # beste-koop-score
  storage.py       # JSON/CSV + ontdubbelen
  report.py        # HTML-rapport genereren
  templates/report.html
  sources/
    autoscout.py   # AutoScout24 BE/NL/DE/FR (Next.js __NEXT_DATA__), dealer-only
    gocar.py       # Gocar.be (Meilisearch-API), enkel erkende dealers
    autohero.py    # Autohero (GraphQL-gateway searchAdV9AdsV2)
    tweedehands.py # 2dehands.be + Marktplaats.nl (particulier, niet geregistreerd)
    __init__.py
  cli.py
```

## Let op

Voor persoonlijk gebruik. `--limit` staat standaard op 1000 (max per bron); in
de praktijk begrenzen de bronnen zelf via paginering: AutoScout24 ~400 (20
pagina's), Gocar tot 1000, Autohero het volledige BE-aanbod (~50). Een hoge
limiet betekent meer pagina's en dus een tragere run door de ingebouwde pauzes.
Geschatte bereiken (~) zijn benaderingen op modelniveau.
