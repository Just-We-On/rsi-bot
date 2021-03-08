# rsi-bot
Scans binance for oversold cryptocurrencies. Sends buy order and tracks performance of position. Closes position after pre-set profit/loss level is passed

## Installing Dependencies
For this program we will be using websocket, json, pprint, talib, numpy, datetime, os, binance.client, and twilio.rest

To set up the needed packages, RUN the following command in your terminal after making sure the "requirements.txt" file is in your local directory. 

pip install -r requirements.txt

## Set Up Tips

- You must have a Binance account in order to use this program (and a Twilio account for SMS updates when the program makes trades.) 
  - NOTE: This program is built for the main Binance.com platform not Binance US. Using Binance.com inside the US (with a US IP address) is prohibited so, do so at your own risk. 
- Create a config.py file in your local directory and set your Binance API Public Key equal to API_KEY, set your API private key equal to API_SECRET
- If you want to use the twilio SMS feature then repeat the same steps with account_sid and auth_token
- Once you've set up the Twilio and Binance API, you can adjust the buy/sell parameter to adjust how risky you want the program to behave. You can also choose the 5 cryptocurrencies you want to trade. 




Disclaimer: This program is just for learning purposes and I do not guarantee any potential success/profits from using it. Use this code at your own risk
