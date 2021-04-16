import websocket
import json
import pprint
import talib
import numpy
import datetime
import config
import os
from binance.client import Client
from binance.enums import *
from twilio.rest import Client as twilio

# SET UP
client = Client(config.API_KEY, config.API_SECRET)
account_sid = config.account_sid
auth_token = config.auth_token
client_twilio = twilio(account_sid, auth_token)
text_list = config.text_list

# PROGRAM SETTINGS
profit_mult = 1.012
loss_mult = 0.99
rsi_overbought = 75
rsi_oversold = 22
rsi_period = 14
rsi_weight = 0.15
portfolio_b = 0.5
reset = True
tickers = ["DOGEUSDT"]

#STREAM SET UP
tickers_list = []
open_positions = {}
for tick in tickers:
    tickers_list.append(tick.lower())

SOCKET = "wss://stream.binance.com:9443/stream?streams={}@kline_1m/{}@kline_1m/{}@kline_1m/{}@kline_1m/{}@kline_1m".format(
    tickers_list[0],tickers_list[1], tickers_list[2], tickers_list[3], tickers_list[4]
    )

#RESET 
if reset:
    closes = {}
    closes_5m = {}
    open_trades = {}
    for tick in tickers:
        closes[tick] = []
        open_trades[tick] = []
        closes_5m[tick] = []
else:
    with open('closes.json', 'r') as f:
        closes = json.load(f)
    with open('open_trades.json', 'r') as f:
        open_trades = json.load(f)
    with open('closes_5m.json', 'r') as f:
        closes_5m = json.load(f)

def on_open(ws):
    global open_positions, ROI
    print('opened connection')

    with open('ROI.json', 'r') as f:
        ROI = json.load(f)
        ROI = float(ROI)

    bnbBalance = getBalance("BNB")
    bnbPrice = getPrice("BNBUSDT")
    if bnbBalance * bnbPrice < 10:
        try:
            order(side=SIDE_BUY, quantity=(float(round((20/bnbPrice),3))),symbol="BNBUSDT")
        except Exception as e:
            print(e)
            pass

    for tick in tickers:
        price = getPrice(tick)
        balance = getBalance(tick[:-4])

        if price*balance > 10:
            open_positions[tick] = True
        else:
            open_positions[tick] = False

def on_close(ws):
    print('closed connection')

    # SAVES FILES
    with open('closes.json', 'w+') as f:
        json.dump(closes, f)

    with open('open_trades.json', 'w+') as f:
        json.dump(open_trades, f)      
    
    with open('closes_5m.json', 'w+') as f:
        json.dump(closes_5m, f)


def order(side, quantity, symbol,order_type=ORDER_TYPE_MARKET):
    global orderData, open_trades
    try:
        print("sending order")
        orderData = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        open_trades[trade_symbol].append(orderData)
        print(orderData)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return True

def getBalance(COIN_TICKER):
    coin_balance_dic = client.get_asset_balance(asset=COIN_TICKER)
    coin_balance = (float(coin_balance_dic['free']))

    return coin_balance


def getPrice(trade_symbol):
    trades = client.get_recent_trades(symbol=trade_symbol)
    price_current = float(trades[-1]['price'])
    
    return price_current

def buy(trade_quantity, ticker, last_rsi, tether_balance, portfolio_pct):
    global open_trades, open_positions

    print("Buy! {}".format(trade_symbol[:-4]))
    try:
        order_succeeded = order(side=SIDE_BUY, quantity=trade_quantity, symbol=ticker)
        order_succeeded = True
    except Exception as e:
        print("an exception occured - {}".format(e))
        order_succeeded = False

    if order_succeeded:
        open_positions[trade_symbol] = True
        totalBalance = tether_balance
        trade_total = float(open_trades[ticker][-1]['cummulativeQuoteQty'])
        avg_cost = trade_total / float(open_trades[trade_symbol][-1]['executedQty'])
        for tick in tickers:
            if open_positions[tick] == True:
                COST = float(open_trades[tick][-1]['cummulativeQuoteQty'])
                totalBalance = totalBalance + COST
        portfolio_pct = round((trade_total / totalBalance),4)
        with open('open_trades.json', 'w+') as f:
            json.dump(open_trades, f)                        
        for number in text_list:
            bought_message = client_twilio.messages.create(
                body="A position has been bought in {} at a total price of ${}. Amount:{} {} @ ${}.".format(
                    ticker[:-4],round(trade_total,2),trade_quantity,ticker[:-4],round(avg_cost,5)),
                from_="+16672443559",
                to=number)
        open_trades[trade_symbol][-1]['last_rsi'] = last_rsi
        open_trades[trade_symbol][-1]['portfolio_pct'] = portfolio_pct
        print("Exit code: InPosition = {}".format(open_positions[trade_symbol]))
    else:
        pass


def sell(coin_balance, ticker, tradeFormat):
    global open_trades, coinBalance, open_positions, trade_quantity, ROI

    print("Sell! {}".format(trade_symbol[:-4]))
    TRADE_QUANTITY = round((float(coin_balance)*0.9999),tradeFormat)
    try:
        order_succeeded = order(side=SIDE_SELL, quantity=trade_quantity, symbol=ticker)
        order_succeeded = True
    except Exception as e:
        print("an exception occured - {}".format(e))
        order_succeeded = False

    if order_succeeded:
        open_positions[trade_symbol] = False
        COST = round(float(open_trades[trade_symbol][-2]['cummulativeQuoteQty']),2)
        REVENUE = round(float(open_trades[trade_symbol][-1]['cummulativeQuoteQty']),2)
        portfolio_pct = round(float(open_trades[trade_symbol][-2]['portfolio_pct']),3)
        with open('ROI.json', 'r') as f:
            ROI = json.load(f)
        PROFIT = REVENUE - COST - ((REVENUE+COST)*0.00075)
        PROFIT_PCT = round((PROFIT / COST),4)
        ROI = round((((PROFIT_PCT*portfolio_pct)+1)*ROI),5)
        with open('ROI.json', 'w+') as f:
            json.dump(ROI, f)
        with open('open_trades.json', 'w+') as f:
            json.dump(open_trades, f)
        if PROFIT > 0:
            body="We sold our position in {} at a total price of ${} for a profit of around ${} or {}%. Total ROI: {}%".format(trade_symbol[:-4],round(REVENUE,2),abs(round(PROFIT,2)),(PROFIT_PCT*100), round((ROI*100-100),2))
        else:
            body="We sold our position in {} at a total price of ${} for a loss of around ${} or {}%. Total ROI: {}%".format(trade_symbol[:-4],round(REVENUE,2),abs(round(PROFIT,2)),(PROFIT_PCT*100), round((ROI*100-100),2))
        for number in text_list:
            sold_message = client_twilio.messages.create(
                body=body,
                from_="+16672443559",
                to=number)
        print("Exit code: InPosition = {}".format(open_positions[trade_symbol]))
    else:
        pass

def on_message(ws, message):
    global closes, open_trades, trade_symbol, closes_5m, trade_quantity
    
    # GETS JSON MESSAGE AND SETS VARIABLES
    json_message = json.loads(message)
    json_message = json_message['data']
    trade_symbol = json_message['s']
    candle = json_message['k']
    is_candle_closed = candle['x']
    close = candle['c']
    COIN_TICKER = trade_symbol[:-4]

    # GETS CURRENT PRICE AND COIN BALANCE
    inPosition = open_positions[trade_symbol]
    if inPosition:
        price_current = getPrice(trade_symbol)
        AVG_COST = round((float(open_trades[trade_symbol][-1]['cummulativeQuoteQty']) / float(open_trades[trade_symbol][-1]['executedQty'])),5)

        # INSTANT SELL IF PRICE GOES UP OR BELOW PRESET %
        if ((AVG_COST * profit_mult) < price_current) or ((price_current / AVG_COST) < loss_mult):
            # FORMATS TRADE QUANTITY
            tradeFormat = len(str(int(price_current)))
            
            if tradeFormat == 0:
                tradeFormat = 0
            else:
                tradeFormat = tradeFormat - 1
            
            coin_balance = getBalance(COIN_TICKER)
            ticker = trade_symbol

            sell(coin_balance, ticker, tradeFormat)

    # RSI AND CLOSED CANDLE BRANCH
    if is_candle_closed == True:
        price_current = getPrice(trade_symbol)
        closes[trade_symbol].append(float(close))
        now = datetime.datetime.now()

        is_5m_closed = False
        if (str(now.minute)[-1]) == '0':
            is_5m_closed = True
        elif ((str(now.minute))[-1]) == '5':
            is_5m_closed = True


        if is_5m_closed: 
            closes_5m[trade_symbol].append(float(close))     

        tradeFormat = len(str(int(price_current)))
        if tradeFormat == 0:
            tradeFormat = 0
        else:
            tradeFormat = tradeFormat - 1

        if len(closes[trade_symbol]) > rsi_period:
            np_closes = numpy.array(closes[trade_symbol])
            rsi = talib.RSI(np_closes, rsi_period)
            last_rsi = rsi[-1]

            if len(closes_5m[trade_symbol]) > rsi_period:
                np_closes5 = numpy.array(closes_5m[trade_symbol])
                rsi5 = talib.RSI(np_closes5, rsi_period)
                last_rsi5 = rsi5[-1]
                RSIchanger = float((last_rsi5 - 50)*0.2)
                RSI_SELL = rsi_overbought + (RSIchanger*0.3)
                RSI_BUY = rsi_oversold + RSIchanger
            else:
                RSI_SELL = rsi_overbought
                RSI_BUY = rsi_oversold
                last_rsi5 = 0
            
            if inPosition:
                print("{}:{} --  Coin: {},   RSI: {},   RSI 5m: {},  RSI Buy: {}   Price: ${}/USDT, Our average cost is {}".format(
                    now.hour, now.minute, COIN_TICKER, round(last_rsi,2), round(last_rsi5,3), round(RSI_BUY,3), price_current, AVG_COST)
                )
            else:
                print("{}:{} --  Coin: {},   RSI: {},   RSI 5m: {},  RSI Buy: {}   Price: ${}/USDT".format(
                    now.hour, now.minute, COIN_TICKER, round(last_rsi,2), round(last_rsi5,3), round(RSI_BUY,3), price_current)
                )

            # SELL LOGIC   
            if (last_rsi > RSI_SELL):
                
                if inPosition:
                    coin_balance = getBalance(COIN_TICKER)
                    ticker = trade_symbol
                    sell(coin_balance, ticker, tradeFormat)

            # BUY LOGIC
            if (last_rsi < RSI_BUY):
                
                if inPosition:
                    pass
                else:
                    # trade_quantity LOGIC
                    tether_balance_dic = client.get_asset_balance(asset='USDT')
                    tether_balance = round((float(tether_balance_dic['free'])),2)
                    RSI_Multiplier = float(RSI_BUY - last_rsi)
                    portfolio_pct = portfolio_b + (rsi_weight*RSI_Multiplier)
                    if portfolio_pct > 0.99:
                        portfolio_pct = 0.995
                    trade_balance = round(((tether_balance/price_current)*portfolio_pct),tradeFormat)                
                    trade_quantity = float(abs(trade_balance))

                    if tether_balance > 15:
                        ticker = trade_symbol
                        buy(trade_quantity, ticker, last_rsi, tether_balance, portfolio_pct)

        if len(closes[trade_symbol]) > 100:
            closes[trade_symbol].pop(0)

        if len(closes_5m[trade_symbol]) > 100:
            closes_5m[trade_symbol].pop(0)            

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
