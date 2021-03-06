import math
from pickle import STOP
import pandas as pd
import time
import multiprocessing as mp
import matplotlib.pyplot as plt
from enum import Enum, auto

from numpy import diff

# local imports
from backtester import engine, tester
from backtester import API_Interface as api


WARMUP_PERIOD = 20
STOPLOSS = 0.0025

# generate enums for states of the algorithm
class State(Enum):
    OUT = auto()
    LONG = auto()
    SHORT = auto()
    WAIT_MACD_LONG = auto()
    WAIT_MACD_SHORT = auto()
    BAH = auto()


def enter_long(account, price, budget=1.0):
    if account.buying_power > 0:
        account.enter_position('long', account.buying_power*budget, price)


def enter_short(account, price, budget=1.0):
    if account.buying_power > 0:
        account.enter_position('short', account.buying_power*budget, price)


def close_position(account, price):
    for position in account.positions:
        account.close_position(position, 1, price)


'''
logic() function:
    Context: Called for every row in the input data.

    Input:  account - the account object
            lookback - the lookback dataframe, containing all data up until this point in time

    Output: none, but the account object will be modified on each call
'''


def logic(account, lookback):  # Logic function to be used for each time interval in backtest

    interval_id = len(lookback) - 1

    if interval_id == 0:
        account.status = State.OUT
        # Used for debugging
        account.pt_hits = 0
        account.pt_misses = 0

    if interval_id > WARMUP_PERIOD:
        rsi = lookback["rsi"][interval_id]
        sto_k = lookback["sto_k"][interval_id]
        sto_d = lookback["sto_d"][interval_id]
        ema_val = lookback["ema"][interval_id]

        price = lookback["close"][interval_id]

        # look to exit while longing
        if account.status == State.LONG:

            if price < account.stoploss:
                close_position(account, price)
                account.stoploss = None
                account.profit_target = None
                account.status = State.OUT
                account.pt_misses += 1

            elif rsi < 40 or not macd_over_signal(lookback, interval_id) :
                close_position(account, price)
                account.stoploss = None
                account.profit_target = None
                account.status = State.OUT
                account.pt_hits += 1

        # look to exit while shorting
        if account.status == State.SHORT:

            # update stoploss
            if lookback["close"][interval_id-1] > price:
                account.stoploss = price*(1+STOPLOSS*2)

            if price > account.stoploss:
                close_position(account, price)
                account.stoploss = None
                account.profit_target = None
                account.status = State.OUT
                account.pt_misses += 1

            elif rsi > 60 or macd_over_signal(lookback, interval_id):
                close_position(account, price)
                account.stoploss = None
                account.profit_target = None
                account.status = State.OUT
                account.pt_hits += 1

        # Default action is to long
        if account.status == State.OUT:
            enter_long(account, lookback["close"][interval_id])
            account.status = State.BAH

        # While in default state
        if account.status == State.BAH:
            ''' Commented out since buy and hold makes this redundant
            if sto_k < 20 and sto_d < 20 and rsi > 50:
                print(f"STO & RSI suggest LONG at {interval_id=}")
                #close_position(account, lookback["close"][interval_id])

                account.status = State.WAIT_MACD_LONG'''

            # Indication that stock is overbought
            if sto_k > 80 and sto_d > 80 and rsi < 50 and lookback["close"][interval_id] < ema_val:
                account.status = State.WAIT_MACD_SHORT

        # wait for macd confirmation for long
        if account.status == State.WAIT_MACD_LONG:

            # if sto condition or rsi condition are untrue then set to out
            if sto_k > 80 or sto_d > 80:
                print('STO > 80 - Finished waiting for MACD\n')
                account.status = State.OUT

            # if macd has crossed signal line
            elif macd_over_signal(lookback, interval_id):
                # then buy and change status to long

                print(f"\tMACD long confirmed buy at {interval_id=}, {price=}")
                enter_long(account, price)
                account.status = State.LONG

                account.stoploss = price*(1-STOPLOSS)
                account.profit_target = price*(1 + STOPLOSS*1.5)

        # wait for macd confirmation for short
        elif account.status == State.WAIT_MACD_SHORT:

            # if sto condition or rsi condition are untrue then set to out
            if sto_k < 20 or sto_d < 20:
                account.status = State.OUT

            # if macd has crossed signal line
            elif not macd_over_signal(lookback, interval_id):
                # then buy and change status to long
                price = lookback["close"][interval_id]
                # Exit long
                close_position(account, lookback["close"][interval_id])
                enter_short(account, price)
                account.status = State.SHORT

                account.stoploss = price*(1+STOPLOSS)
                account.profit_target = price*(1 - STOPLOSS*2)


def calc_rsi(data, periods=14):
    close_delta = data['close'].diff()

    # Make two series: one for lower closes and one for higher closes
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)

    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True,
                       min_periods=periods).mean()

    rsi = ma_up / ma_down
    rsi = 100 - (100/(1 + rsi))
    return rsi


def calc_sto(data, periods=14, k=3, d=3):
    high = data["high"].rolling(periods).max()
    low = data["low"].rolling(periods).min()
    sto = ((data["close"]-low)/(high-low)) * 100
    sto_k = sto.rolling(k).mean()
    sto_d = sto_k.rolling(d).mean()

    return (sto_k, sto_d)


def calc_macd(data, slow=26, fast=12, macd=9):
    exp1 = data['close'].ewm(span=slow, adjust=False).mean()
    exp2 = data['close'].ewm(span=fast, adjust=False).mean()
    macd_ewp = exp1 - exp2
    macd_signal = macd_ewp.ewm(span=macd, adjust=False).mean()

    return (macd_ewp, macd_signal)


def macd_over_signal(data, interval_id):
    return data['MACD'][interval_id] > data['MACD SIGNAL'][interval_id]

def ema(data, periods=50):
    return data["close"].ewm(span=periods, adjust=False).mean()


'''
preprocess_data() function:
    Context: Called once at the beginning of the backtest. TOTALLY OPTIONAL. 
             Each of these can be calculated at each time interval, however this is likely slower.

    Input:  list_of_stocks - a list of stock data csvs to be processed

    Output: list_of_stocks_processed - a list of processed stock data csvs
'''


def preprocess_data(list_of_stocks):
    list_of_stocks_processed = []
    for stock in list_of_stocks:
        df = pd.read_csv(f'data/{stock}.csv', parse_dates=[0])

        df2 = df.groupby(
            pd.Grouper(key="date", freq="30T")
        ).agg({
            'date': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'last'
        }).dropna()
        df2["rsi"] = calc_rsi(df2, 14)
        df2["ema"] = ema(df2, 100)
        (df2['MACD'], df2['MACD SIGNAL']) = calc_macd(df2)
        (df2["sto_k"], df2["sto_d"]) = calc_sto(df2, 14)
        df2.to_csv("data/" + stock + "_Processed.csv",
                   index=False)  # Save to CSV
        list_of_stocks_processed.append(stock + "_Processed")
    return list_of_stocks_processed

if __name__ == "__main__":

    # List of stock data csv's to be tested, located in "data/" folder
    list_of_stocks = [ "GOOG_2020-04-30_2022-03-21_1min", 
                        "AAPL_2020-03-24_2022-02-12_1min",
                       "TSLA_2020-03-01_2022-01-20_1min"]  
    print("Datasets being tested:\n\t", "\n\t".join(list_of_stocks))
    print("Preprocessing datasets...")
    list_of_stocks_proccessed = preprocess_data(list_of_stocks)  # Preprocess the data
    print("Preprocessing complete!")

    # Run backtest on list of stocks using the logic function
    print("Backtesting algorithm...")
    results = tester.test_array(list_of_stocks_proccessed, logic, chart=True)

    print("training period " + str(WARMUP_PERIOD))
    df = pd.DataFrame(list(results), columns=["Buy and Hold", "Strategy", "Longs", "Sells",
                      "Shorts", "Covers", "Stdev_Strategy", "Stdev_Hold", "Stock"])  # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False)  # Save results to csv
