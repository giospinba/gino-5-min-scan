# Binance Spot Candle Analyzer

Questo progetto analizza le candele a 5 minuti del mercato spot Binance e individua le candele bearish (short) con body rilevante.

## Funzionalità

- Scarica dati spot da Binance
- Filtra le candele a 5 minuti negli ultimi 31 giorni
- Considera valide solo le candele bearish in cui:
  - il corpo è maggiore del 20% dell'intervallo medio delle ultime 31 giornate
  - la somma delle spike (ombre) è inferiore al corpo
  - è presente almeno una spike
- Stampa output con coppia, orario (UTC+2) e valore corpo candela

## Requisiti

- Python 3.9+
- `requests`

## Installazione

```bash
python -m pip install -r requirements.txt
```

## Esempio di esecuzione

```bash
python binance_spot_candle_analyzer.py --quote-assets USDT BUSD --max-symbols 20
```

Per analizzare una singola coppia:

```bash
python binance_spot_candle_analyzer.py --symbol BTCUSDT
```

## Link pubblico sempre attivo (senza tunnel)

Per avere una pagina pubblica stabile e aggiornata ogni giorno, usa GitHub Pages con la workflow inclusa in `.github/workflows/daily-pages.yml`.

### 1) Primo setup (una sola volta)

1. Crea un repository su GitHub e carica questi file.
2. In GitHub apri `Settings > Pages`.
3. In `Build and deployment`, seleziona `Source: GitHub Actions`.
4. Avvia una prima esecuzione manuale da `Actions > Daily USDT Scan Pages > Run workflow`.

### 2) URL fisso pubblico

Il link pubblico restera' sempre lo stesso:

```text
https://<tuo-utente-github>.github.io/<nome-repository>/
```

### 3) Aggiornamento automatico giornaliero

La workflow esegue ogni giorno:

- scansione USDT
- generazione HTML ordinato con pulsanti TradingView
- pubblicazione su GitHub Pages

Orario cron attuale: `06:05 UTC`.

### 4) Esecuzione locale facoltativa

Puoi lanciare lo stesso flusso in locale con:

```bash
chmod +x scripts/daily_scan.sh
PYTHON_BIN="/Users/utente/GINO 5 MIN/.venv/bin/python" scripts/daily_scan.sh
```

Output pagina pubblicabile: `docs/index.html`.
