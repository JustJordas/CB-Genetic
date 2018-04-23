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

populationSize = int(sys.argv[1])
crossoverTimes = int(sys.argv[2])
keepPercentage = float(sys.argv[3])
mutationChance = float(sys.argv[4])

data = []
#steps = [1, 5, 15, 30, 60]
#fibs = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
steps = [1, 5, 10, 15]
fibs = [1, 2, 3, 5, 8, 13]
n = len(fibs)
#n = 5
pastSteps = fibs[n - 1]
upOrDown = [0.0] * int(n * (n - 1) + n*n)
SMAs = [0.0] * n
EMAs = [0.0] * n
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
            if ((self.calculateSellProbability() > 0.5)) or coin['price'] < self.bought['price'] * self.stopLoss:

                self.history.append({
                    'bought': self.bought,
                    'sold': coin
                })

                self.profit += coin['price'] - self.bought['price'] - self.bought['fee']
                self.bought = {}

    def crossover(self, mate):
        newBuyWeights = []
        newSellWeights = []
        newScore = 0.0
        newIteration = 0
        newHistory = []
        newProfit = 0.0

        if self.profit < mate.profit:
            newScore = self.score + 0.2 * (mate.score - self.score)
            newProfit = self.profit
            newIteration = self.iteration
            for i in range(0, len(self.history)):
                newHistory.append(self.history[i])
        else:
            newScore = mate.score + 0.2 * (self.score - mate.score)
            newProfit = mate.profit
            newIteration = mate.iteration
            for i in range(0, len(mate.history)):
                newHistory.append(mate.history[i])

        for i in range(0, self.k):
            if random.random() > 0.5:
                newBuyWeights.append(mate.buyWeights[i])
            else:
                newBuyWeights.append(self.buyWeights[i])
            if random.random() > 0.5:
                newSellWeights.append(mate.sellWeights[i])
            else:
                newSellWeights.append(self.sellWeights[i])
        
        return Entity(newScore, newProfit, newBuyWeights, newSellWeights, newHistory, newIteration)

    def mutate(self):
        global mutationChance

        for i in range(0, self.k):
            if random.random() <= mutationChance:
                self.buyWeights[i] += random.gauss(0, 0.05)
            if random.random() <= mutationChance:
                self.sellWeights[i] += random.gauss(0, 0.05)
            if random.random() <= mutationChance / 5:
                self.buyWeights[i] += random.gauss(0, 0.25)
            if random.random() <= mutationChance / 5:
                self.sellWeights[i] += random.gauss(0, 0.25)
            if random.random() <= mutationChance / 25:
                self.buyWeights[i] += random.gauss(0, 0.5)
            if random.random() <= mutationChance / 25:
                self.sellWeights[i] += random.gauss(0, 0.5)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(int(self.score)) + ' (' + str(self.profit) + ', ' + str(self.iteration) + ')'

    def dump(self):
        return str(int(self.score)) + ' (' + str(self.profit) + ', ' + str(self.iteration) + ') --> \n' + str(self.buyWeights) + '\n' + str(self.sellWeights)

start_time = -1
outputTime = 0

for k in range(0, len(steps)):
    population[k] = []
    for i in range(0, populationSize):
        population[k].append(Entity())

mongo_client = MongoClient('localhost', 27017)

db = mongo_client.binance

collection = db.BTC
strategyCollection = db.strategy

strategyCollection.delete_many({
    'strategy': 'moving_averages'
})

data = collection.find().sort([
    ('time', pymongo.ASCENDING)
])

localTime = data[data.count() - 1]['time']

print(localTime)

start_time = localTime

import numpy as np

data = np.array(list(collection.find({
    'time': {
        '$gt': localTime - 60 * 150         #technically 144, but better safe than sorry
    }
}).sort([
    ('time', pymongo.ASCENDING)
])))

print(data.size)

#cursor.sort(key=lambda x: x.time, reverse=False)

#localTime -= 1

outputTime = [0] * len(steps)

current_milli_time = lambda: int(round(time.time() * 1000))

while True:
    print('Time: ' + str(localTime))
    t0 = current_milli_time()

    data = np.delete(data, 0)

    newEntry = []

    while len(newEntry) == 0:
        newEntry = list(collection.find({
            'time': localTime
        }))

    data = np.append(data, list(newEntry)[0])

    last = data.size - 1

    for k in range(0, len(steps)):
        step = steps[k]
        epoch = 60 * step

        for i in range(0, n):
            SMAs[i] = 0.0
            EMAs[i] = 0.0

            countSMA = 0.0
            countEMA = 0.0

            for j in range(last - (fibs[i] + 1) * step, last + step, step):
                SMAs[i] += data[j]['price']
                countSMA += 1.0
            SMAs[i] /= countSMA

            ratio = 0.5
            for j in range(last, last - (fibs[i]) * step, -step):
                EMAs[i] += data[j]['price'] * ratio
                countEMA += ratio
                ratio *= 0.5
            EMAs[i] /= countEMA

        upOrDown = []

        #print("SMAs: " + str(SMAs))
        #print("EMAs: " + str(EMAs))

        for i in range(0, n - 1):
            for j in range(i + 1, n):
                if SMAs[i] > SMAs[j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        for i in range(0, n - 1):
            for j in range(i + 1, n):
                if EMAs[i] > EMAs[j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        for i in range(0, n):
            for j in range(0, n):
                if SMAs[i] > EMAs[j]:
                    upOrDown.append(1.0)
                else:
                    upOrDown.append(-1.0)

        #print('Up or down: ' + str(upOrDown))
        
        for i in range(0, populationSize):
            population[k][i].score = 0.0

            population[k][i].trade(data[last])

            for j in range(0, len(population[k][i].history)):
                population[k][i].score += population[k][i].history[j]['sold']['price'] - population[k][i].history[j]['bought']['price'] - population[k][i].history[j]['bought']['fee']
        
        #print('Population: ' + str(population))

        population[k].sort(key=lambda x: [x.score, x.profit], reverse=True)

        #print('Sorted population: ' + str(population))

        newPopulation = []

        keepNumber = int(keepPercentage * populationSize)

        for i in range(0, keepNumber):
            population[k][i].iteration += 1
            if population[k][i].iteration < epoch or population[k][i].score > 0.0:                
                newPopulation.append(population[k][i])

        for i in range(keepNumber, populationSize):
            if population[k][i].iteration < epoch:
                newPopulation.append(population[k][i])
        
        population[k] = list(newPopulation)

        #print('Kept population: ' + str(population))

        showTop50 = min(50, min(int(populationSize / 20) + 1, len(population[k])))

        #if k == 4:
       

        for i in range(0, keepNumber):
            if bool(population[k][i].bought) == False:
                for j in range(0, crossoverTimes):
                    population[k].append(population[k][i].crossover(population[k][random.randint(0, len(population[k]) - 1)]))

        for i in range(0, len(population[k])):
            if bool(population[k][i].bought) == False:
                population[k][i].mutate()

        while len(population[k]) < populationSize:
            population[k].append(Entity())

        if localTime - start_time > (outputTime[k] + 1) * epoch:
            #workfileName = str(sys.argv[0]) + '_' + str(step) + '_' + str(epoch) + '_' + str(n) + '_population' + str(populationSize) + '_crossoverTimes' + str(crossoverTimes) + '_keepPercentage' + str(keepPercentage) + '_mutationChance' + str(mutationChance) + '_alive' + str(outputTime[k]) + '.txt'
            #outputFile = open(workfileName, 'w')

            strategyCollection.delete_many({
                'strategy': 'moving_averages',
                'step': step,
                'fibs': n
            })

            for l in range(0, showTop50):
                strategy = {
                    '_id': ObjectId(),
                    'strategy': 'moving_averages',
                    'step': step,
                    'fibs': n,
                    'time': last,
                    'score': population[k][l].score,
                    'buyWeights': population[k][l].buyWeights,
                    'sellWeights': population[k][l].sellWeights
                }

                strategyCollection.insert_one(strategy)
            

            #for i in range(0, keepNumber):
            #    outputFile.write(str(population[k][i].dump()) + '\n')

            #outputFile.close()
            outputTime[k] += 1
        if k == 4:
            print('Strategies in collection: ' + str(strategyCollection.count()))
    
    for k in range(0, len(steps)):
        print()
        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Top' + str(steps[k]) + '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

        for i in range(0, int(showTop50 / 2)):
            print(str(i + 1) + '.\t' + str(population[k][i]))

    t1 = current_milli_time()

    print(t1 - t0)

    time.sleep(1 - (t1 - t0) / 1000)
    localTime += 1