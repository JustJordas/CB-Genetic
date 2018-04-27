import datetime
import sys
import time
import pytz
import json
import random
import math
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId

def sigmoid(x):
    return 1 / (1 + math.exp(-x))

germanyTZ = pytz.timezone('Europe/Berlin')

def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(germanyTZ)
    return germanyTZ.normalize(local_dt) # .normalize might be unnecessary

data = []
steps = [5, 15]
fibs = [1, 2, 3, 5, 8, 13, 21, 34, 55]
n = len(fibs)
#n = 5
pastSteps = fibs[n - 1]
upOrDown = [0.0] * int(n * (n - 1) + n*n)

SMAs = [[0.0] * n] * len(steps)
EMAs = [[0.0] * n] * len(steps)
currentBTCPrice = 0.0

population = [[]] * len(steps)

localTime = 0

class Entity:
    k = len(upOrDown)

    def __init__ (self, newScore=None, newProfit=None, newBuyWeights=None, newSellWeights=None, history=None, iteration=None):
        self.profit = 0.0

        if newScore is None:
            self.score = 0.0
            self.profit = 0.0
        else:
            self.score = newScore
            self.profit = newProfit
            
        #set initial random multipliers for rise / fall weights (-1, 1)
        self.buyWeights = []
        self.sellWeights = []
        self.history = []

        self.bought = {}

        self.stopLoss = 0.98

        if newBuyWeights is None:
            for i in range(0, self.k):
                self.buyWeights.append(random.gauss(0, 0.3))
        else:
            for i in range(0, self.k):
                self.buyWeights.append(newBuyWeights[i])

        if newSellWeights is None:
            for i in range(0, self.k):
                self.sellWeights.append(random.gauss(0, 0.3))
        else:
            for i in range(0, self.k):
                self.sellWeights.append(newSellWeights[i])

        if history is None:
            self.history = []
        else:
            for i in range(0, len(history)):
                self.history.append(history[i])
        if iteration is None:
            self.iteration = 1
        else:
            self.iteration = iteration
    
    def update(self, newBuyWeights=None, newSellWeights=None):
        self.buyWeights = []
        self.sellWeights = []

        if newBuyWeights is None:
            for i in range(0, self.k):
                self.buyWeights.append(random.gauss(0, 0.3))
        else:
            for i in range(0, self.k):
                self.buyWeights.append(newBuyWeights[i])

        if newSellWeights is None:
            for i in range(0, self.k):
                self.sellWeights.append(random.gauss(0, 0.3))
        else:
            for i in range(0, self.k):
                self.sellWeights.append(newSellWeights[i])
    
    def calculateBuyProbability(self):
        sum = 0.0

        global upOrDown

        for i in range(0, self.k):
            sum += self.buyWeights[i] * upOrDown[i]

        return sigmoid(sum)

    def calculateSellProbability(self):
        sum = 0.0

        global upOrDown

        for i in range(0, self.k):
            sum += self.sellWeights[i] * upOrDown[i]

        return sigmoid(sum)

    def trade(self, coin):
        global localTime, epoch

        while len(self.history) > 0 and self.history[0]['bought']['time'] < localTime - epoch:
            self.history.pop(0)

        if bool(self.bought) == False:
            if self.calculateBuyProbability() > 0.5:
                self.bought = coin
                self.bought['fee'] = coin['price'] * 0.000
        else:
            if self.calculateSellProbability() > 0.5 or coin['price'] <= self.bought['price'] * self.stopLoss:
                
                self.history.append({
                    'bought': self.bought,
                    'sold': coin
                })

                self.profit += coin['price'] - self.bought['price'] - self.bought['fee']
                self.bought = {}

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(int(self.score)) + ' (' + str(self.profit) + ', ' + str(self.iteration) + ')'

    def dump(self):
        return str(int(self.score)) + ' (' + str(self.profit) + ', ' + str(self.iteration) + ') --> \n' + str(self.buyWeights) + '\n' + str(self.sellWeights)

start_time = -1
outputTime = 0

mongo_client = MongoClient('localhost', 27017)

db = mongo_client.binance

strategyCollection = db.strategy

populationTraded = db.populationTraded

current_milli_time = lambda: int(round(time.time() * 1000))

for k in range(0, len(steps)):
    population[k] = []

    results = list(strategyCollection.find({
        'strategy': 'moving_averages',
        'step': steps[k],
        'fibs': n
    }))

    for i in range(0, int(len(results))):
        population[k].append(Entity(newBuyWeights=results[i]['buyWeights'], newSellWeights=results[i]['sellWeights']))

collection = db.BTC

data = collection.find().sort([
    ('time', pymongo.ASCENDING)
])

localTime = data[data.count() - 1]['time']

print(localTime)

start_time = localTime

data = list(collection.find({
    'time': {
        '$gt': localTime - 60 * 150         #technically 144, but better safe than sorry
    }
}).sort([
    ('time', pymongo.ASCENDING)
]))

print(len(data))

#cursor.sort(key=lambda x: x.time, reverse=False)

#localTime -= 1

outputTime = [0] * len(steps)

last = len(data) - 1

for k in range(0, len(steps)):
    step = steps[k]

    for i in range(0, n):
        SMAs[k][i] = 0.0
        EMAs[k][i] = 0.0

        countSMA = 0.0
        countEMA = 0.0

        for j in range(last - (fibs[i]) * step, last + step, step):
            SMAs[k][i] += data[j]['price']
            countSMA += 1.0
        SMAs[k][i] /= countSMA

        ratio = 0.5
        for j in range(last, last - (fibs[i]) * step, -step):
            EMAs[k][i] += data[j]['price'] * ratio
            countEMA += ratio
            ratio *= 0.5
        EMAs[k][i] /= countEMA

while True:
    populationTraded.delete_many({})
    print('Time: ' + str(localTime))
    t0 = current_milli_time()
    data.pop(0)

    newEntry = collection.find({
        'time': localTime
    })

    data.append(list(newEntry)[0])

    last = len(data) - 1

    for k in range(0, len(steps)):
        results = list(strategyCollection.find({
            'strategy': 'moving_averages',
            'step': steps[k],
            'fibs': n
        }))

        for i in range(0, int(len(results))):
            if len(population[k]) > 0:
                for j in range(0, len(population[k])):
                    population[k][j].update(newBuyWeights=results[i]['buyWeights'], newSellWeights=results[i]['sellWeights'])
                while len(population[k]) < int(len(results) / 5):
                    population[k].append(Entity(newBuyWeights=results[i]['buyWeights'], newSellWeights=results[i]['sellWeights']))
            else:
                population[k].append(Entity(newBuyWeights=results[i]['buyWeights'], newSellWeights=results[i]['sellWeights']))

        step = steps[k]
        epoch = 180 * step

        for i in range(0, n):
            SMAs[k][i] += (data[last]['price'] - data[last - (fibs[i] + 1) * step]['price']) / fibs[i]
            EMAs[k][i] = EMAs[k][i] * 0.5 + data[last]['price'] - data[last - (fibs[i] + 1) * step]['price'] * (0.5 ** fibs[i])

        upOrDown = []

        for i in range(0, n - 1):
            for j in range(i + 1, n):
                if SMAs[k][i] > SMAs[k][j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        for i in range(0, n - 1):
            for j in range(i + 1, n):
                if EMAs[k][i] > EMAs[k][j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        for i in range(0, n):
            for j in range(0, n):
                if SMAs[k][i] > EMAs[k][j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        #print('Up or down: ' + str(upOrDown))
        
        for i in range(0, len(population[k])):
            population[k][i].score = 0.0

            population[k][i].trade(data[last])

            for j in range(0, len(population[k][i].history)):
                population[k][i].score += population[k][i].history[j]['sold']['price'] - population[k][i].history[j]['bought']['price'] - population[k][i].history[j]['bought']['fee']
        
        #print('Population: ' + str(population))

        population[k].sort(key=lambda x: x.score, reverse=True)

        #print('Sorted population: ' + str(population))

        #print('Kept population: ' + str(population))

        showTop50 = int(len(population[k]) / 5)

        print()
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Top' + str(steps[k]) + '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

        for i in range(0, showTop50):
            print(str(i + 1) + '.\t' + str(population[k][i]))

        if localTime - start_time > (outputTime[k] + 1) * epoch:
            #workfileName = str(sys.argv[0]) + '_' + str(step) + '_' + str(epoch) + '_' + str(n) + '_population' + str(populationSize) + '_crossoverTimes' + str(crossoverTimes) + '_keepPercentage' + str(keepPercentage) + '_mutationChance' + str(mutationChance) + '_alive' + str(outputTime[k]) + '.txt'
            #outputFile = open(workfileName, 'w')

            
            

            #for i in range(0, keepNumber):
            #    outputFile.write(str(population[k][i].dump()) + '\n')

            #outputFile.close()
            outputTime[k] += 1

    for k in range(0, len(steps)):
        for i in range(0, len(population[k])):
            pop = {
                '_id': ObjectId(),
                'strategy': 'moving_averages',
                'step': steps[k],
                'time': last,
                'score': population[k][i].score,
                'profit': population[k][i].profit,
                'buyWeights': population[k][i].buyWeights,
                'sellWeights': population[k][i].sellWeights,
                'history': population[k][i].history
            }

            populationTraded.insert_one(pop)

    t1 = current_milli_time()
    time.sleep(1 - (t1 - t0) / 1000)
    localTime += 1

