import pandas as pd
import time
import multiprocessing as mp
import numpy as np
import matplotlib.pyplot as plt

# local imports
from backtester import engine, tester
from backtester import API_Interface as api

training_period = 20  # How far the rolling average takes into calculation
# Number of Standard Deviations from the mean the Bollinger Bands sit
standard_deviations = 3.5
SCALE = 4*24
mv_av_slow_size = 10*SCALE

mv_av_fast_size = 20*SCALE
window = []

def stochastic_oscillator():
    pass


def relative_strength_index():
    pass


def internal_bar_strength():
    pass

# 1 2 3 4  5  6  7  8
# 1 3 6 10 15 21 28 36
def update_slow_average(lookback):
    mv_av_slow = None

    last = len(lookback) - 1
    if last >= mv_av_slow_size:
        sub =  lookback['CUMSUM'][last - mv_av_slow_size ] if last > mv_av_slow_size else 0
        mv_av_slow = (lookback['CUMSUM'][last] - sub)/mv_av_slow_size
        # print(lookback['close'][-mv_av_slow_size:])
        # print(f'{mv_av_slow=}')

    return mv_av_slow

def update_fast_average(lookback):
    mv_av_fast = None
    last = len(lookback) - 1
    if last >= mv_av_fast_size:
        sub =  lookback['CUMSUM'][last - mv_av_fast_size ] if last > mv_av_fast_size else 0
        mv_av_fast = (lookback['CUMSUM'][last] - sub)/mv_av_fast_size

    return mv_av_fast

'''


logic() function:
    Context: Called for every row in the input data.

    Input:  account - the account object
            lookback - the lookback dataframe, containing all data up until this point in time

    Output: none, but the account object will be modified on each call
'''


def logic(account, lookback):  # Logic function to be used for each time interval in backtest
    # how we can create a variable

    

    today = len(lookback)-1
    # will only start returning non (-1, -1) when slow window has caught up
    slow, fast = (update_slow_average(lookback), update_fast_average(lookback))

    if slow is not None:
        account.over = fast > slow

    if today > mv_av_slow_size:
        # print(f'{slow}, {fast}')
        old = account.over
        account.over = fast > slow
        if account.over != old:

            if fast > slow:
                
                for position in account.positions: 
                    account.close_position(position, 1, lookback['close'][today])
                    if(account.buying_power > 0):
                        account.enter_position('long', account.buying_power, lookback['close'][today]) # Enter a long position

            if slow > fast:
                for position in account.positions: 
                    account.close_position(position, 1, lookback['close'][today])
                    if(account.buying_power > 0):
                        account.enter_position('short', account.buying_power, lookback['close'][today]) # Enter a long position

        # try:
        #    account.slow.append(slow)
        # except AttributeError:
        #     account.slow = []

        # try:
        #    account.fast.append(fast)
        # except AttributeError:
        #     account.fast = []

        # if today%25000 == 0:
        #     X = np.linspace(0, 1, num=len(account.close))
        #     plt.plot(X, account.close, 'black')
        #     plt.plot(X, account.slow, 'b')
        #     plt.plot(X, account.fast, 'g')
        #     plt.show()


'''
preprocess_data() function:
    Context: Called once at the beginning of the backtest. TOTALLY OPTIONAL. 
             Each of these can be calculated at each time interval, however this is likely slower.

    Input:  list_of_stocks - a list of stock data csvs to be processed

    Output: list_of_stocks_processed - a list of processed stock data csvs
'''
import time

def preprocess_data(list_of_stocks):
    start = time.time()
    list_of_stocks_processed = []
    for stock in list_of_stocks:
        df = pd.read_csv("data/" + stock + ".csv", parse_dates=[0])
        df['TP'] = (df['close'] + df['low'] + df['high']) / \
            3  # Calculate Typical Price
        # Calculate Standard Deviation
        df['std'] = df['TP'].rolling(training_period).std()
        # Calculate Moving Average of Typical Price
        df['MA-TP'] = df['TP'].rolling(training_period).mean()
        df['BOLU'] = df['MA-TP'] + standard_deviations * \
            df['std']  # Calculate Upper Bollinger Band
        df['BOLD'] = df['MA-TP'] - standard_deviations * \
            df['std']  # Calculate Lower Bollinger Band
        df['CUMSUM'] = df['close'].cumsum()
        df.to_csv("data/" + stock + "_Processed.csv",
                  index=False)  # Save to CSV

        list_of_stocks_processed.append(stock + "_Processed")
    print(f'{(time.time() - start)/len(list_of_stocks)} per stock')
    return list_of_stocks_processed


if __name__ == "__main__":
    # list_of_stocks = ["TSLA_2020-03-01_2022-01-20_1min"]
    # List of stock data csv's to be tested, located in "data/" folder
    list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min",
                      "AAPL_2020-03-24_2022-02-12_15min"]
    list_of_stocks_proccessed = preprocess_data(list_of_stocks)  # Preprocess the data
    # Run backtest on list of stocks using the logic function
    results = tester.test_array(list_of_stocks_proccessed, logic, chart=True)

    print("training period " + str(training_period))
    print("standard deviations " + str(standard_deviations))
    df = pd.DataFrame(list(results), columns=["Buy and Hold", "Strategy", "Longs", "Sells",
                      "Shorts", "Covers", "Stdev_Strategy", "Stdev_Hold", "Stock"])  # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False)  # Save results to csv
