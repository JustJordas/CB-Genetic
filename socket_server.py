import pymongo
from pymongo import MongoClient
import asyncio
import websockets
from bson.json_util import dumps
import time

mongo_client = MongoClient('localhost', 27017)

db = mongo_client.binance

populationTraded = db.populationTraded

steps = [1, 5, 15, 30, 60]

population = {}

async def sendData(websocket, path):

	for i in range(0, len(steps)):
		population[steps[i]] = []

	results = list(populationTraded.find({}))
	for i in range(0, len(results)):
		pop = {
			'score': results[i]['score'],
			'profit': results[i]['profit'],
			'history': results[i]['history']
		}

		population[results[i]['step']].append(pop)

	print(population)

	print('Received message');
	await websocket.send(dumps(population))
	time.sleep(1)
	await sendData(websocket, path)

asyncio.get_event_loop().run_until_complete(
	websockets.serve(sendData, 'localhost', 8081))
asyncio.get_event_loop().run_forever()