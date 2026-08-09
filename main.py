import time

from utils.history_data_service import authenticate, hist_data
from utils.websocket_service import create_websocket_connection
from utils.csv_creator import create_csv
from utils.token_symbol_lookup import get_cached_nifty_future_token

from utils.technical_indicators import (
    add_rsi, add_vwap, add_ema, add_atr, add_adx, add_volume_spike, add_opening_range,
    get_vix_value, calculate_regime_score
)

smart_api = authenticate()
active_nifty_50_token = get_cached_nifty_future_token()

sws = create_websocket_connection(smart_api.access_token, smart_api.getfeedToken())

# =============================================================================
#   Fetch candle data for 3 timeframes
# =============================================================================
# 1-Minute  -> VWAP, Volume Spike (scalping / intraday)
# 5-Minute  -> RSI, ATR, ORB (momentum / volatility / opening range)
# 15-Minute -> 200-EMA, ADX (trend / trend strength)
candle_1min = hist_data(3, "ONE_MINUTE", active_nifty_50_token, smart_api)
time.sleep(2)
candle_5min = hist_data(10, "FIVE_MINUTE", active_nifty_50_token, smart_api)
time.sleep(2)
candle_15min = hist_data(20, "FIFTEEN_MINUTE", active_nifty_50_token, smart_api)

# =============================================================================
#   9:20 AM REGIME FILTER (Decision Engine)
# =============================================================================
vix = get_vix_value(smart_api)
print(f"vix value: {vix}")

# B. For the PRIMARY symbol (5-Minute is the primary frame for regime decisions)
primary_df = candle_5min
score = calculate_regime_score(primary_df, vix)

print(f"\n===== REGIME FILTER SCORE: {score} =====")
if score >= 2:
    print(">> DEPLOY STRATEGY 1 (ORB - Trend Follower)")
elif score <= -2:
    print(">> DEPLOY STRATEGY 2 (RSI+VWAP Scalper)")
else:
    print(">> SIT OUT TODAY (Mixed signals)")

# =============================================================================
#   Strategy 1 Indicators — 5-Minute timeframe
# =============================================================================
# ATR (Volatility)
add_atr(candle_5min, n=14)
# ORB High/Low
add_opening_range(candle_5min)

# =============================================================================
#   Strategy 2 Indicators — Multi-timeframe
# =============================================================================
# VWAP (1-Minute)
add_vwap(candle_1min)
# Volume Spike (1-Minute)
add_volume_spike(candle_1min)
# RSI (Momentum) (5-Minute)
add_rsi(candle_5min, n=14)
# 200-EMA (Trend) (15-Minute)
add_ema(candle_15min, period=200)
# ADX (Trend Strength) (15-Minute)
add_adx(candle_15min, n=14)

# =============================================================================
#   Export CSVs for each timeframe
# =============================================================================
create_csv(candle_1min, "NIFTY_1MIN")
create_csv(candle_5min, "NIFTY_5MIN")
create_csv(candle_15min, "NIFTY_15MIN")

print("Connecting to websocket...")
#sws.connect() # This is a blocking call, it will run continuously
