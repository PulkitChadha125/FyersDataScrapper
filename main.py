import pandas as pd
import datetime  # full module
import json
# from datetime import datetime, timedelta

from FyresIntegration import *
import time
import traceback
import sys
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading as _threading
import os

# Ensure the SDK path is included for import
sys.path.append('.')

FyerSymbolList=[]

def normalize_to_step(price, step):
    if price is None or step in (None, 0):
        return price
    step = float(step)
    # nearest (half-up): 22325->22350, 22322->22300
    return step * math.floor((float(price) + step / 2.0) / step)



def get_api_credentials_Fyers():
    credentials_dict_fyers = {}
    try:
        df = pd.read_csv('FyersCredentials.csv')
        for index, row in df.iterrows():
            title = row['Title']
            value = row['Value']
            credentials_dict_fyers[title] = value
    except pd.errors.EmptyDataError:
        print("The CSV FyersCredentials.csv file is empty or has no data.")
    except FileNotFoundError:
        print("The CSV FyersCredentials.csv file was not found.")
    except Exception as e:
        print("An error occurred while reading the CSV FyersCredentials.csv file:", str(e))
    return credentials_dict_fyers

def get_user_settings():
    global result_dict, instrument_id_list, Equity_instrument_id_list, Future_instrument_id_list, FyerSymbolList
    from datetime import datetime
    import pandas as pd


    try:
        csv_path = 'TradeSettings.csv'
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()

        result_dict = {}
        instrument_id_list = []
        Equity_instrument_id_list = []
        Future_instrument_id_list = []
        FyerSymbolList = []
        # unique_key = f"{symbol}_{OptionType}_{Strike}"

        for index, row in df.iterrows():
            try:
                symbol = str(row['Symbol']).strip()

                # Parse MonthExp (format: DD-MM-YYYY). Allow empty/NaN
                month_exp_raw = row.get('MonthExp') if 'MonthExp' in df.columns else None
                month_exp = None
                if pd.notna(month_exp_raw) and str(month_exp_raw).strip() != "":
                    month_exp = datetime.strptime(str(month_exp_raw).strip(), '%d-%m-%Y').date()

                # Parse WeekExp as list of dates (comma-separated DD-MM-YYYY)
                week_exp_list = []
                week_exp_raw = row.get('WeekExp') if 'WeekExp' in df.columns else None
                if pd.notna(week_exp_raw) and str(week_exp_raw).strip() != "":
                    for part in str(week_exp_raw).split(','):
                        part = part.strip()
                        if part:
                            week_exp_list.append(datetime.strptime(part, '%d-%m-%Y').date())

                # Load numeric settings
                strike_step = None
                if 'StrikeStep' in df.columns and pd.notna(row.get('StrikeStep')):
                    try:
                        strike_step = float(row.get('StrikeStep'))
                    except Exception:
                        strike_step = None

                step = None
                if 'Step' in df.columns and pd.notna(row.get('Step')):
                    try:
                        step = int(row.get('Step'))
                    except Exception:
                        # fallback to float if not an integer
                        try:
                            step = int(float(row.get('Step')))
                        except Exception:
                            step = None

                symbol_dict = {
                    "Symbol": symbol,
                    "MonthExp": month_exp,            # date or None
                    "WeekExp": week_exp_list,         # list[date]
                    "StrikeStep": strike_step,        # float or None
                    "Step": step                      # int or None
                }

                # Contracts accumulator (use a set for uniqueness)
                contracts_set = set()

                # ---------- Monthly FUT ----------
                if month_exp is not None:
                    new_date_string = month_exp.strftime('%y%b').upper()  # e.g., 25JUN
                    fut_symbol = f"NSE:{symbol}{new_date_string}FUT"
                    contracts_set.add(fut_symbol)

                    # ---------- Monthly Options (ATM ± steps) ----------
                    try:
                        ltp = get_ltp(fut_symbol)
                    except Exception:
                        ltp = None

                    atm = normalize_to_step(ltp, strike_step) if ltp is not None else None
                    if atm is not None and strike_step is not None and step is not None:
                        strikes = [int(atm + i * strike_step) for i in range(-step, step + 1)]
                        for strike in strikes:
                            ce = f"NSE:{symbol}{new_date_string}{strike}CE"
                            pe = f"NSE:{symbol}{new_date_string}{strike}PE"
                            contracts_set.add(ce)
                            contracts_set.add(pe)

                # ---------- Weekly Options for each expiry ----------
                def week_code(d):
                    # Format: YY + single-letter month + DD (example: 25O14)
                    yy = d.strftime('%y')
                    month_idx = d.month
                    month_letter_map = {
                        1: 'J', 2: 'F', 3: 'M', 4: 'A', 5: 'M', 6: 'J',
                        7: 'J', 8: 'A', 9: 'S', 10: 'O', 11: 'N', 12: 'D'
                    }
                    ml = month_letter_map.get(month_idx, d.strftime('%b')[0].upper())
                    dd = d.strftime('%d')
                    return f"{yy}{ml}{dd}"

                if week_exp_list:
                    # Use the same ATM baseline as monthly (fut_symbol) if available; otherwise try spot-like symbol if needed
                    # Compute ATM once per symbol to use across weekly expiries
                    base_ltp = None
                    if month_exp is not None:
                        try:
                            base_ltp = get_ltp(fut_symbol)
                        except Exception:
                            base_ltp = None
                    if base_ltp is not None and strike_step is not None:
                        atm_week = normalize_to_step(base_ltp, strike_step)
                    else:
                        atm_week = None

                    for wd in week_exp_list:
                        code = week_code(wd)
                        if atm_week is not None and strike_step is not None and step is not None:
                            strikes_w = [int(atm_week + i * strike_step) for i in range(-step, step + 1)]
                            for strike in strikes_w:
                                ce = f"NSE:{symbol}{code}{strike}CE"
                                pe = f"NSE:{symbol}{code}{strike}PE"
                                contracts_set.add(ce)
                                contracts_set.add(pe)

                # Add all contracts for this symbol
                if contracts_set:
                    FyerSymbolList.extend(sorted(contracts_set))

                # Store per-symbol settings and generated contracts
                symbol_dict["Contracts"] = sorted(contracts_set)
                result_dict[symbol] = symbol_dict
            except Exception as inner_e:
                print(f"Error parsing row {index}: {inner_e}")
            

        # Ensure overall list is unique and stable
        FyerSymbolList = list(dict.fromkeys(FyerSymbolList))

        print("result_dict:", result_dict)
        print("FyerSymbolList:", FyerSymbolList)
        print("-" * 50)
      

    except Exception as e:
        print("Error happened in fetching symbol", str(e))


if __name__ == "__main__":
    # # Initialize settings and credentials
    #   # <-- Add this line
    credentials_dict_fyers = get_api_credentials_Fyers()
    redirect_uri = credentials_dict_fyers.get('redirect_uri')
    client_id = credentials_dict_fyers.get('client_id')
    secret_key = credentials_dict_fyers.get('secret_key')
    grant_type = credentials_dict_fyers.get('grant_type')
    response_type = credentials_dict_fyers.get('response_type')
    state = credentials_dict_fyers.get('state')
    TOTP_KEY = credentials_dict_fyers.get('totpkey')
    FY_ID = credentials_dict_fyers.get('FY_ID')
    PIN = credentials_dict_fyers.get('PIN')
    # Automated login and initialization steps
    automated_login(client_id=client_id, redirect_uri=redirect_uri, secret_key=secret_key, FY_ID=FY_ID,
                                     PIN=PIN, TOTP_KEY=TOTP_KEY)

    get_user_settings()
    # fetch_MarketQuote(xts_marketdata)

    
    # Initialize Market Data API
    fyres_websocket(FyerSymbolList)
    time.sleep(5)

    # ============ Background CSV Writer ============
    from datetime import datetime as _dt
    def ensure_data_dirs():
        base = os.path.join(os.getcwd(), 'database')
        if not os.path.exists(base):
            os.makedirs(base, exist_ok=True)
        today_folder = _dt.now().strftime('%d%b%Y').upper()  # e.g., 08OCT2025
        path = os.path.join(base, today_folder)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return path

    def append_row(csv_path, row_dict):
        # Create file with header if new
        is_new = not os.path.exists(csv_path)
        import csv
        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['symbol','ltp','last_traded_qty','vol_traded_today','timestamp'])
            if is_new:
                writer.writeheader()
            writer.writerow(row_dict)

    def writer_loop():
        from FyresIntegration import shared_data
        while True:
            folder = ensure_data_dirs()
            for symbol in FyerSymbolList:
                data = shared_data.get(symbol)
                if not data:
                    continue
                # file name: contract like NSE:SYMBOL -> strip 'NSE:' for file name
                symbol_name = symbol.replace('NSE:', '')
                fname = symbol_name + '.csv'
                csv_path = os.path.join(folder, fname)
                ts_raw = data.get('timestamp')
                try:
                    # Convert epoch seconds to human readable local time
                    ts_human = _dt.fromtimestamp(int(ts_raw)).strftime('%Y-%m-%d %H:%M:%S') if ts_raw else ''
                except Exception:
                    ts_human = ''
                row = {
                    'symbol': symbol_name,
                    'ltp': data.get('ltp'),
                    'last_traded_qty': data.get('last_traded_qty'),
                    'vol_traded_today': data.get('vol_traded_today'),
                    'timestamp': ts_human
                }
                append_row(csv_path, row)
            time.sleep(1)

    t = _threading.Thread(target=writer_loop, daemon=True)
    t.start()
    

