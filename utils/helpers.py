def dateto_30(dt, df):
    tmp = df['timestamp'].loc[lambda f: f <= dt].iloc[-30:].values
    return tmp[0]

def date30_2now(dt, df):
    tmp = df['timestamp'].loc[lambda f: f >= dt].iloc[:30].values
    return tmp[-1]

def dateto_10(dt, df):
    tmp = df['timestamp'].loc[lambda f: f >= dt].iloc[:10].values
    return tmp[-1]

def prev_trading_day(dt, df):
    tmp = df['timestamp'].loc[lambda f: f <= dt].values
    return tmp[-2]

def next_trading_day(dt, df):
    tmp = df['timestamp'].loc[lambda f: f >= dt].values
    return tmp[1]
    
def date_Ndays_ago(dt, df, num):
    tmp = df['timestamp'].loc[lambda f: f <= dt].iloc[-(num+1):].values
    return tmp[0]

rolling_window_returns = [
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '10',
    '20',
    '27',
    '30'
]