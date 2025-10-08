# Fyers DataScrapper

Real-time Fyers contract builder and data recorder. It logs LTP ticks for monthly futures/options and weekly options around ATM for symbols configured in `TradeSettings.csv`, and appends them to per-symbol CSV files under a daily folder.

## Features
- Reads user settings from `TradeSettings.csv`:
  - Monthly expiry (`MonthExp`)
  - Weekly expiries list (`WeekExp`)
  - Strike rounding step (`StrikeStep`)
  - Number of steps around ATM (`Step`)
- Generates and subscribes to:
  - Monthly future: `NSE:{SYMBOL}{YYMMM}FUT`
  - Monthly options: ATM ± Step with `StrikeStep`
  - Weekly options: for each weekly expiry with code `YY{M}{DD}` (e.g. `25O14`)
- Subscribes via Fyers WebSocket and writes a row every second per symbol.
- CSV columns: `symbol, ltp, last_traded_qty, vol_traded_today, timestamp` (local human-readable time)
- Daily folder rotation; previous days remain preserved.

## Project Structure
```
Fyers DataScrapper/
  main.py
  FyresIntegration.py
  TradeSettings.csv
  FyersCredentials.csv   # NOT tracked in git; contains secrets
  requirements.txt
  database/              # runtime output (ignored by git)
  venv/                  # local virtual env (ignored by git)
```

## Prerequisites
- Python 3.12+
- Fyers API credentials (Client ID, Secret, etc.)

## Install
```bash
# Create and activate venv (Windows PowerShell)
python -m venv venv
./venv/Scripts/Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Configure Credentials
Fill `FyersCredentials.csv` with your values:

```
Title,Value
client_id,<your_client_id>
secret_key,<your_secret_key>
redirect_uri,<your_redirect_uri>
response_type,code
grant_type,authorization_code
state,none
totpkey,<your_totp_key>
FY_ID,<your_fyers_id>
PIN,<your_pin>
```

This file is ignored by git. Do not commit it.

## Configure Trade Settings
`TradeSettings.csv` example:
```
Symbol,MonthExp,WeekExp,StrikeStep,Step
NIFTY,30-10-2025,"14-10-2025,21-10-2025",50,2
```
- MonthExp: `DD-MM-YYYY`
- WeekExp: comma-separated `DD-MM-YYYY` values
- StrikeStep: option strike spacing (e.g., 50)
- Step: number of steps around ATM (2 → generates 5 strikes: -2,-1,0,+1,+2)

## Run
```bash
# Ensure venv is active
python main.py
```
The app will:
1) Log into Fyers automatically (TOTP + PIN flow).
2) Build the contract list from `TradeSettings.csv`.
3) Start the WebSocket and begin writing CSVs once per second to `database/<DDMONYYYY>/`.

Example output path for Oct 8, 2025:
```
database/08OCT2025/NIFTY25O1425000CE.csv
```
Each row contains the latest tick at the time of the write loop.

## Data Retention
- The `database/` folder is never deleted by the script.
- Each day a new folder `DDMONYYYY` is created; older days remain intact.
- If the process runs past midnight, it automatically rolls over to a new date folder on the next write iteration.

## Notes
- WebSocket symbols are built as per Fyers format; weekly code uses single-letter month (J, F, M, A, M, J, J, A, S, O, N, D) and day number.
- Timestamp in CSV is local time (`YYYY-MM-DD HH:MM:SS`).
- If any symbol has no recent tick yet, it is skipped until data arrives.

## Git Hygiene
The repository ignores runtime data and secrets:
- `database/`, `venv/`, `__pycache__/`, `*.py[codwz]*`
- `.env*`, IDE folders, build artifacts

## Troubleshooting
- If login fails, verify all fields in `FyersCredentials.csv` and ensure TOTP time is in sync.
- Ensure your system’s clock is correct; TOTP is time-based.
- If no CSV files appear, confirm WebSocket connectivity and that contracts exist for your configured expiries/strikes.

## License
Proprietary. All rights reserved by the project owner.
