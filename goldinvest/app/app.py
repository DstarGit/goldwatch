import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request

import db
import scraper

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/numi.sqlite")
INTERVAL = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "900"))
OZ05_MIN_GAP = timedelta(minutes=int(os.environ.get("OZ05_MIN_GAP_MINUTES", "25")))
TZ = ZoneInfo("Europe/Warsaw")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)
_scrape_lock = threading.Lock()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def format_pln(value):
    if value is None:
        return "—"
    return "{:,.2f}".format(value).replace(",", "\u00a0").replace(".", ",") + "\u00a0zł"


def format_dt(value):
    if not value:
        return "—"
    return parse_ts(value).astimezone(TZ).strftime("%d.%m.%Y %H:%M")


app.jinja_env.filters["pln"] = format_pln
app.jinja_env.filters["dt"] = format_dt


def run_scrape():
    if not _scrape_lock.acquire(blocking=False):
        log.info("poprzedni cykl jeszcze trwa - pomijam")
        return
    started = utc_now()
    conn = db.connect(DATABASE_PATH)
    run_id = db.start_run(conn, started)
    conn.commit()
    try:
        tiles, pages, warnings = scraper.scrape_all()
        for w in warnings:
            log.warning("parser: %s", w)
        coins = scraper.select_coins(tiles)
        ts = utc_now()
        n = 0
        c1 = [c for c in coins if c["weight"] == 1.0]
        db.insert_coins(conn, 1.0, c1, ts)
        n += len(c1)
        last05 = db.last_timestamp(conn, 0.5)
        if last05 is None or parse_ts(ts) - parse_ts(last05) >= OZ05_MIN_GAP:
            c05 = [c for c in coins if c["weight"] == 0.5]
            db.insert_coins(conn, 0.5, c05, ts)
            n += len(c05)
        db.finish_run(conn, run_id, utc_now(), pages=pages, coins=n)
        conn.commit()
        log.info("cykl ok: stron=%d, zapisano=%d", pages, n)
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        db.finish_run(conn, run_id, utc_now(), error=str(exc)[:300])
        conn.commit()
        log.error("cykl nieudany: %s", exc)
    finally:
        conn.close()
        _scrape_lock.release()


def scrape_loop():
    time.sleep(5)
    while True:
        try:
            run_scrape()
        except Exception:  # noqa: BLE001
            log.exception("blad petli")
        time.sleep(INTERVAL)


def build_table(conn, weight):
    ts = db.last_timestamp(conn, weight)
    rows = db.rows_at(conn, weight, ts) if ts else []
    by_series = {}
    for r in rows:
        s = scraper.series_of(r["nazwa"])
        if s and (s not in by_series or r["cena_pln"] < by_series[s]["cena_pln"]):
            by_series[s] = r
    table = []
    for label in scraper.SERIES_NAMES:
        r = by_series.get(label)
        if r is None:
            table.append({"series": label, "available": False})
            continue
        prev = db.previous_price(conn, weight, r["produkt_id"], ts)
        change = None if prev in (None, 0) else (r["cena_pln"] - prev) / prev * 100
        table.append({"series": label, "available": True, "id": r["produkt_id"], "name": r["nazwa"],
                      "price": r["cena_pln"], "change": change})
    return ts, table


@app.route("/")
def index():
    conn = db.connect(DATABASE_PATH)
    try:
        t1_ts, t1 = build_table(conn, 1.0)
        t05_ts, t05 = build_table(conn, 0.5)
        coins = {"1": db.coin_list(conn, 1.0), "0.5": db.coin_list(conn, 0.5)}
        run = db.last_run(conn)
    finally:
        conn.close()
    return render_template("index.html", t1=t1, t1_ts=t1_ts, t05=t05, t05_ts=t05_ts, coins=coins, run=run,
                           interval=INTERVAL // 60)


@app.route("/api/historia")
def api_history():
    weight = request.args.get("waga", "1")
    try:
        w = float(weight)
        pid = int(request.args.get("produkt_id", ""))
        if w not in (1.0, 0.5):
            raise ValueError
    except ValueError:
        return jsonify({"error": "bad request"}), 400
    conn = db.connect(DATABASE_PATH)
    try:
        rows = db.history(conn, w, pid)
    finally:
        conn.close()
    if not rows:
        return jsonify({"name": "", "points": []})
    return jsonify({"name": rows[-1]["nazwa"], "points": [[r["data_notowania"], r["cena_pln"]] for r in rows]})


@app.route("/api/latest")
def api_latest():
    conn = db.connect(DATABASE_PATH)
    try:
        out = {}
        for key, w in (("oz1", 1.0), ("oz05", 0.5)):
            ts, table = build_table(conn, w)
            out[key] = {"data_notowania": ts, "seria": table}
    finally:
        conn.close()
    return jsonify(out)


@app.route("/health")
def health():
    conn = db.connect(DATABASE_PATH)
    try:
        run = db.last_run(conn)
    finally:
        conn.close()
    return jsonify({"status": "ok", "last_run": dict(run) if run else None})


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def start_background():
    threading.Thread(target=scrape_loop, name="scraper", daemon=True).start()


start_background()
