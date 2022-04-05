import pandas as pd
import time
import multiprocessing as mp

# local imports
from backtester import engine, tester
from backtester import API_Interface as api

training_period = 20 # How far the rolling average takes into calculation
standard_deviations = 3.5 # Number of Standard Deviations from the mean the Bollinger Bands sit

def stochastic_oscillator():
    pass

def relative_strength_index(opens, closes, periods=14):
    
    deltas = pd.Series(closes[-periods:]) - pd.Series(opens[-periods:])

    gain_sum = 0
    loss_sum = 0
    for delta in deltas:
        if delta > 0:
            gain_sum += delta
        if delta < 0:
            loss_sum -= delta
    
    #print(deltas)
    # No losses is always 100 RSI, also avoids zerodivide exception
    if loss_sum == 0:
        return 100

    avg_gain = gain_sum/periods
    avg_loss = loss_sum/periods
    
    relative_strength = avg_gain / avg_loss
    rsi = 100 - ( 100 / (1 + relative_strength ) )
    #print(f"{rsi=}")
    return rsi

def internal_bar_strength():
    pass

'''
logic() function:
    Context: Called for every row in the input data.

    Input:  account - the account object
            lookback - the lookback dataframe, containing all data up until this point in time

    Output: none, but the account object will be modified on each call
'''

def logic(account, lookback): # Logic function to be used for each time interval in backtest 
    
    interval_id = len(lookback) - 1
    today = lookback["date"][interval_id].date()

    is_first_day = False
    if interval_id == 0:
        # first day has no previous day
        is_new_day = True
        is_first_day = True
    else:
        # if previous interval is previous day, it is a new day
        is_new_day = today != lookback["date"][interval_id-1].date()

    # Store the opening and closing prices of every day
    if is_first_day:
        account.day_num = 0
        structure = {"open":[], "close":[], "rsi":[]}
        account.daily_lookback = pd.DataFrame(structure)
        account.daily_lookback["open"][account.day_num] = lookback["open"][interval_id]
        # Day 0 data
        account.daily_lookback.loc[account.day_num] = [ lookback["open"][interval_id], None, None ]

    elif is_new_day:
        # Fill yesterday data
        account.day_num += 1
        account.daily_lookback["close"][account.day_num-1] = lookback["close"][interval_id-1]
        if account.day_num > training_period:
            rsi = relative_strength_index(account.daily_lookback["open"], account.daily_lookback["close"], periods=training_period)
            account.daily_lookback["rsi"][account.day_num-1] = rsi
        
        # Init today data
        account.daily_lookback.loc[account.day_num] = [ lookback["open"][interval_id], None, None ]
        print("day:",account.day_num-1,"interval:", interval_id)
        print(account.daily_lookback.loc[account.day_num-1],"\n")

        # daily decision logic here

    # interval decision logic here

        
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
        df = pd.read_csv("data/" + stock + ".csv", parse_dates=[0])
        df['TP'] = (df['close'] + df['low'] + df['high'])/3 # Calculate Typical Price
        df['std'] = df['TP'].rolling(training_period).std() # Calculate Standard Deviation
        df['MA-TP'] = df['TP'].rolling(training_period).mean() # Calculate Moving Average of Typical Price
        df['BOLU'] = df['MA-TP'] + standard_deviations*df['std'] # Calculate Upper Bollinger Band
        df['BOLD'] = df['MA-TP'] - standard_deviations*df['std'] # Calculate Lower Bollinger Band
        df.to_csv("data/" + stock + "_Processed.csv", index=False) # Save to CSV
        list_of_stocks_processed.append(stock + "_Processed")
    return list_of_stocks_processed

if __name__ == "__main__":
    # list_of_stocks = ["TSLA_2020-03-01_2022-01-20_1min"] 
    list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min", "AAPL_2020-03-24_2022-02-12_15min"] # List of stock data csv's to be tested, located in "data/" folder 
    list_of_stocks_proccessed = preprocess_data(list_of_stocks) # Preprocess the data
    results = tester.test_array(list_of_stocks_proccessed, logic, chart=True) # Run backtest on list of stocks using the logic function

    print("training period " + str(training_period))
    print("standard deviations " + str(standard_deviations))
    df = pd.DataFrame(list(results), columns=["Buy and Hold","Strategy","Longs","Sells","Shorts","Covers","Stdev_Strategy","Stdev_Hold","Stock"]) # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False) # Save results to csv