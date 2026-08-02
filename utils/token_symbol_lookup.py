import os
import json
import pandas as pd
import requests
from datetime import datetime

RESOURCES_DIR = "resources"
CACHE_FILE = os.path.join(RESOURCES_DIR, "active_nifty_future.json")
ANGEL_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"


def ensure_resources_dir():
    """Creates the resources folder if it doesn't exist."""
    if not os.path.exists(RESOURCES_DIR):
        os.makedirs(RESOURCES_DIR)
        print(f"[INFO] Created directory: {RESOURCES_DIR}")


def get_cached_nifty_future_token():
    """
    Returns the near-month NIFTY future token.
    Uses a local JSON cache to avoid downloading the 20MB scrip master every time.
    Automatically deletes the cache and fetches a fresh one if the contract has expired.
    """
    ensure_resources_dir()
    today_date = datetime.now().date()

    # ---- 1. CHECK CACHE ----
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)

            cache_expiry = datetime.fromisoformat(cache_data['expiry_dt']).date()

            if cache_expiry > today_date:
                print(f"[CACHE HIT] Using cached token for {cache_data['symbol']} (Expires: {cache_data['expiry']})")
                return cache_data['token']
            else:
                print(f"[CACHE EXPIRED] Contract expired on {cache_data['expiry']}. Fetching new scrip master...")
                os.remove(CACHE_FILE)  # Delete stale cache
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"[WARNING] Cache file corrupted ({e}). Re-fetching...")
            os.remove(CACHE_FILE)  # Delete corrupted cache

    # ---- 2. FETCH FRESH FROM ANGEL (CACHE MISS OR EXPIRED) ----
    print("[INFO] Downloading fresh scrip master from Angel One (approx 20MB)...")
    try:
        response = requests.get(ANGEL_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to download scrip master: {e}")
        return None
    except json.JSONDecodeError:
        print("[ERROR] Failed to parse JSON response. The API might be down or returning a different format.")
        return None

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        df = pd.DataFrame(data)
    else:
        print("[ERROR] Unexpected JSON format from Angel API.")
        return None

    # ---- 3. FILTER FOR NEAR-MONTH NIFTY FUTURE ----
    # Lowercase/uppercase handling just in case
    df.columns = [col.lower() for col in df.columns]

    nifty_fut = df[
        (df['exch_seg'] == 'NFO') &
        (df['name'] == 'NIFTY') &
        (df['instrumenttype'] == 'FUTIDX')
        ].copy()

    if nifty_fut.empty:
        print("[ERROR] No NIFTY Futures found in the scrip master.")
        return None

    nifty_fut['expiry_dt'] = pd.to_datetime(nifty_fut['expiry'], format='mixed')
    nifty_fut = nifty_fut.sort_values(by='expiry_dt')

    near_month = nifty_fut.iloc[0]
    contract_expiry = near_month['expiry_dt'].date()

    if contract_expiry <= today_date:
        if contract_expiry < today_date:
            if len(nifty_fut) > 1:
                near_month = nifty_fut.iloc[1]
                print(f"[WARNING] Today is past the primary expiry. Using NEXT contract: {near_month['symbol']}")
            else:
                print("[ERROR] No future contracts available.")
                return None

    # ---- 4. SAVE TO CACHE ----
    cache_payload = {
        "token": str(near_month['token']),
        "symbol": near_month['symbol'],
        "expiry": near_month['expiry'],
        "expiry_dt": near_month['expiry_dt'].isoformat(),
        "lotsize": int(near_month['lotsize']),
        "fetched_at": datetime.now().isoformat()
    }

    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_payload, f, indent=4)

    print(f"[INFO] Cached new contract: {near_month['symbol']} (Expires: {near_month['expiry']})")
    return str(near_month['token'])
