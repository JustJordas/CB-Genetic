import pymongo
from pymongo import MongoClient
import datetime
import sys
import time
import pytz
import json
from binance.client import Client
from binance.websockets import BinanceSocketManager
import random
import math
from bson.objectid import ObjectId

mongo_client = MongoClient('localhost', 27017)

db = mongo_client.binance

db.BTC.drop()

collection = db.BTC

client = Client('5eCTxuKOs5VPCNZHVoeutoIV4fthRaGunndt1K77gqjK19lIuPar0Y8GzHrveVoE', 'BnF5gPIUfHVSRgwwinI8fku1sRIhteehlZdIiZEeZmAJihEUnB4xt0XUb5EXeJIr')

prices = client.get_all_tickers()
bm = BinanceSocketManager(client)

class MyDict(dict):
    pass

tick = {}
localTime = 0

def process_message(tickers):
    global tick, collection, localTime   

    if localTime == 0:
        localTime = int(int(tickers[0]['E']) / 1000)

    for ticker in tickers:
        if ticker['s'] == 'BTCUSDT':
            tick = {
                'symbol': ticker['s'],
                'price': float(ticker['c']),
                'qouteVolume': float(ticker['q']),
                'volume': float(ticker['v']),
                'high': float(ticker['h']),
                'low': float(ticker['l'])
            }
    #collection.insert_one(tick)

    
# start any sockets here, i.e a trade socket
conn_key = bm.start_miniticker_socket(process_message)
# then start the socket manager

bm.start()

current_milli_time = lambda: int(round(time.time() * 1000))

tick = {}

while True:
    global tick, localTime
    t0 = current_milli_time()

    if localTime > 0:
        localTime += 1
        collection.delete_many({
            'time': {
                '$lt': localTime - int(sys.argv[1])
            }
        })

    tick['_id'] = ObjectId()
    tick['time'] = localTime
    if len(tick) == 8:
        collection.insert_one(tick)
        print(str(collection.count()) + ' --> ' + str(tick))

    t1 = current_milli_time()
    try:
        time.sleep(1 - (t1 - t0) / 1000)
    except ValueError:
        print(ValueError)