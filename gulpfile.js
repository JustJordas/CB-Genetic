const gulp = require('gulp');
const nodemon = require('gulp-nodemon');

var jsFiles = ['*.js', 'src/**/*.js'];


gulp.task('serve', function () {
    var options = {
        script: 'server.js',
        delayTime: 1,
        env: {
            'PORT': 8080
        },
        watch: jsFiles
    }

    return nodemon(options)
        .on('restart', function (e) {
            console.log('Restarting...');
        })
});