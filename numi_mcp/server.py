#!/usr/bin/env python3
"""Lokalny serwer MCP dla monitora cen zlotych monet bulionowych (GoldInvest24).
Obsluguje protokol Model Context Protocol (MCP) przez standardowe wejscie/wyjscie (stdio).
"""
import json
import logging
import os
import sys
import urllib.request

LOG_FILE = os.path.join(os.path.dirname(__file__), "mcp_server.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("numi_mcp")

SERVER_API_BASE = os.environ.get(
    "NUMI_API_BASE", "http://[2a01:4f9:3b:1a9e::211]:40003"
)

TOOLS = [
    {
        "name": "get_latest_gold_prices",
        "description": (
            "Zwraca najnowsze ceny 6 glownych zlotych monet bulionowych "
            "(Krugerrand, Britannia, Lisc Klonowy, Filharmonik, Orzel, Kangur) "
            "w wadze 1 oz (1 uncja) lub 0.5 oz (pol uncji)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "weight": {
                    "type": "string",
                    "enum": ["1", "0.5"],
                    "description": "Waga monety: '1' dla 1 oz lub '0.5' dla 1/2 oz.",
                    "default": "1",
                }
            },
        },
    },
    {
        "name": "get_coin_history",
        "description": "Zwraca historie notowan cenowych dla wybranej monety (produkt_id).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "produkt_id": {
                    "type": "integer",
                    "description": "ID produktu monety (np. 138 dla Krugerranda 1 oz).",
                },
                "weight": {
                    "type": "string",
                    "enum": ["1", "0.5"],
                    "description": "Waga monety: '1' lub '0.5'.",
                    "default": "1",
                },
            },
            "required": ["produkt_id"],
        },
    },
    {
        "name": "get_monitor_health",
        "description": "Zwraca status ostatniego cyklu pobierania danych przez aplikacje.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def query_api(path):
    url = f"{SERVER_API_BASE}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "NumiLocalMCP/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def handle_get_latest_prices(args):
    weight = str(args.get("weight", "1"))
    key = "oz1" if weight == "1" else "oz05"
    data = query_api("/api/latest")
    section = data.get(key, {})
    ts = section.get("data_notowania", "brak")
    series_list = section.get("seria", [])

    lines = [f"Notowania zlotych monet ({weight} oz) z dnia {ts}:"]
    for s in series_list:
        if s.get("available"):
            chg = s.get("change")
            chg_str = f" ({chg:+.2f}%)" if chg is not None else ""
            lines.append(
                f"- {s['series']}: {s['name']} -> {s['price']:,.2f} PLN{chg_str} [id: {s['id']}]"
            )
        else:
            lines.append(f"- {s['series']}: BRAK TOWARU")
    return "\n".join(lines)


def handle_get_coin_history(args):
    pid = args.get("produkt_id")
    weight = str(args.get("weight", "1"))
    data = query_api(f"/api/historia?waga={weight}&produkt_id={pid}")
    name = data.get("name", f"Produkt #{pid}")
    points = data.get("points", [])
    if not points:
        return f"Brak historii odczytow dla monety '{name}' (id: {pid})."

    lines = [f"Historia cen dla: {name} (lacznie {len(points)} odczytow):"]
    for ts, price in points[-20:]:  # ostatnie 20
        lines.append(f"  {ts}: {price:,.2f} PLN")
    return "\n".join(lines)


def handle_get_monitor_health(_args):
    data = query_api("/health")
    run = data.get("last_run") or {}
    return (
        f"Status monitora: {data.get('status', 'nieznany')}\n"
        f"Ostatnia zbiorka: {run.get('finished_at', 'w trakcie / brak')}\n"
        f"Pobrane strony: {run.get('pages', 0)}\n"
        f"Zapisane monety: {run.get('coins', 0)}\n"
        f"Bledy: {run.get('error') or 'brak'}"
    )


def handle_call_tool(params):
    name = params.get("name")
    args = params.get("arguments", {})
    try:
        if name == "get_latest_gold_prices":
            text = handle_get_latest_prices(args)
        elif name == "get_coin_history":
            text = handle_get_coin_history(args)
        elif name == "get_monitor_health":
            text = handle_get_monitor_health(args)
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Nieznane narzedzie: {name}"}]}
        return {"content": [{"type": "text", "text": text}]}
    except Exception as exc:
        log.exception("Blad w wykonaniu narzedzia %s", name)
        return {"isError": True, "content": [{"type": "text", "text": f"Blad wykonania: {exc}"}]}


def run():
    log.info("NumiTracker Local MCP Server uruchomiony")
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "numitracker-goldinvest-local",
                        "version": "1.0.0",
                    },
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            result = handle_call_tool(req.get("params", {}))
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": result}
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        else:
            if msg_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }
            else:
                continue

        out = json.dumps(resp) + "\n"
        sys.stdout.write(out)
        sys.stdout.flush()


if __name__ == "__main__":
    run()
