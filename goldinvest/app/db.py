import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
CREATE TABLE IF NOT EXISTS oz1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produkt_id INTEGER NOT NULL,
    nazwa TEXT NOT NULL,
    data_notowania TEXT NOT NULL,
    cena_pln REAL NOT NULL,
    waga_oz REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oz05 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produkt_id INTEGER NOT NULL,
    nazwa TEXT NOT NULL,
    data_notowania TEXT NOT NULL,
    cena_pln REAL NOT NULL,
    waga_oz REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oz1_prod_czas ON oz1(produkt_id, data_notowania);
CREATE INDEX IF NOT EXISTS idx_oz05_prod_czas ON oz05(produkt_id, data_notowania);
CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    pages INTEGER,
    coins INTEGER,
    error TEXT
);
"""

TABLES = {1.0: "oz1", 0.5: "oz05"}


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def get_conn(path):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def table_for(weight):
    return TABLES[float(weight)]


def insert_coins(conn, weight, coins, ts):
    tbl = table_for(weight)
    conn.executemany(
        "INSERT INTO %s (produkt_id, nazwa, data_notowania, cena_pln, waga_oz) VALUES (?,?,?,?,?)" % tbl,
        [(c["id"], c["name"], ts, c["price"], float(weight)) for c in coins],
    )


def last_timestamp(conn, weight):
    row = conn.execute("SELECT MAX(data_notowania) AS t FROM %s" % table_for(weight)).fetchone()
    return row["t"] if row else None


def rows_at(conn, weight, ts):
    return conn.execute(
        "SELECT produkt_id, nazwa, cena_pln FROM %s WHERE data_notowania = ?" % table_for(weight), (ts,)
    ).fetchall()


def previous_price(conn, weight, produkt_id, before_ts):
    row = conn.execute(
        "SELECT cena_pln FROM %s WHERE produkt_id = ? AND data_notowania < ? ORDER BY data_notowania DESC LIMIT 1"
        % table_for(weight),
        (produkt_id, before_ts),
    ).fetchone()
    return row["cena_pln"] if row else None


def coin_list(conn, weight):
    return conn.execute(
        "SELECT produkt_id, nazwa FROM %s GROUP BY produkt_id ORDER BY MAX(data_notowania) DESC, nazwa"
        % table_for(weight)
    ).fetchall()


def history(conn, weight, produkt_id):
    rows = conn.execute(
        "SELECT nazwa, data_notowania, cena_pln FROM %s WHERE produkt_id = ? ORDER BY data_notowania" % table_for(weight),
        (produkt_id,),
    ).fetchall()
    return rows


def start_run(conn, ts):
    cur = conn.execute("INSERT INTO scrape_runs (started_at) VALUES (?)", (ts,))
    return cur.lastrowid


def finish_run(conn, run_id, ts, pages=None, coins=None, error=None):
    conn.execute(
        "UPDATE scrape_runs SET finished_at=?, pages=?, coins=?, error=? WHERE id=?",
        (ts, pages, coins, error, run_id),
    )


def last_run(conn):
    return conn.execute("SELECT * FROM scrape_runs ORDER BY id DESC LIMIT 1").fetchone()
