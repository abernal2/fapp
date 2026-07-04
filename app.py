import streamlit as st
from PIL import Image
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date
from collections import defaultdict

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


image_path = os.path.join(path, 'files/graph.png')
image = Image.open(image_path)


st.markdown('# Trading App')
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
    "CRM", "ARM", "TLRY", "WEN", "HOOD", "SMMT"
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

tickers = st.multiselect(
    label="Choose stock tickers:",
    options=st.session_state.master_tickers,
    default=st.session_state.master_tickers
)

if st.button('Run'):
    ### iterating over the years
    output = {}
    ledger = {}
    for i in range(1):
        end_date = datetime.now() - timedelta(days=365*i) - timedelta(minutes=15)
        start_date = end_date - timedelta(days=365)
        ledger[start_date.date()] = {}

        ########## GET DATA ##########
        # Initialize the official Alpaca Data Client
        data_client = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_API_SECRET)
        st.write(f"Fetching historical daily bars from Alpaca from {start_date.date()} and {end_date.date()}...")
        request_params = StockBarsRequest(
            symbol_or_symbols=tickers,
            timeframe=TimeFrame.Day,
            start=start_date,
            end=end_date
        )

        # Fetch data and convert to multi-index Pandas DataFrame (symbol, timestamp)
        dfs = data_client.get_stock_bars(request_params).df
        dfs = dfs.reset_index()
        # 2. Convert UTC timestamps to New York local time
        dfs['timestamp'] = dfs['timestamp'].dt.tz_convert('America/New_York')

        st.write("Data download complete.")

        # Concatenate dfs
        # dfs = pd.concat([dfs, crypto_df], ignore_index=True)

        dfs['timestamp'] = pd.to_datetime(dfs['timestamp']).dt.date
        # ts = datetime.now().date() - timedelta(days=1)
        # dfs = dfs.loc[lambda f: f['timestamp'] <= ts]

        # algo begins
        st.write("Running Algorithm: ")
        output_returns = {}
        for stock, df in dfs.groupby('symbol'):
            df.loc[:,'change'] = (df.close.shift(-1).fillna(0.0) / df.close) * 100. - 100.
            df['change'] = df['change'].shift(1)
            df.loc[:,'change'] = df['change'].fillna(0.0)

            # create true returns of different windows
            df['tmp'] = (df['change']/100.)+1
            for rw in rolling_window_returns:
                df[rw] = df['tmp'].rolling(window=int(rw)).apply(
                            lambda window: np.prod(window)-1
                        )
                df[rw] = df[rw].shift(-(int(rw)-1))
                df[rw] = df[rw] * 100.
            df = df.fillna(0.0)
            df = df.drop(columns='tmp')


            data_dic = df.set_index('timestamp').to_dict()

            # If theres a 10-day signal = the first row is good and 80% column is bad
            # if last 2 have been bad
            data_df = df[['timestamp']+cols].set_index('timestamp')

            # algo begins
            buy_ledger = {}
            sell_ledger = {}
            consecutive_days_hold = 0
            rr = 0
            position = None

            for idx, ts in zip(range(len(data_df)-9), data_df.index):
                if idx <= 30:
                    continue
                todays_date = dateto_10(ts, df)
                
                date_30_days_ago = dateto_30(todays_date, df)
                is_pos30 = data_dic['30'][date_30_days_ago] >= 0
                return_window = data_df.iloc[idx:idx+10] * mask_10day
                col_neg_returns = (return_window['change'] < 0).sum()
                row_sum_returns = return_window.iloc[0].sum()

                # determining 30 day signal
                date_before_30_days = prev_trading_day(date_30_days_ago, df)
                return_30d_day_before_neg = data_dic['30'][date_before_30_days] < 0
                just_turned_green_30days = is_pos30 and return_30d_day_before_neg
                if just_turned_green_30days and position is None:
                    date__days_ago = dateto_30(todays_date, df)
                    tmp_dates = [date_Ndays_ago(todays_date, df, 4-i) for i in range(4)]
                    tmp = np.array([data_dic['close'][d] for d in tmp_dates])
                    # slope, _ = np.polyfit(range(len(tmp)), tmp, 1)

                    # if red wait long enough
                    if (len(tmp[tmp < 0]) >= 3) or (tmp[-1] > 0):
                        prev_date = prev_trading_day(todays_date, df)
                        if data_dic['close'][prev_date] >= data_dic['close'][todays_date]:
                            buy_ledger[todays_date] = data_dic['close'][todays_date]
                            position = 1
                            consecutive_days_hold += 1
                            continue
                
                # if signal good and 10day
                if (col_neg_returns >= 6) and (row_sum_returns > -3):
                    if is_pos30:
                        if position is None:
                            # buy and hold until you drop
                            prev_date = prev_trading_day(todays_date, df)
                            if data_dic['close'][prev_date] >= data_dic['close'][todays_date]:
                                buy_ledger[todays_date] = data_dic['close'][todays_date]
                                position = 1
                                consecutive_days_hold += 1
                        else:
                            # you are long
                            prev_date = prev_trading_day(todays_date, df)
                            sorted_data = dict(sorted(buy_ledger.items(), key=lambda item: item[0], reverse=True))
                            price_bought = next(iter(sorted_data.items()))[1]       
                            rr = (data_dic['close'][todays_date]/price_bought - 1.) * 100. 
                            todays_change = (data_dic['open'][todays_date]/data_dic['close'][prev_date] - 1.) * 100. 
                            consecutive_days_hold += 1
                            if todays_change <= -4.0 or rr <= -5.0:
                                sell_ledger[todays_date] = data_dic['open'][todays_date]
                                position = None
                                consecutive_days_hold = 0

                    else:
                        # keep for at most 2 days or return drops below 5%
                        if position is None:
                            # buy and hold until you drop
                            prev_date = prev_trading_day(todays_date, df)
                            if data_dic['close'][prev_date] >= data_dic['close'][todays_date]:
                                buy_ledger[todays_date] = data_dic['close'][todays_date]
                                position = 1
                                consecutive_days_hold += 1
                        else:
                            prev_date = prev_trading_day(todays_date, df)
                            sorted_data = dict(sorted(buy_ledger.items(), key=lambda item: item[0], reverse=True))
                            price_bought = next(iter(sorted_data.items()))[1]       
                            rr = (data_dic['close'][todays_date]/price_bought - 1.) * 100. 
                            todays_change = (data_dic['open'][todays_date]/data_dic['close'][prev_date] - 1.) * 100. 
                    
                            if (consecutive_days_hold == 2) or (todays_change <= -4.0) or (rr <= -5.0):
                                sell_ledger[todays_date] = data_dic['open'][todays_date]
                                position = None
                                consecutive_days_hold = 0
                            consecutive_days_hold += 1
                            # if todays_change <= -4.0 or rr <= -5.0:
                            #     sell_ledger[todays_date] = data_dic['close'][todays_date]
                            #     position = None
                            #     consecutive_days_hold = 0
        
                elif (is_pos30) and (not just_turned_green_30days) and (position is None):
                    buy_ledger[todays_date] = data_dic['close'][todays_date]
                    position = 1
                    consecutive_days_hold += 1
                else:
                    # no signal
                    if position is not None:
                        prev_date = prev_trading_day(todays_date, df)
                        sorted_data = dict(sorted(buy_ledger.items(), key=lambda item: item[0], reverse=True))
                        price_bought = next(iter(sorted_data.items()))[1]       
                        rr = (data_dic['close'][todays_date]/price_bought - 1.) * 100. 
                        todays_change = (data_dic['open'][todays_date]/data_dic['close'][prev_date] - 1.) * 100. 
                        consecutive_days_hold += 1
                        if todays_change <= -4.0 or rr <= -5.0:
                            sell_ledger[todays_date] = data_dic['open'][todays_date]
                            position = None
                            consecutive_days_hold = 0


            ret = []
            for i, j in zip(buy_ledger.items(), sell_ledger.items()):
                bought = i[1]
                buy_ts = i[0]
                sell = j[1]
                sell_ts = j[0]
                ror = (sell/bought - 1.0) * 100.
                ret.append(ror)

            output_returns[stock] = [sum(ret), ret]
            ledger[start_date.date()][stock] = {'B': buy_ledger, 'S': sell_ledger}
        
        output[start_date.date()] = output_returns

    dt_cols = list(output.keys())
    ddict_output = {k: defaultdict(lambda: [0.0], v) for k,v in output.items()}
    return_data = [
        [tik] + [ddict_output[dt][tik][0] for dt in dt_cols]
        for tik in tickers
    ]
    # dt_cols = [d.date() for d in ddict_output.keys()]
    output_df = pd.DataFrame(return_data, columns=['symbol']+dt_cols)


    s = []
    pdfs = []
    dtts = list(output_df.columns)[1]
    for stk in tickers:
        if stk in ledger[dtts]:
            df1 = pd.DataFrame.from_dict(ledger[dtts][stk]['B'], orient='index').reset_index().rename(columns={'index': 'buy_date', 0: 'buy_price'})
            df2 = pd.DataFrame.from_dict(ledger[dtts][stk]['S'], orient='index').reset_index().rename(columns={'index': 'sell_date', 0: 'sell_price'})
            result = pd.concat([df1, df2], axis=1).fillna(0.)
            # result['next_earnings'] = next_earnings
            result['ticker'] = stk
            result['current_price'] = dfs.loc[lambda f: (f.symbol==stk)&(f['timestamp']==datetime.now().date()-timedelta(days=2)), 'close'].values[0]
            result['days_held'] = result.apply(lambda f: (f['sell_date'] - f['buy_date']).days if isinstance(f['sell_date'], date) else 0.0, axis=1)
            result['buy_day'] = result.apply(lambda f: f['buy_date'].strftime('%A') if isinstance(f['buy_date'], date) else 0.0, axis=1)
            result['sell_day'] = result.apply(lambda f: f['sell_date'].strftime('%A') if isinstance(f['sell_date'], date) else 0.0, axis=1)
            result['return'] = (result['sell_price']/result['buy_price'] - 1.0) * 100.
            if not result.loc[lambda f: f.days_held==0, 'days_held'].empty:
                # result.loc[lambda f: f.days_held==0, 'return'] = (dfs.loc[lambda f: (f.symbol==stk)&(f['timestamp']==datetime.now().date()), 'close'].values[0]/result.loc[lambda f: f.days_held==0, 'buy_price'] - 1.0) * 100.
                result.loc[lambda f: f.days_held==0, 'days_held'] = (datetime.now().date() - result.loc[lambda f: f.days_held==0, 'buy_date'].values[0]).days
            # print(stk)
            s.append(result.iloc[-1])
            pdfs.append(result)
            # if result.iloc[-1]['return'] != -100.:
            #     s.append(result.iloc[-1]['return'])
            # print('-'*16)
    df_series = pd.DataFrame(s)
    st.session_state.results = pd.concat(pdfs)
    d = datetime.now().date() - timedelta(days=2)

    st.write("Buy: ")
    st.dataframe(df_series.loc[lambda f: (f.buy_date==d), c].reset_index(drop=True))
    
    st.write("Sell: ")
    st.dataframe(df_series.loc[lambda f: (f.sell_date==d), c].reset_index(drop=True))

if st.session_state.results is not None:
    selected_ticker = st.selectbox(
        label="Choose a stock ticker to view historical trades:",
        options=st.session_state.master_tickers,
        index=0  # Pre-selects the first item ("AAPL"). Change to None for no default selection.
    )
    st.dataframe(st.session_state.results.loc[lambda f: f.ticker==selected_ticker, c].reset_index(drop=True))
else:
    st.info("Click the 'Run' button above to generate the results dataframe.")

