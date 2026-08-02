import pandas as pd
import numpy as np
import logging

def calculate_regime_score(primary_df, vix):
    yesterday_close = primary_df.iloc[1]['close'] if len(primary_df) > 1 else primary_df.iloc[0]['close']
    gap_pct = calculate_gap_percent(primary_df, yesterday_close)
    range_pct = get_5min_range_percent(primary_df)
    breakout_score = breakout_test(primary_df)

    score = 0
    if vix is not None and vix > 18:
        score += 1
    elif vix is not None and vix < 15:
        score -= 1

    if gap_pct > 0.006:
        score += 1
    elif gap_pct < 0.002:
        score -= 1

    if range_pct > 0.4:
        score += 1
    elif range_pct < 0.2:
        score -= 1

    return score + breakout_score

# =============================================================================
# 1. CORE WILDER'S SMOOTHING (TradingView's RMA) - DO NOT TOUCH
# =============================================================================
def wilder_smoothing(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's Smoothing (RMA) exactly as used in TradingView for RSI and ATR.
    First value = SMA of first 'period' values.
    Subsequent values = (Previous_RMA * (period - 1) + Current_Value) / period.
    """
    if len(series) < period:
        return pd.Series([np.nan] * len(series), index=series.index)

    rma = np.full(len(series), np.nan, dtype=float)
    rma[period - 1] = series.iloc[:period].mean()

    for i in range(period, len(series)):
        rma[i] = (rma[i - 1] * (period - 1) + series.iloc[i]) / period

    return pd.Series(rma, index=series.index)


# =============================================================================
# 2. SINGLE-DF CALCULATORS (Internal use only - pure math)
# =============================================================================
def _calculate_rsi_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = wilder_smoothing(gain, period)
    avg_loss = wilder_smoothing(loss, period)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100).clip(upper=100)
    return rsi


def _calculate_vwap_series(df: pd.DataFrame) -> pd.Series:
    """
    Calculates cumulative VWAP with DAILY RESET.
    TradingView resets at 9:15 AM each day.
    Typical Price = (High + Low + Close) / 3 (hlc3)

    Handles BOTH:
    1. DatetimeIndex (your style)
    2. 'date' column (my previous style)
    """
    # --- SMART DATE DETECTION ---
    # Check if the index is a DatetimeIndex
    if isinstance(df.index, pd.DatetimeIndex):
        date_key = df.index.date  # Extracts YYYY-MM-DD for grouping
    # Fallback: check if a 'date' column exists
    elif 'date' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        date_key = df['date'].dt.date
    else:
        raise ValueError("DataFrame must have a DatetimeIndex or a 'date' column.")

    # --- VWAP MATH (hlc3) ---
    typical_price = (df['high'] + df['low'] + df['close']) / 3

    # Group by the date key (resets at midnight, effectively at 9:15 AM)
    cum_vol = df.groupby(date_key)['volume'].cumsum()
    cum_tp_vol = (typical_price * df['volume']).groupby(date_key).cumsum()

    vwap = cum_tp_vol / cum_vol
    return vwap


def _calculate_atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return wilder_smoothing(true_range, period)


# =============================================================================
# 3. STRATEGY 2 INDICATORS (RSI, VWAP, 200-EMA) - DICT WRAPPERS
# =============================================================================
def add_rsi(df_dict: dict, n: int = 14):
    """Adds 'rsi' column to every DataFrame in the dictionary."""
    for key, df in df_dict.items():
        df['rsi'] = _calculate_rsi_series(df, n)


def add_vwap(df_dict: dict):
    """Adds 'vwap' column to every DataFrame with daily reset (matches TradingView)."""
    for key, df in df_dict.items():
        df['vwap'] = _calculate_vwap_series(df)


def add_ema(df_dict: dict, period: int = 200, source: str = 'close'):
    """Adds 'ema_200' (or custom period) column. Uses TradingView's EMA (adjust=False)."""
    for key, df in df_dict.items():
        df[f'ema_{period}'] = df[source].ewm(span=period, adjust=False, min_periods=1).mean()


# =============================================================================
# 4. STRATEGY 1 INDICATORS (ATR, Volume Spike, Opening Range) - DICT WRAPPERS
# =============================================================================
def add_atr(df_dict: dict, n: int = 14):
    """Adds 'atr_14' column to every DataFrame in the dictionary."""
    for key, df in df_dict.items():
        df['atr'] = _calculate_atr_series(df, n)


def add_volume_spike(df_dict: dict, lookback: int = 10, multiplier: float = 1.5):
    """
    Adds 'volume_spike' (bool) column. True if current volume > multiplier * avg of previous 'lookback' candles.
    """
    for key, df in df_dict.items():
        spike = [False] * len(df)
        if len(df) > lookback:
            for i in range(lookback, len(df)):
                avg_prev = df['volume'].iloc[i - lookback:i].mean()
                if not pd.isna(avg_prev) and avg_prev > 0:
                    spike[i] = df['volume'].iloc[i] > (multiplier * avg_prev)
        df['volume_spike'] = spike


def add_opening_range(df_dict: dict, start_time: str = "09:15", end_time: str = "09:45"):
    """
    Adds 'orb_high' and 'orb_low' columns (forward-filled across the entire day).
    Automatically converts string dates to datetime if necessary.
    """
    for key, df in df_dict.items():
        # --- FIX: Ensure the 'date' column is proper datetime dtype ---
        if 'date' in df.columns:
            # If it's not datetime yet, convert it in-place
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'])

            # Now .dt accessor will work perfectly
            time_str = df['date'].dt.strftime('%H:%M')
        else:
            # Fallback: try using index
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                # If index is also string, convert it
                df.index = pd.to_datetime(df.index)
            time_str = pd.Series(df.index).dt.strftime('%H:%M')
            time_str.index = df.index

        # Filter for the opening range period
        mask = (time_str >= start_time) & (time_str <= end_time)
        range_df = df[mask]

        if not range_df.empty:
            orb_high_val = range_df['high'].max()
            orb_low_val = range_df['low'].min()
        else:
            orb_high_val = np.nan
            orb_low_val = np.nan

        # Forward-fill these values to every row
        df['orb_high'] = orb_high_val
        df['orb_low'] = orb_low_val


# =============================================================================
# 5. REGIME FILTER HELPERS (Run at 9:20 AM)
#    These return SCALAR values (single numbers) for decision making.
# =============================================================================
def get_vix_value(smartApi):
    """
    Fetches the live India VIX value. Returns float, or 15.0 as fallback.
    """
    try:
        vix_request = {
            "exchange": "NSE",
            "tradingsymbol": "INDIA VIX",
            "symboltoken": "99926017"
        }

        # CORRECT METHOD: Use ltpData instead of getLtpData
        vix_response = smartApi.ltpData(
            vix_request['exchange'],
            vix_request['tradingsymbol'],
            vix_request['symboltoken']
        )

        # Verification to ensure the response data field is populated properly
        if vix_response and vix_response.get('status') and 'data' in vix_response:
            return float(vix_response['data']['ltp'])
        else:
            logging.error(f"API returned failure status: {vix_response.get('message')}")
            return 15.0

    except KeyError as e:
        logging.error(f"VIX response structure unexpected: {e}")
        return 15.0  # Fallback to standard baseline on schema changes
    except Exception as e:
        logging.error(f"VIX fetch failed: {e}. Using fallback 15.0")
        return 15.0


def calculate_gap_percent(df: pd.DataFrame, yesterday_close: float) -> float:
    """Returns gap % = (Today's Open / Yesterday's Close) - 1."""
    if df.empty or yesterday_close == 0:
        return 0.0
    today_open = df.iloc[0]['open']
    return (today_open / yesterday_close) - 1


def get_5min_range_percent(df: pd.DataFrame) -> float:
    """Returns percentage range of the first 5 minutes (9:15 to 9:20)."""
    # Convert 'date' column to datetime if it exists and is string
    if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])
        time_str = df['date'].dt.strftime('%H:%M')
    elif 'date' in df.columns:
        time_str = df['date'].dt.strftime('%H:%M')
    else:
        return 0.0

    mask = (time_str >= "09:15") & (time_str <= "09:20")
    range_df = df[mask]

    if range_df.empty or len(df) < 2:
        return 0.0

    high = range_df['high'].max()
    low = range_df['low'].min()
    prev_close = df.iloc[1]['close'] if len(df) > 1 else df.iloc[0]['close']

    if prev_close == 0:
        return 0.0
    return ((high - low) / prev_close) * 100


def breakout_test(df: pd.DataFrame) -> int:
    """
    Returns +1 if 9:23 AM price > 9:15 High OR < 9:15 Low (Trending).
    Returns -1 if 9:23 price is INSIDE the 9:15 range (Sideways).
    """
    # Convert 'date' column to datetime if it exists and is string
    if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])
        time_str = df['date'].dt.strftime('%H:%M')
    elif 'date' in df.columns:
        time_str = df['date'].dt.strftime('%H:%M')
    else:
        return 0

    row_915 = df[time_str == "09:15"]
    row_923 = df[time_str == "09:23"]

    if row_915.empty or row_923.empty:
        return 0

    h_915 = row_915.iloc[0]['high']
    l_915 = row_915.iloc[0]['low']
    price_923 = row_923.iloc[0]['close']

    if price_923 > h_915 or price_923 < l_915:
        return 1
    else:
        return -1