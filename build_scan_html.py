import argparse
import csv
import datetime as dt
import html
from pathlib import Path
from zoneinfo import ZoneInfo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an HTML report from scan_results_usdt.csv with TradingView links."
    )
    parser.add_argument(
        "--input",
        default="scan_results_usdt.csv",
        help="Input CSV produced by binance_spot_candle_analyzer.py",
    )
    parser.add_argument(
        "--output",
        default="scan_results_usdt_sorted.html",
        help="Output HTML file path",
    )
    return parser.parse_args()


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_html(rows: list[dict[str, str]], source_name: str) -> str:
    rows_sorted = sorted(rows, key=lambda r: to_float(r.get("range_pct%", "0")), reverse=True)
    unique_symbols = len({r.get("symbol", "") for r in rows_sorted if r.get("symbol")})
    now_rome = dt.datetime.now(ZoneInfo("Europe/Rome"))
    now_local = now_rome.strftime("%Y-%m-%d %H:%M:%S")
    pct_values = [to_float(row.get("range_pct%", "0")) for row in rows_sorted]
    min_pct = min(pct_values, default=0.0)
    max_pct = max(pct_values, default=0.0)
    avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0

    # Percorso file simboli precedenti
    last_symbols_path = Path("docs/last_symbols.txt")
    last_symbols_path.parent.mkdir(parents=True, exist_ok=True)
    prev_symbols = set()
    if last_symbols_path.exists():
      with last_symbols_path.open("r", encoding="utf-8") as f:
        prev_symbols = set(line.strip() for line in f if line.strip())

    # Simboli attuali
    current_symbols = [r.get("symbol", "") for r in rows_sorted if r.get("symbol")]
    new_symbols = set(current_symbols) - prev_symbols

    # Salva la nuova lista simboli per la prossima scansione
    with last_symbols_path.open("w", encoding="utf-8") as f:
      for s in current_symbols:
        f.write(s + "\n")

    # Costruisci righe tabella, nuovi in alto e evidenziati
    table_rows: list[str] = []
    # Prima i nuovi simboli (evidenziati)
    for idx, row in enumerate([r for r in rows_sorted if r.get("symbol", "") in new_symbols], start=1):
      symbol = html.escape(row.get("symbol", ""))
      date = html.escape(row.get("date", ""))
      time_utc2 = html.escape(row.get("time_UTC+2", ""))
      total_range = to_float(row.get("total_range", "0"))
      prev_close = to_float(row.get("prev_close", "0"))
      range_pct = to_float(row.get("range_pct%", "0"))
      tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}"
      table_rows.append(
        "<tr class='nuovo'>"
        f"<td class='num'>{idx}</td>"
        f"<td class='symbol'>{symbol}</td>"
        f"<td>{date}</td>"
        f"<td>{time_utc2}</td>"
        f"<td class='num'>{total_range:.8f}</td>"
        f"<td class='num'>{prev_close:.8f}</td>"
        f"<td class='num pct'>{range_pct:.2f}</td>"
        f"<td><a class='tv-btn' href='{tv_url}' target='_blank' rel='noopener noreferrer'>Apri su TradingView</a></td>"
        "</tr>"
      )
    # Poi tutti gli altri simboli
    for idx, row in enumerate([r for r in rows_sorted if r.get("symbol", "") not in new_symbols], start=len(new_symbols)+1):
      symbol = html.escape(row.get("symbol", ""))
      date = html.escape(row.get("date", ""))
      time_utc2 = html.escape(row.get("time_UTC+2", ""))
      total_range = to_float(row.get("total_range", "0"))
      prev_close = to_float(row.get("prev_close", "0"))
      range_pct = to_float(row.get("range_pct%", "0"))
      tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{symbol}"
      table_rows.append(
        "<tr>"
        f"<td class='num'>{idx}</td>"
        f"<td class='symbol'>{symbol}</td>"
        f"<td>{date}</td>"
        f"<td>{time_utc2}</td>"
        f"<td class='num'>{total_range:.8f}</td>"
        f"<td class='num'>{prev_close:.8f}</td>"
        f"<td class='num pct'>{range_pct:.2f}</td>"
        f"<td><a class='tv-btn' href='{tv_url}' target='_blank' rel='noopener noreferrer'>Apri su TradingView</a></td>"
        "</tr>"
      )

    rows_html = "\n".join(table_rows)

    return f"""<!doctype html>
<html lang=\"it\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Scan Results USDT - Ordinati</title>
  <style>
    :root {{
      --bg: #f2f6f4;
      --card: #ffffff;
      --text: #1b2d2a;
      --muted: #49635f;
      --line: #cfe0db;
      --accent: #046c4e;
      --accent-soft: #e8f6f1;
      --btn: #0e7a59;
      --btn-hover: #0b6147;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: \"Trebuchet MS\", \"Segoe UI\", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 15% 10%, #d9f1e8 0%, transparent 28%),
        radial-gradient(circle at 85% 90%, #dfeef8 0%, transparent 28%),
        var(--bg);
      padding: 24px;
    }}

    .wrap {{
      max-width: 1240px;
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
      box-shadow: 0 12px 30px rgba(8, 42, 33, 0.08);
    }}

    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, #edf8f4, #e9f5fb);
    }}

    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }}

    .sub {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: #f7fcfa;
    }}

    .kpi {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fff;
    }}

    .kpi .label {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }}

    .kpi .value {{
      margin: 4px 0 0;
      font-size: 20px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}

    .table-wrap {{
      padding: 14px;
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      min-width: 1100px;
    }}

    th,
    td {{
      border: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      white-space: nowrap;
    }}

    th {{
      background: #eff9f5;
      position: sticky;
      top: 0;
      z-index: 1;
      font-weight: 700;
    }}

    tbody tr:nth-child(even) {{
      background: #fbfefd;
    }}

    tr.nuovo {{
      background: #ffe066 !important;
      font-weight: 700;
    }}

    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}

    td.symbol {{
      font-weight: 700;
      letter-spacing: 0.2px;
    }}

    td.pct {{
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }}

    .tv-btn {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 8px;
      text-decoration: none;
      color: #fff;
      background: var(--btn);
      font-weight: 600;
      font-size: 13px;
      transition: background 120ms ease;
    }}

    .tv-btn:hover {{
      background: var(--btn-hover);
    }}

    footer {{
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      padding: 12px 16px;
      background: #fbfffd;
    }}

    @media (max-width: 840px) {{
      body {{ padding: 10px; }}
      h1 {{ font-size: 20px; }}
      .kpis {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <header>
      <h1>Scan Results USDT</h1>
      <p class=\"sub\">Ordinamento: range_pct% decrescente | Ultima scansione: {now_local} (Europe/Rome)</p>
    </header>

    <section class=\"kpis\" aria-label=\"Riepilogo\">
      <article class=\"kpi\"><p class=\"label\">Eventi</p><p class=\"value\">{len(rows_sorted)}</p></article>
      <article class=\"kpi\"><p class=\"label\">Simboli unici</p><p class=\"value\">{unique_symbols}</p></article>
      <article class=\"kpi\"><p class=\"label\">Range % min</p><p class=\"value\">{min_pct:.2f}</p></article>
      <article class=\"kpi\"><p class=\"label\">Range % max</p><p class=\"value\">{max_pct:.2f}</p></article>
    </section>

    <div class=\"table-wrap\">
      <table aria-label=\"Risultati scanner USDT ordinati per percentuale\">
        <thead>
          <tr>
            <th>#</th>
            <th>symbol</th>
            <th>date</th>
            <th>time_UTC+2</th>
            <th>total_range</th>
            <th>prev_close</th>
            <th>range_pct%</th>
            <th>TradingView</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <footer>
      Fonte: {html.escape(source_name)} | Range % medio: {avg_pct:.2f}
    </footer>
  </div>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    csv_path = Path(args.input)
    html_path = Path(args.output)

    if not csv_path.exists():
        raise SystemExit(f"Input CSV non trovato: {csv_path}")

    rows = read_rows(csv_path)
    output = build_html(rows, csv_path.name)
    html_path.write_text(output, encoding="utf-8")

    print(f"HTML generato: {html_path} ({len(rows)} righe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())