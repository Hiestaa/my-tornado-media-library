$(function () {
    function isPositiveInteger(str) {
        return /^\+?(0|[1-9]\d*)$/.test(str);
    }
    function render(template, replace, options) {
        /*
        In the given template (as a string), the tags '{{<tag-id>}}'
        For each tag id found, it will look in replace. If the tag
        does exist as key, it will replace it by the corresp. value.
        */
        var res = template.slice();
        for (var tagid in replace) {
            // the 'g' flag does not work in webkit?
            res = res.replace(
                new RegExp('{{' + tagid + '}}', 'gm'),
                replace[tagid], 'gm');
        };
        return res;
    }
    /*
     Preload the list of pictures, calls back when the full batch is loaded
     This might fail if trying to load a very large batches of pictures,
     or too many batches at once. Use `preloadPictureBatched`.
     */
    function preloadPictures(pictureUrls, callback) {
        var i,
            j,
            loaded = 0;

        var done = function () {
            if (++loaded == pictureUrls.length && callback) {
                callback();
            }
        };

        if (pictureUrls.length == 0)
            return callback();
        for (i = 0, j = pictureUrls.length; i < j; i++) {
            (function (img, src) {
                img.onload = done;

                // Use the following callback methods to debug
                // in case of an unexpected behavior.
                img.onerror = function () {
                    console.log('Unable to load img: ' + src, arguments);
                    done();
                };
                img.onabort = function () {
                    console.log('Aborted loading of img: ' + src, arguments);
                    done();
                };

                img.src = src;
            } (new Image(), pictureUrls[i]));
        };
    }

    var MAX_BATCH_SIZE = 5;
    var preloadWorkQueue = [];  // list of {url, callback} objects
    var preloadCurrentBatch = {};   // mapping url => callback
    /*
     * Preload the given picture, calls back when it is ready
     * Will ensure not to have more than the maximum batch size pending requests at a given time
     * Beware this takes a single picture as parameter, unlike `preloadPictures` which takes a batch
     */
    function preloadPictureBatched(pictureUrl, callback) {
        var preloadNext = function () {
            var done = function (job, image) {
                delete preloadCurrentBatch[job.url];
                preloadNext();
                job.callback(image);
            }
            if (Object.keys(preloadCurrentBatch).length >= MAX_BATCH_SIZE) { return; }
            if (preloadWorkQueue.length === 0) { return; }

            var job = preloadWorkQueue.shift(0);
            preloadCurrentBatch[job.url] = job.callback;
            var img = new Image();
            img.onload = function () {
                done(job, this);
            };
            img.onerror = function () {
                console.log('Unable to load img: ' + job.url, this,  arguments);
                // done(job);
            };
            img.onabort = function () {
                console.log('Aborted loading of img: ' + job.url, this,  arguments);
                // done(job);
            };
            img.src = job.url;

            preloadNext();
        }

        preloadWorkQueue.push({url: pictureUrl, callback: callback});

        preloadNext();
    }

    function spinLoading(stop) {
        if (stop)
            $('body > #loading-overlay').css('display', 'none');
        else
            $('body > #loading-overlay').css('display', 'table');
    }

    function colorMapping(type, value) {
        var _gradient = function(val, min, max, inv) {
            var r = (val - min) * 255.0 / (max - min);
            var g = (max - (val - min)) * 255.0 / (max - min);
            r = Math.max(0, Math.min(255, r));
            g = Math.max(0, Math.min(255, g));
            r = parseInt(r).toString(16);
            g = parseInt(g).toString(16);
            if (r.length < 2)
                r = '0' + r;
            if (g.length < 2)
                g = '0' + g;
            if (inv)
                [r, g] = [g, r]
            return '#' + r + g + '00';
        }
        if (type == 'resolution') {
            if (value[0] < 1280 && value[1] < 720)
                return '#FF0000'
            else if (value[0] < 1920 && value[1] < 1080)
                return "#FFF200"
            else
                return "#00FF00"
        }
        if (type == 'duration') {
            var min_time = 200.0;  // 3min20
            var max_time = 1200.0;  // 20min
            var max_color = 255.0;
            return _gradient(value, min_time, max_time);
        }
        if (type == 'size') {
            return _gradient(
                value,
                1024 * 1024 * 100,
                1024 * 1024 * 1024);
        }
        if (type == 'fps') {
            return _gradient(value, 20, 60, true);
        }
        if (type == 'faceTimeProp') {
            return _gradient(value, 30, 80, true);
        }
    };


    function FullPageOverlay () {
        var self = this;

        self.overlayTimeout = null;

        self.show = function () {
            $('#full-page-overlay').removeClass('no-transition').addClass('visible');
            clearTimeout(self.overlayTimeout);
        }

        self.hide = function () {
            $('#full-page-overlay').addClass('no-transition').removeClass('visible')
            clearTimeout(self.overlayTimeout);
            self.overlayTimeout = setTimeout(() => $('#full-page-overlay').removeClass('no-transition'), 10000);
        }
    }


    window.render = render;
    window.preloadPictures = preloadPictures;
    window.preloadPictureBatched = preloadPictureBatched;
    window.spinLoading = spinLoading;
    window.isPositiveInteger = isPositiveInteger;
    window.colorMapping = colorMapping;
    window.fullPageOverlay = new FullPageOverlay();

    $('#close-spinner').click(function () {
        spinLoading('stop');
    });
});
