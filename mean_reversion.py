from numpy import short
import pandas as pd
import time
import multiprocessing as mp

# local imports
from backtester import engine, tester
from backtester import API_Interface as api

# import train_test_split
from sklearn.model_selection import train_test_split

training_period = 20 # How far the rolling average takes into calculation
standard_deviations = 3.5 # Number of Standard Deviations from the mean the Bollinger Bands sit

def enter_long(account, price):
    if account.buying_power >0:
        account.enter_position('long', account.buying_power, price)

def enter_short(account, price):
    if account.buying_power >0:
        account.enter_position('short', account.buying_power, price)

def close_position(account, price):
    for position in account.positions:
        account.close_position(position, 1, price)

def stochastic_oscillator(highs, lows, closes, periods=14):
    high = max(highs[-periods:])
    low = min(lows[-periods:])
    sto = (closes.iloc[-1] - low) / (high - low) * 100
    #print(f"{sto=}")
    return sto

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

def lowest_val(opens, close,low, periods =14):
    # find lowest closing price in lookback
    lowest = min(low[-periods:])
    
    return lowest

def highest_val(opens, close,high ,periods =14):
    # find lowest closing price in lookback
    highest = max(high[-periods:])
    
    return highest
# find ema of price 
def ema(opens, closes, periods=14):
    ema = closes.ewm(span=periods, adjust=False, min_periods=periods).mean()
    return ema

# build function for macd with open, close, high and low price 
def macd(opens, closes,periods=12, short_period=26, long_period=9):
    k = closes.ewm(span=periods, adjust=False, min_periods=periods).mean()
    d = closes.ewm(span=short_period, adjust=False, min_periods=short_period).mean()
    macd = k - d
    signal = macd.ewm(span=long_period, adjust=False, min_periods=long_period).mean()
    macd_h = macd - signal
    # return signal and macd
    return macd_h

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
    if interval_id == 0:
        account.status = "out"
        structure = {"rsi":[], "sto_k":[], "sto_d":[], "lowest":[], "highest":[], "mach_h":[],"ema":[]}
        account.stats = pd.DataFrame(structure)

    account.stats.loc[interval_id] = [None,None,None,None,None,None,None] # add empty row
    buy_price = None
    stoch_trigger = 0
    stop_loss_long = None
    stop_loss_short = None
    sell_price = None
    ema_x = None
    



    if interval_id > training_period:
        #print(f"{interval_id=}")
        rsi = relative_strength_index(lookback['open'], lookback['close'], periods=14)
        sto_k = stochastic_oscillator(lookback['high'], lookback['low'], lookback['close'], periods=14)
        lowest = lowest_val(lookback['open'], lookback['close'], lookback['low'] ,periods=14)
        highest = highest_val(lookback['open'], lookback['close'], lookback['high'], periods=14)
        mach_h = macd(lookback['open'], lookback['close'], periods=12, short_period=26, long_period=9)
        ema_x = ema(lookback['open'], lookback['close'], periods=14)
        account.stats["rsi"][interval_id] = rsi
        account.stats["sto_k"][interval_id] = sto_k
        account.stats['sto_d'] = account.stats.iloc[:,1].rolling(window=3).mean()
        account.stats['lowest'] = lowest
        account.stats['highest'] = highest
        account.stats['mach_h'] = mach_h
        account.stats['ema'] = ema_x
        


        # create trigger if sto_k and sto_d are both below 30 as true
        # while trigger is true if rsi is above 50 enter long
    if interval_id > training_period:
        if account.stats["sto_k"][interval_id] < 20 and account.stats["sto_d"][interval_id] < 20:
            stoch_trigger = 1
        if account.stats["sto_k"][interval_id] > 80 and account.stats["sto_d"][interval_id] > 80:
            stoch_trigger = -1

        if account.stats["rsi"][interval_id] > 50 and account.stats["mach_h"][interval_id] > 0 and lookback['close'][interval_id] < account.stats['ema'][interval_id]:
            if stoch_trigger == 1:
                for position in account.positions: # Close all current positions
                    account.close_position(position, 1, lookback['close'][interval_id])
                if(account.buying_power > 0):
                    account.enter_position('long', account.buying_power, lookback['close'][interval_id])
                    #enter_long(account, lookback['close'][interval_id])
                    buy_price = lookback['close'][interval_id]
                    stoch_trigger = 0
                    stop_loss_long = buy_price-account.stats['lowest'][interval_id]
        if account.stats["rsi"][interval_id] < 50 and account.stats["mach_h"][interval_id] < 0 and lookback['close'][interval_id] < account.stats['ema'][interval_id]:
            if stoch_trigger == -1:
                for position in account.positions: # Close all current positions
                    account.close_position(position, 1, lookback['close'][interval_id])
                if(account.buying_power > 0):
                    account.enter_position('short', account.buying_power, lookback['close'][interval_id])
                #enter_short(account, lookback['close'][interval_id])
                    sell_price = lookback['close'][interval_id]
                    stoch_trigger = 0
                    stop_loss_short = sell_price+account.stats['highest'][interval_id]
    
        
        if buy_price != None and stop_loss_long != None and lookback['close'][interval_id] <= buy_price - stop_loss_long:
            #close_position(account, lookback['close'][interval_id])
            for position in account.positions: # Close all current positions
                account.close_position(position, 1, lookback['close'][interval_id])
            buy_price = None
            stop_loss_long = None
            print ("Loss")
            
        if buy_price != None and stop_loss_long != None and lookback['close'][interval_id] >= buy_price + (stop_loss_long):
            #close_position(account, lookback['close'][interval_id])
            for position in account.positions: # Close all current positions
                account.close_position(position, 1, lookback['close'][interval_id])
            buy_price = None
            stop_loss_long = None
            print ("Profit")
            
        
        if sell_price != None and stop_loss_short != None and lookback['close'][interval_id] <= sell_price - stop_loss_short:
            #close_position(account, lookback['close'][interval_id])
            for position in account.positions: # Close all current positions
                account.close_position(position, 1, lookback['close'][interval_id])
            sell_price = None
            stop_loss_short = None
            print ("Profit")
            
        if sell_price != None and stop_loss_short != None and lookback['close'][interval_id] >= sell_price + (stop_loss_short):
            #close_position(account, lookback['close'][interval_id])
            for position in account.positions: # Close all current positions
                account.close_position(position, 1, lookback['close'][interval_id])
            sell_price = None
            stop_loss_short = None
            print ("Loss")
            
        
                

                
        
       
        
def daily_logic(account, lookback):   
    interval_id = len(lookback) - 1
    today = lookback["date"][interval_id].date()
    is_first_day = False
    if interval_id == 0:
        # first day has no previous day
        # init variables
        is_new_day = True
        is_first_day = True
        account.temp_min = None
        account.temp_max = None
        account.day_num = 0
        structure = {"open":[], "close":[], "start_interval":[], "end_interval":[], "high":[], "low":[], "rsi":[], "sto":[]}
        account.daily_lookback = pd.DataFrame(structure)
        account.daily_lookback["open"][account.day_num] = lookback["open"][interval_id]
        # Day 0 data
        account.daily_lookback.loc[account.day_num] = [ lookback["open"][interval_id], None, interval_id, None, None, None, None, None ]

    elif today != lookback["date"][interval_id-1].date():

        # Fill yesterday data
        account.day_num += 1
        account.daily_lookback["close"][account.day_num-1] = lookback["close"][interval_id-1]
        account.daily_lookback["end_interval"][account.day_num-1] = interval_id-1
        account.daily_lookback["high"][account.day_num-1] = account.temp_max
        account.daily_lookback["low"][account.day_num-1] = account.temp_min
        # Reset counters
        account.temp_max = None
        account.temp_min = None

        # Get and store indicators
        if account.day_num > training_period:
            rsi = relative_strength_index(account.daily_lookback["open"], account.daily_lookback["close"], periods=training_period)
            account.daily_lookback["rsi"][account.day_num-1] = rsi

            sto = stochastic_oscillator(account.daily_lookback["high"], account.daily_lookback["low"], account.daily_lookback["close"])
            account.daily_lookback["sto"][account.day_num-1] = sto
        
        # Init today data
        account.daily_lookback.loc[account.day_num] = [ lookback["open"][interval_id], None, interval_id, None, None, None, None, None ]
        print("day:",account.day_num-1,"interval:", interval_id)
        print(account.daily_lookback.loc[account.day_num-1],"\n")

        # daily decision logic here

    # interval decision logic here

    # For the daily min/max
    if account.temp_max is None or account.temp_min is None:
        account.temp_max = max(lookback["high"][interval_id], lookback["low"][interval_id])
        account.temp_min = min(lookback["high"][interval_id], lookback["low"][interval_id])
    else:
        account.temp_max = max(lookback["high"][interval_id], lookback["low"][interval_id], account.temp_max)
        account.temp_min = min(lookback["high"][interval_id], lookback["low"][interval_id], account.temp_min)

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
        # all headers to lowercase
        df.columns = [x.lower() for x in df.columns]
        df['TP'] = (df['close'] + df['low'] + df['high'])/3 # Calculate Typical Price
        df['std'] = df['TP'].rolling(training_period).std() # Calculate Standard Deviation
        df['MA-TP'] = df['TP'].rolling(training_period).mean() # Calculate Moving Average of Typical Price
        df['BOLU'] = df['MA-TP'] + standard_deviations*df['std'] # Calculate Upper Bollinger Band
        df['BOLD'] = df['MA-TP'] - standard_deviations*df['std'] # Calculate Lower Bollinger Band
        df.to_csv("data/" + stock + "_Processed.csv", index=False) # Save to CSV
        list_of_stocks_processed.append(stock + "_Processed")
    return list_of_stocks_processed

if __name__ == "__main__":
    #list_of_stocks = ["TSLA_2020-03-01_2022-01-20_1min"] 


    #list_of_stocks = ["TSLA_2020-03-09_2022-01-28_15min"] 
    list_of_stocks = ["AAPL_2020-03-24_2022-02-12_15min"] # List of stock data csv's to be tested, located in "data/" folder 
    #list_of_stocks = ["GOOG"]
    list_of_stocks_proccessed = preprocess_data(list_of_stocks) # Preprocess the data
    testing_set = list_of_stocks_proccessed
    
    
        
    results = tester.test_array(testing_set, logic, chart=True) # Run backtest on list of stocks using the logic function

    print("training period " + str(training_period))
    print("standard deviations " + str(standard_deviations))
    df = pd.DataFrame(list(results), columns=["Buy and Hold","Strategy","Longs","Sells","Shorts","Covers","Stdev_Strategy","Stdev_Hold","Stock"]) # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False) # Save results to csv