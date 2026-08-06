import pandas as pd

def create_csv(df: pd.DataFrame, symbol: str = "NIFTY_FUT"):
    df_to_export = df.reset_index()

    if 'index' in df_to_export.columns:
        df_to_export.rename(columns={'index': 'date'}, inplace=True)

    filename = f"{symbol}_indicators.csv"
    df_to_export.to_csv(filename, index=False)
    print(f"✅ Exported {symbol} data (with date column) to {filename}")
