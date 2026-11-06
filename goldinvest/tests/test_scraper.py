import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import db  # noqa: E402
import scraper  # noqa: E402


def tile(pid, name, price, available=True):
    action = (
        '<button>Do koszyka</button><span>Dodaj do koszyka produkt %s</span>' % name
        if available
        else '<div class="saleout">Produkt niedostępny</div>'
    )
    return (
        '<figure class="product-tile"><div data-price="%s" data-price-type="|show_type" data-product-id="%d" '
        'data-product-name="%s"></div>%s</figure>' % (price, pid, name, action)
    )


PAGE = "".join([
    tile(138, "Złota moneta Krugerrand 1 oz", 16223.26),
    tile(832, "Złota moneta Krugerrand 1 oz — drugi gatunek", 16279.08),
    tile(849, "Złota moneta Britannia 1/2 uncji — mieszane roczniki", 6420.08, False),
    tile(1291, "Złota moneta Britannia 1/2 uncji Karol III — 2026", 8407.55),
    tile(1728, "Złota moneta Britannia i Liberty 1 uncja — 2026", 16352.07),
    tile(1661, "Złota moneta Kanadyjski Liść Klonowy 1 uncja .99999", 16881.73),
    tile(1738, "Złota moneta Kanadyjski Liść Klonowy 1 uncja — 2027", 16378.73),
    tile(1383, "Złota moneta Wiedeński Filharmonik 1/4 uncji — 2026", 4327.76),
    tile(83, "Złota moneta Wiedeński Filharmonik 1 uncja", 16343.19),
    tile(433, "Złota moneta Amerykański Orzeł 1 uncja", 16457.45),
    tile(1349, "Złota moneta Chińska Panda 3 g — 2026", 1788.19),
    tile(1118, "Złota moneta Wiedeński Filharmonik 1 uncja — nominał 100 euro", 12188.65, False),
    tile(438, "Złoty Kangur 1 uncja", 16298.77),
    tile(1289, "Złota moneta Britannia 1/10 uncji Karol III — 2026", 1718.69),
])


def test_parse_tiles_and_availability():
    tiles, warnings = scraper.parse_page(PAGE)
    assert not warnings
    assert len(tiles) == 14
    by_id = {t["id"]: t for t in tiles}
    assert by_id[849]["available"] is False
    assert by_id[138]["available"] is True
    assert by_id[138]["price"] == 16223.26
    assert "Złota moneta" in by_id[138]["name"]


def test_ambiguous_tile_is_warning():
    bad = '<figure class="product-tile"><div data-price="1.0" data-product-id="1" data-product-name="x"></div></figure>'
    tiles, warnings = scraper.parse_page(bad)
    assert tiles == [] and warnings


def test_weight_and_series():
    assert scraper.weight_of("Krugerrand 1 oz") == 1.0
    assert scraper.weight_of("Britannia 1/2 uncji — 2026") == 0.5
    assert scraper.weight_of("Krugerrand 1/10 uncji") is None
    assert scraper.weight_of("Filharmonik 1/4 uncji") is None
    assert scraper.weight_of("Lunar 2 uncje") is None
    assert scraper.weight_of("Panda 3 g") is None
    assert scraper.series_of("Złoty Kangur 1 uncja") == "Kangur"
    assert scraper.series_of("Amerykański Orzeł 1 uncja") == "Orzeł"
    assert scraper.series_of("Kanadyjski Liść Klonowy 1 uncja") == "Liść Klonowy"


def test_select_coins_filters_availability_and_exclusions():
    tiles, _ = scraper.parse_page(PAGE)
    coins = scraper.select_coins(tiles)
    ids = {c["id"] for c in coins}
    assert ids == {138, 1291, 1738, 83, 433, 438}
    # niedostepne (849, 1118), wykluczone (832, 1728, 1661) i inne wagi odpadaja
    assert not ids & {849, 1118, 832, 1728, 1661, 1383, 1289, 1349}


def test_cheapest_per_series_marks_missing():
    tiles, _ = scraper.parse_page(PAGE)
    coins = scraper.select_coins(tiles)
    half = dict(scraper.cheapest_per_series(coins, 0.5))
    assert half["Britannia"]["id"] == 1291
    assert half["Kangur"] is None
    one = dict(scraper.cheapest_per_series(coins, 1.0))
    assert one["Krugerrand"]["id"] == 138
    assert one["Britannia"] is None


def test_db_insert_and_history():
    with tempfile.TemporaryDirectory() as d:
        conn = db.connect(os.path.join(d, "t.sqlite"))
        coins = [{"id": 138, "name": "Krugerrand 1 oz", "price": 100.0}]
        db.insert_coins(conn, 1.0, coins, "2026-11-05T10:00:00Z")
        coins[0]["price"] = 110.0
        db.insert_coins(conn, 1.0, coins, "2026-11-05T10:15:00Z")
        db.insert_coins(conn, 0.5, [{"id": 1291, "name": "Britannia 1/2 uncji", "price": 50.0}], "2026-11-05T10:15:00Z")
        conn.commit()
        assert db.last_timestamp(conn, 1.0) == "2026-11-05T10:15:00Z"
        assert db.previous_price(conn, 1.0, 138, "2026-11-05T10:15:00Z") == 100.0
        assert [r["cena_pln"] for r in db.history(conn, 1.0, 138)] == [100.0, 110.0]
        assert conn.execute("SELECT waga_oz FROM oz05").fetchone()[0] == 0.5
        cols = [r[1] for r in conn.execute("PRAGMA table_info(oz1)")]
        assert cols == ["id", "produkt_id", "nazwa", "data_notowania", "cena_pln", "waga_oz"]
        conn.close()
