from re import L
from numpy import average
import pandas as pd
import time
import multiprocessing as mp

# local imports
from backtester import engine, tester
from backtester import API_Interface as api
from backtester.help_funcs import period

training_period = 500 # How far the rolling average takes into calculation
standard_deviations = 1 # Number of Standard Deviations from the mean the Bollinger Bands sit


'''
logic() function:
    Context: Called for every row in the input data.

    Input:  account - the account object
            lookback - the lookback dataframe, containing all data up until this point in time

    Output: none, but the account object will be modified on each call
'''
def set_allocation(account, leverage, close):
    if leverage == 0:
        for position in account.positions: # Close all current positions
                account.close_position(position, 1, close)
    else:
        #current_position = account
        pass

def logic(account, lookback): # Logic function to be used for each time interval in backtest 
    
    current_period = len(lookback)-1
   

    one_day = (14) # periods 64*15
    global buy_per

    if(current_period > training_period):

        start_period = current_period

        while lookback['date'][start_period].day == lookback['date'][current_period].day:
            start_period -= 1
       
        
        sum = 0
        count = 0
        for day in range(25):
            High = 0
            Low = 9999999
            for hour in range(one_day):
                High = max(High,lookback['high'][start_period - hour - day*one_day])
                Low = min(Low,lookback['low'][start_period - hour - day*one_day])

            Close = lookback['close'][start_period]

            sum += (Close - Low)/(High-Low)
            
            count += 1

        ratio = sum/count

        close = lookback['close'][current_period]
        current_ratio = (close - lookback['low'][current_period])/(lookback['high'][current_period] - lookback['low'][current_period])


        if current_ratio <= 0.21*ratio and account.buying_power >0 and current_ratio >= 0.1*ratio and account.buying_power >0:
            account.enter_position('long', account.buying_power, close) # Enter a long position
            
        if lookback['close'][current_period] >= 1.035*lookback['close'][start_period] or lookback['close'][current_period] <= 0.95*lookback['close'][start_period]:
            for position in account.positions: # Close all current positions
                account.close_position(position, 1, close)
            print(account.total_value(close))



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
    list_of_stocks = ["IBM_2020-04-07_2022-02-26_60min"]
    #list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min", "AAPL_2020-03-24_2022-02-12_15min"] # List of stock data csv's to be tested, located in "data/" folder 
    #list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min", "AAPL_2020-03-24_2022-02-12_15min"] # List of stock data csv's to be tested, located in "data/" folder 
    #list_of_stocks = ["AAPL_2020-04-08_2022-02-27_60min"]
    #list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min"]

    list_of_stocks_proccessed = preprocess_data(list_of_stocks) # Preprocess the data
    results = tester.test_array(list_of_stocks_proccessed, logic, chart=True) # Run backtest on list of stocks using the logic function

    print("training period " + str(training_period))
    print("standard deviations " + str(standard_deviations))
    df = pd.DataFrame(list(results), columns=["Buy and Hold","Strategy","Longs","Sells","Shorts","Covers","Stdev_Strategy","Stdev_Hold","Stock"]) # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False) # Save results to csv