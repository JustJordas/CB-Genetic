const express = require('express');
const expressSession = require('express-session');
const bodyParser = require('body-parser');

//const authRouter = require('./src/routes/authRoutes')();

const MongoClient = require('mongodb').MongoClient;

var app = express();

var sessionOptions = {
	secret: 'AAI',
	resave: false,
	saveUninitialized: true
}

app.use(bodyParser({ limit: '50mb' }));

app.use(express.static('public'));
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({
	extended: true
}));
app.use(expressSession(sessionOptions));

// set the view engine to ejs
app.set('views', './src/views');
app.set('view engine', 'ejs');
//Set routing for authetication
//app.use('/auth', authRouter);

// index page 
app.get('/', function (req, res) {
	res.render('index');
});

app.listen(8080);
console.log("Server started on port: 8080");

function max(a, b) {
	return a > b ? a : b;
}

steps = [1, 5, 15, 30, 60]

population = {}

MongoClient.connect("mongodb://localhost:27017/", function (err, client) {

    const db = client.db('binance');

    db.collection('populationTraded', function (err, collection) {

        collection.find().toArray(function (err, population) {
            if (err) throw err;

            console.log(population.length);
            client.close();
        });
    });
});




//Load users from DB and set them all to authenticated (FALSE)

const webSocket = require('ws');

const wss_general = new webSocket.Server({
	port: 8081
});

wss_general.on('connection', function connection(ws, req) {
    console.log('%s: connected - %s', new Date(), req.connection.remoteAddress);
    
    setInterval(function() { 
        MongoClient.connect("mongodb://localhost:27017/", function (err, client) {

        const db = client.db('binance');

        db.collection('populationTraded', function (err, collection) {

            collection.find().toArray(function (err, population) {
                if (err) throw err;

                ws.send(JSON.stringify(population));

                console.log(population.length);
                client.close();
            });
        });
    });
    }, 1000);

	ws.on('message', function incoming(message) {});

	ws.on('close', function close() {});

	ws.on('error', () => console.log('errored'));
});