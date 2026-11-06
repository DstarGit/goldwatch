"""Scraper listy zlotych monet GoldInvest24 (strony kategorii, zgodnie z robots.txt)."""
import html
import logging
import os
import re
import time
import urllib.request

log = logging.getLogger("scraper")

BASE = "https://goldinvest24.pl"
LIST_PATH = "/zlote-monety-inwestycyjne"
USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "NumiGoldWatch/1.0 (prywatny monitor cen; 1 cykl co 15 min, przerwa 1,5 s)",
)
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.5"))
MAX_PAGES = 30
MIN_PAGES = 5

# Slowa wykluczajace (regex, bez rozrozniania wielkosci liter) - konfigurowalne w .env
EXCLUDE_WORDS = os.environ.get("EXCLUDE_WORDS", r"drugi gatunek|uszkodz|Liberty|\.99999|nomin")
EXCLUDE_RE = re.compile(EXCLUDE_WORDS, re.I) if EXCLUDE_WORDS.strip() else None

SERIES = [
    ("Krugerrand", re.compile(r"Krugerrand", re.I)),
    ("Britannia", re.compile(r"Britannia", re.I)),
    ("Liść Klonowy", re.compile(r"Li[śs][ćc] Klonowy|Maple", re.I)),
    ("Filharmonik", re.compile(r"Filharmonik", re.I)),
    ("Orzeł", re.compile(r"Orze[łl]|Eagle", re.I)),
    ("Kangur", re.compile(r"Kangur|Kangaroo", re.I)),
]
SERIES_NAMES = [s[0] for s in SERIES]

W1_RE = re.compile(r"(?<![\d/.,])1\s*(?:oz|uncj)", re.I)
W05_RE = re.compile(r"(?<![\d/.,])(?:1/2|0[.,]5)\s*(?:oz|uncj)", re.I)

TILE_SPLIT = '<figure class="product-tile"'
UNAVAILABLE_MARK = "Produkt niedostępny"
CART_MARK = "Do koszyka"


class ScrapeError(Exception):
    pass


def series_of(name):
    for label, rx in SERIES:
        if rx.search(name):
            return label
    return None


def weight_of(name):
    if W05_RE.search(name):
        return 0.5
    if W1_RE.search(name):
        return 1.0
    return None


def parse_page(page_html):
    """Zwraca (kafelki, ostrzezenia). Kafelek: dict id, name, price, available."""
    tiles, warnings = [], []
    for chunk in page_html.split(TILE_SPLIT)[1:]:
        pid = re.search(r'data-product-id="(\d+)"', chunk)
        name = re.search(r'data-product-name="([^"]*)"', chunk)
        price = re.search(r'data-price="([\d.]+)"', chunk)
        if not (pid and name and price):
            warnings.append("kafelek bez id/nazwy/ceny")
            continue
        unavailable = UNAVAILABLE_MARK in chunk
        has_cart = CART_MARK in chunk
        if unavailable == has_cart:
            warnings.append("niejednoznaczna dostepnosc id=%s" % pid.group(1))
            continue
        tiles.append({
            "id": int(pid.group(1)),
            "name": html.unescape(name.group(1)).strip(),
            "price": float(price.group(1)),
            "available": has_cart,
        })
    return tiles, warnings


def has_next(page_html):
    return 'rel="next"' in page_html


def fetch(url, timeout=25, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise ScrapeError("pobieranie %s nie powiodlo sie: %s" % (url, last))


def scrape_all(fetcher=fetch, delay=None):
    """Pobiera wszystkie strony listy. Zwraca (kafelki, liczba_stron, ostrzezenia)."""
    delay = REQUEST_DELAY if delay is None else delay
    tiles, warnings, pages = [], [], 0
    for page in range(1, MAX_PAGES + 1):
        url = BASE + LIST_PATH + ("" if page == 1 else "/pa/%d" % page)
        page_html = fetcher(url)
        pages += 1
        t, w = parse_page(page_html)
        tiles.extend(t)
        warnings.extend(w)
        if not has_next(page_html):
            break
        time.sleep(delay)
    if pages < MIN_PAGES:
        raise ScrapeError("pobrano tylko %d stron (min. %d)" % (pages, MIN_PAGES))
    if not any(t["available"] for t in tiles):
        raise ScrapeError("brak dostepnych monet - zmiana ukladu strony?")
    return tiles, pages, warnings


def select_coins(tiles):
    """Dostepne monety 6 serii w wagach 1 oz i 1/2 oz po filtrze wykluczen."""
    out = []
    for t in tiles:
        if not t["available"]:
            continue
        if EXCLUDE_RE and EXCLUDE_RE.search(t["name"]):
            continue
        series = series_of(t["name"])
        weight = weight_of(t["name"])
        if series is None or weight is None:
            continue
        out.append({**t, "series": series, "weight": weight})
    return out


def cheapest_per_series(coins, weight):
    """Dla kazdej serii najtanszy wariant (albo None gdy brak towaru)."""
    result = []
    for label in SERIES_NAMES:
        c = [x for x in coins if x["weight"] == weight and x["series"] == label]
        result.append((label, min(c, key=lambda x: x["price"]) if c else None))
    return result
