import streamlit as st
from PIL import Image
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots
# import plotly.express as px
from datetime import datetime, timedelta, date
from collections import defaultdict
import yfinance as yf

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from utils.helpers import *

st.set_page_config(
    page_icon="📉",
)

path = os.path.dirname(os.path.realpath(__file__))


image_path = os.path.join(path, '../files/graph.png')
image = Image.open(image_path)


st.markdown('# Return and Stock Price Plot')
st.image(image, width=300)

st.markdown(
    """
    App will provide what trades to make the day you run the algorithm.
"""
)

ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
ALPACA_API_SECRET = st.secrets["ALPACA_API_SECRET"]
cols = ['change','2','3','4','5','6','7','10']
mask_10day = np.array([
    [1.0]*8,
    [1.0]*7 + [0.]*1,
    [1.0]*7 + [0.]*1,
    [1.0]*7 + [0.]*1,
    [1.0]*6 + [0.]*2,
    [1.0]*5 + [0.]*3,
    [1.0]*4 + [0.]*4,
    [1.0]*3 + [0.]*5,
    [1.0]*2 + [0.]*6,
    [1.0]*1 + [0.]*7,
])
c = ['ticker','buy_date','buy_price','sell_date','sell_price', 'return']

# List of requested tickers
ticker_list = [
    "IONQ", "INTC", "QUBT", "RGTI", "QBTS", "ALMS", "ALAB", "MU", "SATL", 
    "WOLF", "WULF", "CRCL", "CRWV", "RKLB", "MRVL", "ORCL", "PLTR", "PL", 
    "JOBY", "ACHR", "AVGO", "SNDK", "FIG", "SOUN", "RDDT", "OPEN", "GOOG",
    "QS", "FLY", "INFQ", "SMCI", "BLDR", "FIX", "NVDA", "META", "LLY", "TSLA", 
    "CRM", "ARM", "TLRY", "WEN", "HOOD", "SMMT", "BTC/USD", "ETH/USD"
]
# 1. Initialize the master ticker list in Session State if it doesn't exist yet
if "master_tickers" not in st.session_state:
    st.session_state.master_tickers = ticker_list
if "results" not in st.session_state:
    st.session_state.results = None

# 2. Section to add a new ticker
st.subheader("Add a Custom Ticker")

# Using a form prevents the app from rerunning until the user clicks submit
with st.form("add_ticker_form", clear_on_submit=True):
    new_ticker = st.text_input("Enter new stock ticker (e.g., AMD, META):").upper().strip()
    submitted = st.form_submit_button("Add to List")
    
    if submitted:
        if not new_ticker:
            st.error("Please enter a valid ticker name.")
        elif new_ticker in st.session_state.master_tickers:
            st.warning(f"'{new_ticker}' is already in your list!")
        else:
            # Append the new ticker to session state
            st.session_state.master_tickers.append(new_ticker.upper())
            st.success(f"Added '{new_ticker}' successfully!")
            # Force an immediate rerun to refresh the multiselect dropdown below
            # st.rerun()

st.divider()

st.subheader("Select Tickers to Analyze")

# tickers = st.multiselect(
#     label="Choose stock tickers:",
#     options=st.session_state.master_tickers,
#     default=st.session_state.master_tickers
# )
tickers = st.selectbox(
        label="Choose a stock ticker to view historical trades:",
        options=st.session_state.master_tickers,
        index=0  # Pre-selects the first item ("AAPL"). Change to None for no default selection.
    )
crypto = ["BTC/USD", "ETH/USD"]

if st.button('Run'):
    ### iterating over the years
    output = {}
    ledger = {}
    end_date = datetime.now() - timedelta(minutes=15)
    start_date = end_date - timedelta(days=1095)

    ########## GET DATA ##########
    if tickers not in crypto:
        # Initialize the official Alpaca Data Client
        data_client = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET)
        st.write(f"{tickers}: Fetching historical daily bars from Alpaca from {start_date.date()} and {end_date.date()}...")
        request_params = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=start_date,
            end=end_date
        )

        # Fetch data and convert to multi-index Pandas DataFrame (symbol, timestamp)
        df = data_client.get_stock_bars(request_params).df
    else:
        client = CryptoHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET)
        st.write(f"{tickers}: Fetching historical daily bars from Alpaca from {start_date.date()} and {end_date.date()}...")
        bars_request = CryptoBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,          # Options: TimeFrame.Minute, TimeFrame.Hour, etc.
            start=start_date,       # Start date
            end=end_date          # End date
        )

        # Fetch historical data
        historical_bars = client.get_crypto_bars(bars_request)

        # Convert the resulting data directly into a clean Pandas DataFrame
        # Fetch data and convert to multi-index Pandas DataFrame (symbol, timestamp)
        df = historical_bars.df
    df = df.reset_index()
    # 2. Convert UTC timestamps to New York local time
    df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')

    st.write("Data download complete.")

    # Concatenate dfs
    # dfs = pd.concat([dfs, crypto_df], ignore_index=True)

    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.date

    tmp_dfs = []
    for indx, df_indx in df.groupby('symbol'):
        df_indx.loc[:,'change'] = (df_indx.close.shift(-1).fillna(0.0) / df_indx.close) * 100. - 100.
        df_indx['change'] = df_indx['change'].shift(1)
        df_indx.loc[:,'change'] = df_indx['change'].fillna(0.0)

        # create true returns of different windows
        df_indx['tmp'] = (df_indx['change']/100.)+1
        for rw in rolling_window_returns:#+['40','50','60','70','80','90']:
            df_indx[rw] = df_indx['tmp'].rolling(window=int(rw)).apply(
                        lambda window: np.prod(window)-1
                    )
            df_indx[rw] = df_indx[rw].shift(-(int(rw)-1))
            df_indx[rw] = df_indx[rw] * 100.
        df_indx = df_indx.fillna(0.0)
        df_indx = df_indx.drop(columns='tmp')
        tmp_dfs.append(df_indx)

    st.session_state.results = pd.concat(tmp_dfs)

# if st.session_state.results is not None:
    # selected_ticker = st.selectbox(
    #     label="Choose a stock ticker to view historical trades:",
    #     options=st.session_state.master_tickers,
    #     index=0  # Pre-selects the first item ("AAPL"). Change to None for no default selection.
    # )
    df_indx = st.session_state.results.loc[lambda f: f.symbol==tickers]
    # st.dataframe(df_indx)

    # 1. Prepare your data data
    df_indx["close_shifted"] = df_indx["close"].shift(-30)

    tkr = yf.Ticker(tickers)
    calendar_data = tkr.calendar
    try:
        next_earnings = calendar_data["Earnings Date"][0]
    except:
        next_earnings = 'No Date'

    mn = df_indx['30'].values.min()
    mx = df_indx['30'].values.max()
    mx = mx if mx <= 400. else 400.

    # 2. Create figure with secondary y-axis
    # fig = go.Figure() 
    # # fig = make_subplots(specs=[[{"secondary_y": True}]])

    # # 3. Add the first curve (Returns) on the primary Y-axis
    # fig.add_trace(
    #     go.Scatter(
    #         x=df_indx["timestamp"],
    #         y=df_indx["30"],
    #         name="30-day Return",
    #         mode="lines",
    #         line=dict(width=2),
    #     ),
    #     # secondary_y=False,
    # )

    # 4. Add the second curve (Shifted Close) on the secondary Y-axis
    # fig.add_trace(
    #     go.Scatter(
    #         x=df_indx["timestamp"],
    #         y=df_indx["close_shifted"],
    #         name="Close Shifted",
    #         mode="lines",
    #         line=dict(color="red", width=2),
    #     ),
    #     secondary_y=True,
    # )

    # 5. Configure layout options (Labels, Limits, and Size)
    # fig.update_layout(
    #     title_text="Stock 30-day Returns vs Shifted Close Price",
    #     xaxis_title="Timestamp",
    #     width=1100,  # Adjust to fit your Streamlit layout width
    #     height=600,
    #     # hovermode="x unified",  # Shows both values on a single hover tooltip
    # )

    # Set the y-axis limits for the primary axis (corresponds to your mn, mx)
    # fig.update_yaxes(title_text="30-day Return", range=[mn, mx])#, secondary_y=False)
    # fig.update_yaxes(title_text="Close Shifted (Red)", secondary_y=True)

    # fig = px.line(
    #     df_indx,
    #     x="timestamp",
    #     y=["30"],  # Pass both metrics as a list
    #     title="Stock 30-day Returns vs Shifted Close Price",
    #     color_discrete_map={"30": "blue", "close_shifted": "red"},
    # )

    # # 3. Apply your limits and styling
    # fig.update_layout(hovermode="x unified", height=600)
    # fig.update_yaxes(range=[mn, mx], title_text="Value")

    # 2. Explicitly create the figure and axis objects
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # 3. Plot the first curve (Returns) on the primary axis
    df_indx.plot(
        x="timestamp",
        y="30",
        ax=ax1,
        linewidth=2,
        color="blue",
        label="30-day Return",
    )
    ax1.set_ylim(mn, mx)
    ax1.set_ylabel("Return", color="blue")

    # 4. Create the secondary y-axis using twinx()
    ax2 = ax1.twinx()

    # 5. Plot the second curve (Shifted Close) on the secondary axis
    df_indx.plot(
        x="timestamp",
        y="close_shifted",
        ax=ax2,
        linewidth=2,
        color="red",
        label="Close Shifted",
    )
    ax2.set_ylabel("Close Shifted", color="red")
    fig.autofmt_xdate(rotation=45) 
    plt.title(f"{tickers}: Next Earning {next_earnings}")
    # 6. Render the interactive chart in Streamlit
    st.pyplot(fig, use_container_width=True)

else:
    st.info("Click the 'Run' button above to generate the results dataframe.")
