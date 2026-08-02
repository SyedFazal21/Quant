from utils.smart_api_helper import authenticate, hist_data
from utils.csv_creator import create_csv
from utils.token_symbol_lookup import get_cached_nifty_future_token

from utils.technical_indicators import (
    add_rsi, add_vwap, add_ema, add_atr, add_volume_spike, add_opening_range,
    get_vix_value, calculate_regime_score
)

smart_api = authenticate()
active_nifty_50_token = get_cached_nifty_future_token()
candle_data = hist_data(["NIFTY_FUT"], 10, "FIVE_MINUTE", active_nifty_50_token, smart_api)

# =============================================================================
#   9:20 AM REGIME FILTER (Decision Engine)
# =============================================================================
vix = get_vix_value(smart_api)
print(f"vix value: {vix}")

# B. For the PRIMARY symbol
primary_df = candle_data["NIFTY_FUT"]
score = calculate_regime_score(primary_df, vix)

print(f"\n===== REGIME FILTER SCORE: {score} =====")
if score >= 2:
    print(">> DEPLOY STRATEGY 1 (ORB - Trend Follower)")
    # Strategy 1 Indicators
    add_atr(candle_data, n=14)  # Adds 'atr' column
    add_volume_spike(candle_data)  # Adds 'volume_spike' (bool) column
    add_opening_range(candle_data)  # Adds 'orb_high' and 'orb_low' columns
elif score <= -2:
    print(">> DEPLOY STRATEGY 2 (RSI+VWAP Scalper)")
    # Strategy 2 Indicators
    add_rsi(candle_data, n=14)  # Adds 'rsi' column
    add_vwap(candle_data)  # Adds 'vwap' column
    add_ema(candle_data, period=200)  # Adds 'ema_200' column
else:
    print(">> SIT OUT TODAY (Mixed signals)")

create_csv(candle_data["NIFTY_FUT"])
