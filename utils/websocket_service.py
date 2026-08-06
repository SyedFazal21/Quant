import os

from dotenv import load_dotenv
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

load_dotenv()

API_KEY = os.getenv('API_KEY')
CLIENT_CODE = os.getenv('PASS_CODE')

correlation_id = "nifty_stream_1"
mode = 2  # 1 = LTP (Last Traded Price), 2 = Quote, 3 = Snap Quote

# exchangeType 2 is for NSE_FO (Futures and Options)
token_list = [
    {
        "exchangeType": 2,
        "tokens": ["58072"]  # Token for NIFTY25AUG26FUT
    }
]

# 4. Define Event Callbacks
def on_data(wsapp, message):
    """Triggered when live data is received."""
    print("Received Tick:", message)


def on_open(wsapp, sws):
    """Triggered when the connection opens successfully."""
    print("WebSocket connection opened.")

    # Send the subscription request
    return sws.subscribe(correlation_id, mode, token_list)


def on_error(wsapp, error):
    """Triggered if there is a connection error."""
    print("Error occurred:", error)


def on_close(wsapp):
    """Triggered when the connection is closed."""
    print("WebSocket connection closed.")


def create_websocket_connection(auth_token, feed_token):
    sws = SmartWebSocketV2(auth_token, API_KEY, CLIENT_CODE, feed_token)

    sws.on_open = lambda wsapp: on_open(wsapp, sws)
    print(f"Subscribed to NSE_FO token: 58072")

    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = on_close

    return sws

