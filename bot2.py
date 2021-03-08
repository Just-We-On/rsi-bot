import websocket, json, pprint, talib, numpy, datetime
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
TICKERS = ["DOGEUSDT", "XRPUSDT", "ADAUSDT", "DOTUSDT", "RVNUSDT"]

# PROGRAM SETTINGS
PROFIT_MULT = 1.012
LOSS_MULT = 0.99
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 22
RSI_PERIOD = 14
RSI_WEIGHT = 0.15
PORTFOLIO_B = 0.5
RESET = True

#STREAM SET UP
tickers_list = []
inPositionD = {}
for tick in TICKERS:
    tickers_list.append(tick.lower())

SOCKET = "wss://stream.binance.com:9443/stream?streams={}@kline_1m/{}@kline_1m/{}@kline_1m/{}@kline_1m/{}@kline_1m".format(tickers_list[0],tickers_list[1], tickers_list[2], tickers_list[3], tickers_list[4])

#RESET 
if RESET:
    closes = {}
    closes_5m = {}
    openTrades = {}
    for tick in TICKERS:
        closes[tick] = []
        openTrades[tick] = []
        closes_5m[tick] = []
else:
    with open('closes.json', 'r') as f:
        closes = json.load(f)
    with open('openTrades.json', 'r') as f:
        openTrades = json.load(f)
    with open('closes_5m.json', 'r') as f:
        closes_5m = json.load(f)

def on_open(ws):
    global inPositionD, ROI
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

    for tick in TICKERS:
        price = getPrice(tick)
        balance = getBalance(tick[:-4])

        if price*balance > 10:
            inPositionD[tick] = True
        else:
            inPositionD[tick] = False

def on_close(ws):
    print('closed connection')

    # SAVES FILES
    with open('closes.json', 'w+') as f:
        json.dump(closes, f)

    with open('openTrades.json', 'w+') as f:
        json.dump(openTrades, f)      
    
    with open('closes_5m.json', 'w+') as f:
        json.dump(closes_5m, f)


def order(side, quantity, symbol,order_type=ORDER_TYPE_MARKET):
    global orderData, openTrades
    try:
        print("sending order")
        orderData = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        openTrades[TRADE_SYMBOL].append(orderData)
        print(orderData)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return True

def getBalance(COIN_TICKER):
    coin_balance_dic = client.get_asset_balance(asset=COIN_TICKER)
    coin_balance = (float(coin_balance_dic['free']))

    return coin_balance


def getPrice(TRADE_SYMBOL):
    trades = client.get_recent_trades(symbol=TRADE_SYMBOL)
    price_current = float(trades[-1]['price'])
    
    return price_current

def buy(TRADE_QUANTITY, ticker, last_rsi, tether_balance, Portfolio_pct):
    global openTrades, inPositionD

    print("Buy! {}".format(TRADE_SYMBOL[:-4]))
    try:
        order_succeeded = order(side=SIDE_BUY, quantity=TRADE_QUANTITY, symbol=ticker)
        order_succeeded = True
    except Exception as e:
        print("an exception occured - {}".format(e))
        order_succeeded = False

    if order_succeeded:
        inPositionD[TRADE_SYMBOL] = True
        totalBalance = tether_balance
        TRADE_TOTAL = float(openTrades[ticker][-1]['cummulativeQuoteQty'])
        avgCost = TRADE_TOTAL / float(openTrades[TRADE_SYMBOL][-1]['executedQty'])
        for tick in TICKERS:
            if inPositionD[tick] == True:
                COST = float(openTrades[tick][-1]['cummulativeQuoteQty'])
                totalBalance = totalBalance + COST
        Portfolio_pct = round((TRADE_TOTAL / totalBalance),4)
        with open('openTrades.json', 'w+') as f:
            json.dump(openTrades, f)                        
        for number in text_list:
            bought_message = client_twilio.messages.create(
                body="A position has been bought in {} at a total price of ${}. Amount:{} {} @ ${}.".format(ticker[:-4],round(TRADE_TOTAL,2),TRADE_QUANTITY,ticker[:-4],round(avgCost,5)),
                from_="+16672443559",
                to=number)
        openTrades[TRADE_SYMBOL][-1]['last_rsi'] = last_rsi
        openTrades[TRADE_SYMBOL][-1]['Portfolio_pct'] = Portfolio_pct
        print("Exit code: InPosition = {}".format(inPositionD[TRADE_SYMBOL]))
    else:
        pass


def sell(coin_balance, ticker, tradeFormat):
    global openTrades, coinBalance, inPositionD, TRADE_QUANTITY, ROI

    print("Sell! {}".format(TRADE_SYMBOL[:-4]))
    TRADE_QUANTITY = round((float(coin_balance)*0.9999),tradeFormat)
    try:
        order_succeeded = order(side=SIDE_SELL, quantity=TRADE_QUANTITY, symbol=ticker)
        order_succeeded = True
    except Exception as e:
        print("an exception occured - {}".format(e))
        order_succeeded = False

    if order_succeeded:
        inPositionD[TRADE_SYMBOL] = False
        COST = round(float(openTrades[TRADE_SYMBOL][-2]['cummulativeQuoteQty']),2)
        REVENUE = round(float(openTrades[TRADE_SYMBOL][-1]['cummulativeQuoteQty']),2)
        Portfolio_pct = round(float(openTrades[TRADE_SYMBOL][-2]['Portfolio_pct']),3)
        with open('ROI.json', 'r') as f:
            ROI = json.load(f)
        PROFIT = REVENUE - COST - ((REVENUE+COST)*0.00075)
        PROFIT_PCT = round((PROFIT / COST),4)
        ROI = round((((PROFIT_PCT*Portfolio_pct)+1)*ROI),5)
        with open('ROI.json', 'w+') as f:
            json.dump(ROI, f)
        with open('openTrades.json', 'w+') as f:
            json.dump(openTrades, f)
        if PROFIT > 0:
            body="We sold our position in {} at a total price of ${} for a profit of around ${} or {}%. Total ROI: {}%".format(TRADE_SYMBOL[:-4],round(REVENUE,2),abs(round(PROFIT,2)),(PROFIT_PCT*100), round((ROI*100-100),2))
        else:
            body="We sold our position in {} at a total price of ${} for a loss of around ${} or {}%. Total ROI: {}%".format(TRADE_SYMBOL[:-4],round(REVENUE,2),abs(round(PROFIT,2)),(PROFIT_PCT*100), round((ROI*100-100),2))
        for number in text_list:
            sold_message = client_twilio.messages.create(
                body=body,
                from_="+16672443559",
                to=number)
        print("Exit code: InPosition = {}".format(inPositionD[TRADE_SYMBOL]))
    else:
        pass

def on_message(ws, message):
    global closes, openTrades, TRADE_SYMBOL, closes_5m, TRADE_QUANTITY
    
    # GETS JSON MESSAGE AND SETS VARIABLES
    json_message = json.loads(message)
    json_message = json_message['data']
    TRADE_SYMBOL = json_message['s']
    candle = json_message['k']
    is_candle_closed = candle['x']
    close = candle['c']
    COIN_TICKER = TRADE_SYMBOL[:-4]

    # GETS CURRENT PRICE AND COIN BALANCE
    inPosition = inPositionD[TRADE_SYMBOL]
    if inPosition:
        price_current = getPrice(TRADE_SYMBOL)
        AVG_COST = round((float(openTrades[TRADE_SYMBOL][-1]['cummulativeQuoteQty']) / float(openTrades[TRADE_SYMBOL][-1]['executedQty'])),5)

        # INSTANT SELL IF PRICE GOES UP OR BELOW PRESET %
        if ((AVG_COST * PROFIT_MULT) < price_current) or ((price_current / AVG_COST) < LOSS_MULT):
            # FORMATS TRADE QUANTITY
            tradeFormat = len(str(int(price_current)))
            
            if tradeFormat == 0:
                tradeFormat = 0
            else:
                tradeFormat = tradeFormat - 1
            
            coin_balance = getBalance(COIN_TICKER)
            ticker = TRADE_SYMBOL

            sell(coin_balance, ticker, tradeFormat)

    # RSI AND CLOSED CANDLE BRANCH
    if is_candle_closed == True:
        price_current = getPrice(TRADE_SYMBOL)
        closes[TRADE_SYMBOL].append(float(close))
        now = datetime.datetime.now()

        is_5m_closed = False
        if (str(now.minute)[-1]) == '0':
            is_5m_closed = True
        elif ((str(now.minute))[-1]) == '5':
            is_5m_closed = True


        if is_5m_closed: 
            closes_5m[TRADE_SYMBOL].append(float(close))     

        tradeFormat = len(str(int(price_current)))
        if tradeFormat == 0:
            tradeFormat = 0
        else:
            tradeFormat = tradeFormat - 1

        if len(closes[TRADE_SYMBOL]) > RSI_PERIOD:
            np_closes = numpy.array(closes[TRADE_SYMBOL])
            rsi = talib.RSI(np_closes, RSI_PERIOD)
            last_rsi = rsi[-1]

            if len(closes_5m[TRADE_SYMBOL]) > RSI_PERIOD:
                np_closes5 = numpy.array(closes_5m[TRADE_SYMBOL])
                rsi5 = talib.RSI(np_closes5, RSI_PERIOD)
                last_rsi5 = rsi5[-1]
                RSIchanger = float((last_rsi5 - 50)*0.2)
                RSI_SELL = RSI_OVERBOUGHT + (RSIchanger*0.3)
                RSI_BUY = RSI_OVERSOLD + RSIchanger
            else:
                RSI_SELL = RSI_OVERBOUGHT
                RSI_BUY = RSI_OVERSOLD
                last_rsi5 = 0
            
            if inPosition:
                print("{}:{} --  Coin: {},   RSI: {},   RSI 5m: {},  RSI Buy: {}   Price: ${}/USDT, Our average cost is {}".format(now.hour, now.minute, COIN_TICKER, round(last_rsi,2), round(last_rsi5,3), round(RSI_BUY,3), price_current, AVG_COST))
            else:
                print("{}:{} --  Coin: {},   RSI: {},   RSI 5m: {},  RSI Buy: {}   Price: ${}/USDT".format(now.hour, now.minute, COIN_TICKER, round(last_rsi,2), round(last_rsi5,3), round(RSI_BUY,3), price_current))

            # SELL LOGIC   
            if (last_rsi > RSI_SELL):
                
                if inPosition:
                    coin_balance = getBalance(COIN_TICKER)
                    ticker = TRADE_SYMBOL
                    sell(coin_balance, ticker, tradeFormat)

            # BUY LOGIC
            if (last_rsi < RSI_BUY):
                
                if inPosition:
                    pass
                else:
                    # TRADE_QUANTITY LOGIC
                    tether_balance_dic = client.get_asset_balance(asset='USDT')
                    tether_balance = round((float(tether_balance_dic['free'])),2)
                    RSI_Multiplier = float(RSI_BUY - last_rsi)
                    Portfolio_pct = PORTFOLIO_B + (RSI_WEIGHT*RSI_Multiplier)
                    if Portfolio_pct > 0.99:
                        Portfolio_pct = 0.995
                    trade_balance = round(((tether_balance/price_current)*Portfolio_pct),tradeFormat)                
                    TRADE_QUANTITY = float(abs(trade_balance))

                    if tether_balance > 15:
                        ticker = TRADE_SYMBOL
                        buy(TRADE_QUANTITY, ticker, last_rsi, tether_balance, Portfolio_pct)

        if len(closes[TRADE_SYMBOL]) > 100:
            closes[TRADE_SYMBOL].pop(0)

        if len(closes_5m[TRADE_SYMBOL]) > 100:
            closes_5m[TRADE_SYMBOL].pop(0)            

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
