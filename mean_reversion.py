import pandas as pd
import time
import multiprocessing as mp

# local imports
from backtester import engine, tester
from backtester import API_Interface as api

training_period = 20 # How far the rolling average takes into calculation
standard_deviations = 3.5 # Number of Standard Deviations from the mean the Bollinger Bands sit

def enter_long(account, price, budget=1.0):
    if account.buying_power >0:
        account.enter_position('long', account.buying_power*budget, price)

def enter_short(account, price, budget=1.0):
    if account.buying_power >0:
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

def logic(account, lookback): # Logic function to be used for each time interval in backtest 
    
    interval_id = len(lookback) - 1

    if interval_id == 0:
        account.status = "out"
        account.pt_hits = 0
        account.pt_misses = 0

    if interval_id > training_period:
        #print(f"{interval_id=}")
        rsi = lookback["rsi"][interval_id]
        sto_k = lookback["sto_k"][interval_id]
        sto_d = lookback["sto_d"][interval_id]

        if account.status == "long":

            if lookback["close"][interval_id] < account.stoploss:
                close_position(account, lookback["close"][interval_id])
                account.stoploss = None
                account.profit_target = None
                account.status = "out"
                account.pt_misses += 1
                print(f"\tstoploss triggered at {interval_id=}")
                print(f"{account.pt_hits}/{account.pt_hits+account.pt_misses} targets hit")

            elif lookback["close"][interval_id] > account.profit_target:
                close_position(account, lookback["close"][interval_id])
                account.stoploss = None
                account.profit_target = None
                account.status = "out"
                account.pt_hits += 1
                print(f"\tPROFIT TARGET HIT at {interval_id=}")
                print(f"{account.pt_hits}/{account.pt_hits+account.pt_misses} targets hit")



        if account.status == "out":
            if sto_k < 25 and sto_d < 25 and rsi > 50:
                print(f"sto & rsi suggest long {interval_id=}")
                
                account.status = "wait_macd_buy"
                
                # =====move this to wait_macd_buy if block when macd  arrives=======
                enter_long(account, lookback["close"][interval_id])
                account.status = "long"

                # placeholder stoploss
                account.stoploss = lookback["low"].iloc[-1].min()
                account.profit_target = lookback["close"][interval_id] + (lookback["close"][interval_id]-account.stoploss)*1.5
                print(f"\t{account.stoploss=}\n\t{account.profit_target=}")
                # =================================================================
        
        if account.status == "wait_macd_buy":
            # put check here to see if macd has cross signal line
                # then buy and change status to long
                # set stoploss
                # set profit target
            pass
        


def calc_rsi(data, periods=14):
    deltas = data["close"]-data["open"]

    gains = 0 * deltas
    losses = 0 * deltas

    gains[deltas > 0] = deltas[deltas > 0]
    losses[deltas < 0] = deltas[deltas < 0]

    avg_gains = gains.rolling(periods).mean()
    avg_losses = losses.rolling(periods).mean()
    relative_strength = abs(avg_gains / avg_losses)
    rsi = 100 - ( 100 / (1 + relative_strength ) )
    return rsi

def calc_sto(data, periods=14, k=3, d=3):
    high = data["high"].rolling(periods).max()
    low = data["low"].rolling(periods).min()
    sto = (data["close"]-low)/(high-low) * 100
    sto_k = sto.rolling(k).mean()
    sto_d = sto_k.rolling(d).mean()

    return (sto_k, sto_d)


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
        
        df2 = df.groupby(
            pd.Grouper(key="date", freq="1h")
        ).agg({
            'date':'first',
            'open':'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'last'
        }).dropna()
        df2["rsi"] = calc_rsi(df2, 14)
        (df2["sto_k"], df2["sto_d"]) = calc_sto(df2,14)
        df2.to_csv("data/" + stock + "_Processed.csv", index=False) # Save to CSV
        list_of_stocks_processed.append(stock + "_Processed")
    return list_of_stocks_processed

if __name__ == "__main__":
    #list_of_stocks = ["GOOG_2020-04-20_2020-04-20_1min"] 
    list_of_stocks = ["GOOG_2020-04-30_2022-03-21_1min", "AAPL_2020-03-24_2022-02-12_1min", "TSLA_2020-03-01_2022-01-20_1min"] # List of stock data csv's to be tested, located in "data/" folder 
    list_of_stocks_proccessed = preprocess_data(list_of_stocks) # Preprocess the data
    results = tester.test_array(list_of_stocks_proccessed, logic, chart=True) # Run backtest on list of stocks using the logic function
    #results = tester.test_array(list_of_stocks, logic, chart=True) # Run backtest on list of stocks using the logic function

    print("training period " + str(training_period))
    print("standard deviations " + str(standard_deviations))
    df = pd.DataFrame(list(results), columns=["Buy and Hold","Strategy","Longs","Sells","Shorts","Covers","Stdev_Strategy","Stdev_Hold","Stock"]) # Create dataframe of results
    df.to_csv("results/Test_Results.csv", index=False) # Save results to csv