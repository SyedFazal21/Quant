from utils.history_data_service import authenticate, hist_data
from utils.websocket_service import create_websocket_connection
from utils.csv_creator import create_csv
from utils.token_symbol_lookup import get_cached_nifty_future_token

from utils.technical_indicators import (
    add_rsi, add_vwap, add_ema, add_atr, add_volume_spike, add_opening_range,
    get_vix_value, calculate_regime_score
)

smart_api = authenticate()
active_nifty_50_token = get_cached_nifty_future_token()

sws = create_websocket_connection(smart_api.access_token, smart_api.getfeedToken())
candle_data = hist_data(10, "FIVE_MINUTE", active_nifty_50_token, smart_api)

# =============================================================================
#   9:20 AM REGIME FILTER (Decision Engine)
# =============================================================================
vix = get_vix_value(smart_api)
print(f"vix value: {vix}")

# B. For the PRIMARY symbol
primary_df = candle_data
score = calculate_regime_score(primary_df, vix)

print(f"\n===== REGIME FILTER SCORE: {score} =====")
if score >= 2:
    print(">> DEPLOY STRATEGY 1 (ORB - Trend Follower)")
elif score <= -2:
    print(">> DEPLOY STRATEGY 2 (RSI+VWAP Scalper)")
else:
    print(">> SIT OUT TODAY (Mixed signals)")

# Strategy 1 Indicators
add_atr(candle_data, n=14)
add_volume_spike(candle_data)
add_opening_range(candle_data)

# Strategy 2 Indicators
add_rsi(candle_data, n=14)
add_vwap(candle_data)
add_ema(candle_data, period=200)

create_csv(candle_data)

print("Connecting to websocket...")
#sws.connect() # This is a blocking call, it will run continuously
