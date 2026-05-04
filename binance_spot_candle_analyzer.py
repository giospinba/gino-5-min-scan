import argparse
import concurrent.futures
import datetime
import os
import sys
import time
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- INIZIO AGGIUNTA BITGET E MARKET CAP ---
import json

def fetch_bitget_symbols(session: requests.Session, market_type: str = "spot") -> list:
    symbols = set()
    if market_type == "spot":
        url = "https://api.bitget.com/api/v2/spot/public/symbols"
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            s = item.get("symbol")
            if s:
                # Bitget spot v2: simboli tipo BTCUSDT_SPBL
                s = s.split('_')[0]
                symbols.add(s)
    elif market_type == "futures":
        url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            s = item.get("symbol")
            if s:
                # Bitget futures v2: simboli tipo BTCUSDTUMCBL
                # Normalizza a BTCUSDT
                if s.endswith("UMCBL"):
                    s = s[:-6]
                symbols.add(s)
    else:
        raise ValueError("market_type deve essere 'spot' o 'futures'")
    return sorted(symbols)

def fetch_binance_symbols(quote_assets: list, session: requests.Session) -> list:
    return fetch_symbols(quote_assets, session)

def fetch_market_caps(symbols: list, session: requests.Session) -> dict:
    # Scarica la lista completa CoinGecko (id, symbol)
    cg_list_url = "https://api.coingecko.com/api/v3/coins/list"
    cg_resp = session.get(cg_list_url, timeout=30)
    cg_resp.raise_for_status()
    cg_list = cg_resp.json()
    # Mappa symbol (es: BTC) -> [id, ...]
    symbol_to_ids = {}
    for coin in cg_list:
        sym = coin.get('symbol', '').upper()
        if sym:
            symbol_to_ids.setdefault(sym, []).append(coin['id'])

    # Estrai base symbol (BTC) da BTCUSDT
    base_symbols = [s[:-4].upper() if s.endswith('USDT') else s.upper() for s in symbols]
    # Mappa simbolo a CoinGecko id (prendi il primo id disponibile)
    symbol_to_id = {}
    for s, base in zip(symbols, base_symbols):
        ids = symbol_to_ids.get(base, [])
        if ids:
            symbol_to_id[s] = ids[0]
    # Richiedi market cap solo per i simboli mappati
    url = "https://api.coingecko.com/api/v3/coins/markets"
    market_caps = {}
    ids = list(symbol_to_id.values())
    for i in range(0, len(ids), 250):
        params = {
            "vs_currency": "usd",
            "ids": ','.join(ids[i:i+250]),
        }
        r = session.get(url, params=params, timeout=20)
        if r.status_code == 200:
            for coin in r.json():
                # Trova tutti i simboli che mappano a questo id
                for sym, cid in symbol_to_id.items():
                    if cid == coin['id']:
                        market_caps[sym] = coin.get('market_cap', 0)
    return market_caps

def get_filtered_bitget_symbols(session: requests.Session, min_market_cap=5_500_000):
    # 1. Ottieni spot e futures Bitget
    spot = fetch_bitget_symbols(session, "spot")
    fut = fetch_bitget_symbols(session, "futures")
    all_bitget = set(spot) | set(fut)
    print(f"# Coppie Bitget totali (spot+futures): {len(all_bitget)}", file=sys.stderr)
    # 2. Ottieni Binance spot
    binance = set(fetch_binance_symbols(["USDT"], session))
    print(f"# Coppie Binance spot USDT: {len(binance)}", file=sys.stderr)
    # 3. Escludi quelle già su Binance
    only_bitget = sorted(all_bitget - binance)
    print(f"# Coppie Bitget esclusive: {len(only_bitget)}", file=sys.stderr)
    # 4. Filtra per market cap
    market_caps = fetch_market_caps(only_bitget, session)
    mapped = [s for s in only_bitget if s in market_caps]
    print(f"# Coppie Bitget esclusive mappate su CoinGecko: {len(mapped)}", file=sys.stderr)
    filtered = [s for s in only_bitget if (market_caps.get(s, 0) or 0) >= min_market_cap]
    print(f"# Coppie Bitget esclusive con market cap >= {min_market_cap}: {len(filtered)}", file=sys.stderr)
    return filtered
# --- FINE AGGIUNTA ---

BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")


def fetch_symbols(quote_assets: List[str], session: requests.Session) -> List[str]:
    url = f"{BASE_URL}/api/v3/exchangeInfo"
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"# Error fetching symbols: {exc}", file=sys.stderr)
        return []
    data = response.json()
    symbols = []
    for sym in data.get("symbols", []):
        if sym.get("status") != "TRADING":
            continue
        if sym.get("isSpotTradingAllowed") is not True:
            continue
        if quote_assets:
            if sym.get("quoteAsset") not in quote_assets:
                continue
        symbols.append(sym["symbol"])
    return sorted(symbols)


def fetch_klines(
    symbol: str,
    interval: str,
    start_ts: int,
    end_ts: int,
    session: requests.Session,
) -> List[List[Any]]:
    candles: List[List[Any]] = []
    url = f"{BASE_URL}/api/v3/klines"
    while start_ts < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ts,
            "endTime": end_ts,
            "limit": 1000,
        }

        response = None
        for attempt in range(5):
            try:
                response = session.get(url, params=params, timeout=20)
            except requests.RequestException as exc:
                if attempt < 4:
                    time.sleep(0.5 + attempt * 0.5)
                    continue
                raise RuntimeError(f"Errore network fetching klines for {symbol}: {exc}")

            if response.status_code == 200:
                break
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(1 + attempt * 0.5)
                continue
            raise RuntimeError(
                f"Errore fetching klines for {symbol}: {response.status_code} {response.text}"
            )
        else:
            raise RuntimeError(f"Errore persistente fetching klines per {symbol}")

        batch = response.json()
        if not batch:
            break
        candles.extend(batch)
        if len(batch) < 1000:
            break
        last_open = int(batch[-1][0])
        start_ts = last_open + 1
    return candles


def scan_symbol(
    symbol: str,
    start_time: int,
    end_time: int,
    session: requests.Session,
    range_threshold_pct: float = 0.20,
) -> Dict[str, Any]:
    start_perf = time.perf_counter()
    try:
        candles = fetch_klines(symbol, "5m", start_time, end_time, session)
        matches = analyze_candles(symbol, candles, range_threshold_pct)
        duration = time.perf_counter() - start_perf
        return {
            "symbol": symbol,
            "matches": matches,
            "error": None,
            "duration": duration,
            "candles": len(candles),
        }
    except Exception as exc:
        duration = time.perf_counter() - start_perf
        return {
            "symbol": symbol,
            "matches": [],
            "error": str(exc),
            "duration": duration,
            "candles": 0,
        }


def analyze_candles(symbol: str, candles: List[List[Any]], range_threshold_pct: float = 0.20) -> List[Dict[str, Any]]:
    parsed: List[Dict[str, Any]] = []

    for k in candles:
        o = float(k[1])
        h = float(k[2])
        l = float(k[3])
        c = float(k[4])
        parsed.append(
            {
                "open_time": int(k[0]),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
            }
        )

    if len(parsed) < 2:
        return []

    results: List[Dict[str, Any]] = []

    for idx in range(1, len(parsed)):
        curr = parsed[idx]
        prev = parsed[idx - 1]

        o = curr["open"]
        c = curr["close"]
        if c >= o:
            continue

        body = o - c
        high = curr["high"]
        low = curr["low"]
        total_range = high - low
        prev_close = prev["close"]
        
        range_threshold = range_threshold_pct * prev_close
        if total_range < range_threshold:
            continue

        upper_wick = high - o
        lower_wick = c - low
        total_spikes = max(0.0, upper_wick) + max(0.0, lower_wick)

        if total_spikes >= body:
            continue
        if upper_wick <= 0 and lower_wick <= 0:
            continue

        results.append(
            {
                "symbol": symbol,
                "open_time": curr["open_time"],
                "high": high,
                "low": low,
                "total_range": total_range,
                "prev_close": prev_close,
                "range_pct": (total_range / prev_close * 100) if prev_close > 0 else 0.0,
                "body": body,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
            }
        )

    return results


def format_utc2(timestamp_ms: int) -> str:
    utc_dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0, datetime.timezone.utc)
    offset = datetime.timedelta(hours=2)
    local_dt = utc_dt + offset
    return local_dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analizza candele Binance Spot 5-min per impulsi short validi."
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Una coppia Binance da analizzare, es. BTCUSDT. Se omessa, usa quote-assets o tutte le coppie."
    )
    parser.add_argument(
        "--quote-assets",
        nargs="*",
        default=["USDT"],
        help="Mantiene solo coppie USDT (compatibilita' con versioni precedenti)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compatibilita' con versioni precedenti: la scansione resta limitata a USDT."
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=0,
        help="Numero massimo di simboli da elaborare. 0 = tutte le coppie trovate."
    )
    parser.add_argument(
        "--range-threshold",
        type=float,
        default=0.20,
        help="Soglia di range percentuale (es. 0.15 per +15%%, 0.20 per +20%%)."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Numero di thread paralleli per la scansione."
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Percorso del file di log dove salvare i tempi e il riepilogo della scansione."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=31,
        help="Numero di giorni da analizzare."
    )
    parser.add_argument(
        "--bitget",
        action="store_true",
        help="Analizza solo le coppie Bitget (spot+futures), escluse quelle già su Binance e con market cap < 5.5M."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=max(10, args.workers * 2),
        pool_maxsize=max(10, args.workers * 2),
    )
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "binance-spot-candle-analyzer/1.0"})

    if args.symbol:
        symbol = args.symbol.upper()
        if not symbol.endswith("USDT"):
            print("# Errore: --symbol deve essere una coppia USDT (es. BTCUSDT).", file=sys.stderr)
            return 1
        symbols = [symbol]
    elif getattr(args, "bitget", False):
        print("# Uso solo coppie Bitget (spot+futures), escluse quelle su Binance e con market cap < 5.5M", file=sys.stderr)
        symbols = get_filtered_bitget_symbols(session, min_market_cap=5_500_000)
        print(f"# Simboli Bitget filtrati: {len(symbols)}", file=sys.stderr)
        if args.max_symbols > 0:
            symbols = symbols[: args.max_symbols]
    else:
        quote_assets = ["USDT"]
        symbols = fetch_symbols(quote_assets, session)
        if args.max_symbols > 0:
            symbols = symbols[: args.max_symbols]

    end_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    start_time = end_time - args.days * 24 * 60 * 60 * 1000

    print("symbol,date,time_UTC+2,total_range,prev_close,range_pct%")
    results: List[Dict[str, Any]] = []
    scan_records: List[Dict[str, Any]] = []
    scan_start = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_symbol = {
            executor.submit(scan_symbol, symbol, start_time, end_time, session, args.range_threshold): symbol
            for symbol in symbols
        }
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                task_result = future.result()
            except Exception as exc:
                print(f"# Errore interno {symbol}: {exc}", file=sys.stderr)
                scan_records.append(
                    {"symbol": symbol, "error": str(exc), "duration": 0.0, "candles": 0, "matches": 0}
                )
                continue

            scan_records.append(
                {
                    "symbol": task_result["symbol"],
                    "error": task_result["error"],
                    "duration": task_result["duration"],
                    "candles": task_result["candles"],
                    "matches": len(task_result["matches"]),
                }
            )

            if task_result["error"]:
                print(f"# Errore {symbol}: {task_result['error']}", file=sys.stderr)
                continue

            results.extend(task_result["matches"])

    total_duration = time.perf_counter() - scan_start
    results.sort(key=lambda item: (item["symbol"], item["open_time"]))
    for match in results:
        date_str = format_utc2(match["open_time"]).split()[0]
        time_str = format_utc2(match["open_time"]).split()[1]
        print(
            f"{match['symbol']},{date_str},{time_str},{match['total_range']:.8f},"
            f"{match['prev_close']:.8f},{match['range_pct']:.2f}"
        )

    if args.log_file:
        with open(args.log_file, "w", encoding="utf-8") as log_fd:
            log_fd.write(f"scan_start={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
            log_fd.write(f"scan_duration_s={total_duration:.3f}\n")
            log_fd.write(f"symbols_requested={len(symbols)}\n")
            log_fd.write(f"symbols_scanned={len(scan_records)}\n")
            log_fd.write(f"rows_output={len(results)}\n")
            log_fd.write("symbol,error,duration_s,candles,matches\n")
            for record in scan_records:
                log_fd.write(
                    f"{record['symbol']},{record['error'] or ''},{record['duration']:.3f},"
                    f"{record['candles']},{record['matches']}\n"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
