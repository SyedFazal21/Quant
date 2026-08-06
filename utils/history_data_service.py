import os
import datetime as dt
import pandas as pd
import pyotp

from logzero import logger
from dotenv import load_dotenv
from SmartApi import SmartConnect

def authenticate():
    load_dotenv()

    api_key = os.getenv('API_KEY')
    username = os.getenv('USER_NAME')
    pwd = os.getenv('PASS_CODE')
    smart_api = SmartConnect(api_key)

    try:
        token = os.getenv('TOKEN')
        totp = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e

    smart_api.generateSession(username, pwd, totp)

    return smart_api

def hist_data(duration, interval, token, smart_api, exchange="NFO"):
    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": interval,
        # Fixed subtraction syntax by converting today() to a datetime object
        "fromdate": (dt.datetime.combine(dt.date.today(), dt.time.min) - dt.timedelta(duration)).strftime('%Y-%m-%d %H:%M'),
        "todate": dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    candle_data = smart_api.getCandleData(params)
    df_data = pd.DataFrame(candle_data["data"],
                           columns=["date", "open", "high", "low", "close", "volume"])
    df_data.set_index("date", inplace=True)
    df_data.index = pd.to_datetime(df_data.index)
    df_data.index = df_data.index.tz_localize(None)
    return df_data


