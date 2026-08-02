import pandas as pd
import datetime as dt

def create_csv(candle_data):
    # Scenario 1: candle_data is a DICTIONARY (multiple symbols like NIFTY, BANKNIFTY)
    if isinstance(candle_data, dict):
        for symbol, df in candle_data.items():
            # Reset the index to turn 'date' from Index into a regular column
            df_to_export = df.reset_index()

            # Optional: Rename the column if it got named 'index' (safety measure)
            if 'index' in df_to_export.columns:
                df_to_export.rename(columns={'index': 'date'}, inplace=True)

            # Save to CSV with the date column intact
            filename = f"{symbol}_indicators_{dt.datetime.now().strftime('%Y-%m-%d_%H:%M')}.csv"
            df_to_export.to_csv(filename, index=False)
            print(f"✅ Exported {symbol} data (with date column) to {filename}")
    # Scenario 2: If candle_data is a single DATAFRAME (fallback)
    elif isinstance(candle_data, pd.DataFrame):
        df_to_export = candle_data.reset_index()
        if 'index' in df_to_export.columns:
            df_to_export.rename(columns={'index': 'date'}, inplace=True)
        df_to_export.to_csv("nifty_indicators.csv", index=False)
        print("✅ Exported single DataFrame (with date column) to nifty_indicators.csv")
    else:
        print("⚠️ Warning: candle_data is neither a dict nor DataFrame. Cannot export.")