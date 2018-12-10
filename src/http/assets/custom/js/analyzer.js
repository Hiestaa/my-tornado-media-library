
/*
 * Establish the websocket connection required to submit the video analysis request.
 * Visually report the progress of the process in a fixed frame.
 * The process starts immediately once the object is constructed.
 */
$(function () {
    var MARKER_COLOR = '#BB6B00';
    var MARKER_BORDER_COLOR = '#BB4800';
    var MARKER_FRAME_COLOR = '#DA7D00';
    var FACE_FRAME_COLOR = '#FFAF43';
    var CROP_FRAME_COLOR = '#00C4E1';
    function Visualizer($view, thumbnail, videoId, options) {
        var self = this;

        self.$view = $view;

        options = options || {};
        self._onClickPlay = options.onClickPlay || function () {};
        self._onClickPause = options.onClickPause || function () {};
        self._onClickForward = options.onClickForward || function () {};
        self._onClickBackward = options.onClickBackward || function () {};
        self._onAddTag = options.onAddTag || function () {};
        self._initialDelay = options.initialDelay || 1000.0 / 12.0;

        self._template = '\
<div id="analyze-modal" class="uk-modal">\
    <div class="uk-modal-dialog large">\
        <button type="button" class="uk-modal-close uk-close"/>\
        <h1 class="uk-modal-header">Analyze in progress...</h1>\
        <p>A visualization of the progress of the analysis will appear below.</p>\
        <div id="board-container">\
            <!-- If the annotations are off, it may be that these dimensions are not matching the ones defined in the config -->\
            <img class="default-size" width="800" height="450" id="image-board" src="{{thumbnail}}"></img>\
            <canvas width="800" height="450" id="canvas-board"></canvas>\
            <span class="status row-1 center" id="pause"><i class="uk-icon-pause"></i></span>\
            <span class="status row-1 center hidden" id="play"><i class="uk-icon-play"></i></span>\
            <span class="status row-1 left" id="forward"><i class="uk-icon-backward"></i></span>\
            <span class="status row-1 right" id="backward"><i class="uk-icon-forward"></i></span>\
            <span class="status row-2 center large"><i class="uk-icon-clock-o"></i><span id="delay">{{delay}}</span></span>\
        </div>\
        <hr>\
        <h3>Computed Properties</h3>\
        <h4>Face Ratio<span id="average-face-ratio"></span></h4>\
        <div id="face-ratio"></div>\
        <h4>Detection Confidence<span id="average-face-time-ratio"></span></h4>\
        <div id="face-detection-confidence"></div>\
        <hr>\
        <h3>Related Images</h3>\
        <div id="imgs-board" class="uk-grid">\
        </div>\
        <hr>\
        <h3>Suggested Tags<input style="float: right" type="number" id="tags-limit" value="30" /></h3>\
        <div id="tags-board">\
        </div>\
        <div class="uk-modal-footer">\
            <h3>More details...</h3>\
            <pre id="details-board"></pre>\
        </div>\
    </div>\
</div>';

        self.$imageBoard = null;
        self.$detailsBoard = null
        self._canvas = null;
        self._canvasCtx = null;
        self.$tagsBoard = null;
        self.$tagsLimit = null;
        self.$averageFaceRatio = null;
        self.$faceTime = null;
        self._videoId = videoId;

        self.renderView = function () {
            self.$view.html(render(self._template, {
                thumbnail: thumbnail,
                delay: self._initialDelay
            }));
            self.$imageBoard = self.$view.find('#image-board');
            self.$detailsBoard = self.$view.find('#details-board');
            self._canvas = document.getElementById('canvas-board');
            self._canvasCtx = self._canvas.getContext('2d');
            self.$tagsBoard = self.$view.find('#tags-board');
            self.$tagsLimit = self.$view.find('#tags-limit');
            self.$imgsBoard = self.$view.find('#imgs-board');
            self.$averageFaceRatio = self.$view.find('#average-face-ratio');
            self.$faceTime = self.$view.find('#average-face-time-ratio');
            self.show();
        }

        self.events = function () {
            self.$view.find("#board-container #pause").click(function () {
                self.$view.find("#board-container #pause").toggleFGClass('hidden');
                self.$view.find("#board-container #play").toggleClass('hidden');
                self._onClickPause();
            });
            self.$view.find("#board-container #play").click(function () {
                self.$view.find("#board-container #pause").toggleClass('hidden');
                self.$view.find("#board-container #play").toggleClass('hidden');
                self._onClickPlay();
            });
            self.$view.find("#board-container #forward").click(function () {
                self._onClickForward();
            });
            self.$view.find("#board-container #backward").click(function () {
                self._onClickBackward();
            });
            self.$view.find('#tags-limit').change(function () {
                self._displayLabels();
            })
        }

        self.updateDelay = function (value) {
            self.$view.find('#delay').text(value.toString().slice(0, 5));
        }

        self.show = function () {
            var dialog = $.UIkit.modal('#analyze-modal');
            if (!dialog.isActive())
                dialog.show();
        }

        self.prepareDisplayFrame = function (data, done) {
            var t = Date.now();
            data.preloadUrl = '/download/minivid/' + self._videoId + '/' + data.frame
            preloadPictures([data.preloadUrl], function () {
                data._preloadDuration = Date.now() - t;
                done(data);
            })
        }

        self._tryLoad = function (webData, done) {
            var stopped = false;
            var stop = function () {
                if (stopped) { return; }
                stopped = true;
                done([]);
            };
            var timeout = setTimeout(stop, 10000);
            var pictures = webData.full_matching_images.map(function(img) { return img.url; });
            preloadPictures(pictures, function () {
                if (stopped) {
                    return;
                }
                stopped = true
                done(pictures.map(function (url, idx) {
                    if (webData.pages_with_matching_images.length > idx) {
                        return {imgUrl: url, pageUrl: webData.pages_with_matching_images[idx].url};
                    }
                    return {imgUrl: url};
                }));
            });
        }

        self.prepareDisplayAnnotationRaw = function (data, done) {
            var t = Date.now();
            data.preloadUrl = '/download/minivid/' + self._videoId + '/' + data.frame
            data.loadedWebData = [];
            preloadPictures([data.preloadUrl], function () {
                data._preloadDuration = Date.now() - t;
                self._tryLoad(data.annotation.web, function (loadedWebData) {
                    data.loadedWebData = loadedWebData;
                    // if (loadedWebData.length != data.annotation.web.full_matching_images.length) { debugger; }
                    done(data);
                })
            })
        }

        self.prepareDisplayAnnotationPP = function (data, done) {
            var t = Date.now();
            data.preloadUrl = '/download/minivid/' + self._videoId + '/' + data.frame
            preloadPictures([data.preloadUrl], function () {
                data._preloadDuration = Date.now() - t;
                done(data);
            })
        }

        self.prepareDisplayResult = function (data, done) {
            rand = Math.random() * 1000;
            data.prepTime = rand;
            setTimeout(function () {
                done(data);
            }, rand);
        }

        self.displayFrame = function (data) {
            self._clearCanvas();
            var frame = data.frame;
            var msg = "Executing action: displayFrame, frame#" + frame;
            console.log(msg, data);
            self.$detailsBoard.html(msg);
            self.$imageBoard.attr('src', data.preloadUrl);
        }

        self._displayLandmark = function (landmark) {
            var RADIUS = 2;
            self._canvasCtx.beginPath();
            self._canvasCtx.arc(landmark.position.x, landmark.position.y, RADIUS, 0, 2 * Math.PI, false);
            self._canvasCtx.fillStyle = MARKER_COLOR;
            self._canvasCtx.fill();
            self._canvasCtx.lineWidth = 1;
            self._canvasCtx.strokeStyle = MARKER_BORDER_COLOR;
            self._canvasCtx.stroke();
        }

        self._displayFace = function (faceData) {
            var MARGIN = 3;
            var minPosX = -1;
            var minPosY = -1;
            var maxPosX = -1;
            var maxPosY = -1;
            faceData.landmarks.map(function (landmark) {
                if (minPosY == -1 || landmark.position.y < minPosY) {
                    minPosY = landmark.position.y;
                }
                if (minPosX == -1 || landmark.position.x < minPosX) {
                    minPosX = landmark.position.x;
                }
                if (maxPosY == -1 || landmark.position.y > maxPosY) {
                    maxPosY = landmark.position.y;
                }
                if (maxPosX == -1 || landmark.position.x > maxPosX) {
                    maxPosX = landmark.position.x;
                }
                self._displayLandmark(landmark);
            });

            var bounds = [
                minPosX, minPosY, maxPosX, maxPosY
            ];
            self._canvasCtx.beginPath();
            self._canvasCtx.rect(
                bounds[0] - MARGIN,
                bounds[1] - MARGIN,
                bounds[2] - bounds[0] + MARGIN,
                bounds[3] - bounds[1] + MARGIN);
            self._canvasCtx.lineWidth = 1;
            self._canvasCtx.strokeStyle = MARKER_FRAME_COLOR;
            self._canvasCtx.stroke();
            var bounds = [
                faceData.bounding_poly[0].x,
                faceData.bounding_poly[0].y,
                faceData.bounding_poly[2].x,
                faceData.bounding_poly[2].y
            ];
            self._canvasCtx.beginPath();
            self._canvasCtx.rect(
                bounds[0] - MARGIN,
                bounds[1] - MARGIN,
                bounds[2] - bounds[0] + MARGIN,
                bounds[3] - bounds[1] + MARGIN);
            self._canvasCtx.lineWidth = 2;
            self._canvasCtx.strokeStyle = FACE_FRAME_COLOR;
            self._canvasCtx.stroke();
        }

        self._displayCrop = function (cropData) {
            var bounds = [
                cropData.bounding_poly[0].x,
                cropData.bounding_poly[0].y,
                cropData.bounding_poly[2].x,
                cropData.bounding_poly[2].y
            ];
            if (bounds[0] > 30 || bounds[1] > 30 ||
                bounds[2] < self._canvas.width - 30 ||
                bounds[3] < self._canvas.height - 30) {

                self._canvasCtx.beginPath();
                self._canvasCtx.rect(
                    bounds[0],
                    bounds[1],
                    bounds[2] - bounds[0],
                    bounds[3] - bounds[1]);
                self._canvasCtx.lineWidth = 2;
                self._canvasCtx.strokeStyle = CROP_FRAME_COLOR;
                self._canvasCtx.stroke();
            }
        }

        // label description -> {count: count of occurrences, confidence: sum of condidences}
        self._labelsCounts = null;
        self._displayLabels = function (labelsData) {
            if (labelsData) {
                labelsData.forEach(function (labelData) {
                    self._labelsCounts[labelData.description] = self._labelsCounts[labelData.description] || {};
                    self._labelsCounts[labelData.description].count = self._labelsCounts[labelData.description].count || 0
                    self._labelsCounts[labelData.description].confidence = self._labelsCounts[labelData.description].confidence || 0
                    self._labelsCounts[labelData.description].count += 1;
                    self._labelsCounts[labelData.description].confidence += labelData.score;
                });
            }
            var sortedTags = Object.keys(self._labelsCounts).sort(function(label1, label2) {
                return (self._labelsCounts[label2].confidence -
                        self._labelsCounts[label1].confidence);
            });
            var nbTags = parseInt(self.$tagsLimit.val() || '10', 10);
            self.$tagsBoard.html('');
            sortedTags.map(function (tagName, i) {
                if (i > nbTags) {
                    return;
                }
                var $tag = $('<div class="tag-container"><div class="tag uk-badge" data-uk-tooltip="{pos:\'top\'}"' +
                    ' title="Count: ' + self._labelsCounts[tagName].count + '; confidence: ' +
                    (self._labelsCounts[tagName].confidence / self._labelsCounts[tagName].count).toString().slice(0, 6) +
                    '">' + tagName + '</div><span class="add-tag uk-icon-plus-square" data-uk-tooltip="{pos:\'top\'}"' +
                    ' title="Add to video"></span></div>');
                $tag.find('.add-tag').off().click(function () {
                    self._onAddTag(tagName);
                });
                self.$tagsBoard.append($tag);
            });
        }

        self.IMG_PER_ROW = 5;
        self._referencedPages = {};
        self._displayImages = function (loadedWebData) {
            var nbImages = self.$view.find('.image-item').length;
            if (nbImages > 200) {
                return;
            }
            // loadedWebData = [{imgUrl, pageUrl}, ...]
            var i = 0;
            // if (loadedWebData.length > i) {
            for (var i = 0; i < Math.min(loadedWebData.length, 3); i++) {
                if (loadedWebData[i].pageUrl && !self._referencedPages[loadedWebData[i].pageUrl]) {
                    var $img = $('<div class="image-item uk-width-1-5">' +
                        '<a href="' + loadedWebData[i].pageUrl + '" title="' + loadedWebData[i].pageUrl +
                        '" data-uk-tooltip="{pos: \'top\'}"><img src="' + loadedWebData[i].imgUrl + '" /></a></div>');
                    self.$imgsBoard.append($img);
                    self._referencedPages[loadedWebData[i].pageUrl] = true;
                }
                // else {
                //     var $img = $('<div class="image-item uk-width-1-5">' +
                //         '<img src="' + loadedWebData[i].imgUrl + '" /></a></div>');
                // }
            }
        }

        self._clearCanvas = function () {
            self._canvasCtx.clearRect(0, 0, self._canvas.width, self._canvas.height);
        }

        self._faceDetectionConfidence = [];
        self._displayFaceDetectionConfidence = function(faceDetectionConfidence) {
            self._faceDetectionConfidence.push(
                parseInt(faceDetectionConfidence * 10000) / 10000.0);
            self.$view.find('#face-detection-confidence').sparkline(self._faceDetectionConfidence,  {
                type: 'line',
                width: '98%',
                height: '50px'
            });
        }

        self.displayAnnotationRaw = function (data) {
            self._clearCanvas();
            var filename = data.annotation.name;
            var frame = data.frame;
            var loadedWebData = data.loadedWebData;
            var annotation = data.annotation;
            var confidence = 0;
            var msg = (
                "Executing action: displayAnnotationRaw, frame#" + frame +
                " for file:" + filename);
            console.log(msg, annotation);
            self.$detailsBoard.html(msg);
            self.$imageBoard.attr('src', data.preloadUrl);

            if (annotation.face) {
                annotation.face.map(self._displayFace);
                if (annotation.face.length > 0) {
                    confidence = annotation.face.reduce(function (acc, itm) {
                        return acc + itm.detection_confidence
                    }, 0) / annotation.face.length;
                }
                self._displayFaceDetectionConfidence(confidence);
            }
            if (annotation.crop) {
                annotation.crop.map(self._displayCrop);
            }
            if (annotation.labels) {
                self._displayLabels(annotation.labels);
            }
            if (loadedWebData) {
                self._displayImages(loadedWebData);
            }
        }

        self._faceRatios = [];
        self._displayFaceRatio = function(faceRatio) {
            self._faceRatios.push(parseInt(faceRatio * 10000) / 10000.0);
            self.$view.find('#face-ratio').sparkline(self._faceRatios,  {
                type: 'line',
                width: '98%',
                height: '50px'
            });
        }

        // add face detection confidence - compute average face frame ratio (nb frame with face, not accounting for its size)

        self.displayAnnotationPP = function (data) {
            self._clearCanvas();
            var filename = data.annotation.name;
            var frame = data.frame;
            var annotation = data.annotation;
            var msg = (
                "Executing action: displayAnnotationPP, frame#" + frame +
                ", file:" + filename);
            console.log(msg, annotation);
            self.$detailsBoard.html(msg);
            self.$imageBoard.attr('src', data.preloadUrl);

            if (annotation.face) {
                annotation.face.map(self._displayFace);
            }
            if (annotation.crop) {
                annotation.crop.map(self._displayCrop);
            }
            self._displayFaceRatio(annotation.faceRatio || 0);
        }

        self.displayResult = function (data) {
            var msg = "Executing action: displayResult"
            console.log(msg, data);
            self.$detailsBoard.html(msg);
            self.$averageFaceRatio.html(
                '<span style="padding-left: 10px" class="small">Average: </span>' +
                '<span class="uk-badge uk-badge-success">' +
                data.averageFaceRatio.toString().slice(0, 6) + '</span>');
            self.$faceTime.html(
                '<span style="padding-left: 10px" class="small">Face Time: </span>' +
                '<span class="uk-badge uk-badge-success">' +
                data.faceTime.toString() + '</span>' +
                '<span style="padding-left: 10px" class="small">Face Time Proportion: </span>' +
                '<span class="uk-badge uk-badge-success">' +
                data.faceTimeProp.toString().slice(0, 6) + '%</span>');
        }

        self.getActionPreparators = function () {
            return {
                displayFrame: self.prepareDisplayFrame,
                displayAnnotationRaw: self.prepareDisplayAnnotationRaw,
                displayAnnotationPP: self.prepareDisplayAnnotationPP,
                displayResult: self.prepareDisplayResult
            };
        }

        self.getActionExecutors = function () {
            return {
                displayFrame: self.displayFrame,
                displayAnnotationRaw: self.displayAnnotationRaw,
                displayAnnotationPP: self.displayAnnotationPP,
                displayResult: self.displayResult
            };
        }

        self.initialize = function () {
            self.renderView();
            self.events();
            self.reset();
        }

        self.reset = function () {
            self._labelsCounts = {};
            self.$imgsBoard.html('');
            self._referencedPages = {};
            self._faceRatios = [];
            self._faceDetectionConfidence = [];
            self.$averageFaceRatio.html('');
            self.$faceTime.html('');
        }

        self.initialize();
    }

    /*
     * Object tuned in with the analyzer thread, will expect to receive updates of a
     * result object as it is being constructed by the thread and sent over the socket.
     */
    function Analyzer(videoId, $view, thumbnailUrl, callbacks) {
        var self = this;
        var DELAY = 100.0;

        self._socket = null;

        self._visualizer = null;
        self._scheduler = null;
        self._videoId = videoId;

        self._currentFrame = 0;

        callbacks = callbacks || {};
        self._onAddTag = callbacks.onAddTag;

        //reopen the visualizer if it has been closed
        self.reopenVisualizer = function () {
            if (self._visualizer) {
                self._visualizer.show();
            }
        }

        // schedule next available frames for display
        // returns the index right after the last scheduled frame
        self._scheduleNextFrames = function (data) {
            var i = self._currentFrame;
            for (i = self._currentFrame; i <= data.nb_frames; i++) {
                self._scheduler.scheduleNextStep(
                    "display-frame-" + i, 'displayFrame', {frame: i});
            }
            return i;
        }


        self.onmessage = function (message) {
            var data = JSON.parse(message.data);
            if (data.error) {
                return console.error(data.error);
            }

            // we still have unscheduled frames to display
            if (self._currentFrame < data.nb_frames) {
                self._currentFrame = self._scheduleNextFrames(data);
            }
            if (!data.generation_complete) {
                // don't past that point if the generation isn't complete
                // there may be more frames to display that haven't been generated yet
                return;
            }

            // we have scheduled all frames
            // now depending on the data type, schedule the appropriate action

            if (data.data_type === 'annotation_raw') {
                self._scheduler.scheduleNextStep(
                    "display-annotation-" + data.frame_number, 'displayAnnotationRaw', {
                        frame: data.frame_number,
                        annotation: data.data
                    });
            }
            else if (data.data_type === 'annotation') {
                self._scheduler.scheduleNextStep(
                    "display-annotation-pp-" + data.frame_number, 'displayAnnotationPP', {
                        frame: data.frame_number,
                        annotation: data.data
                    });
            }
            if (data.data_type === 'aggregation') {
                self._scheduler.scheduleNextStep(
                    'display-result', 'displayResult', data.data);
            }

        }

        self.events = function() {

        };

        self._onClickForward = function () {
            self._visualizer.updateDelay(self._scheduler.speedDown());
        }

        self._onClickBackward = function () {
            self._visualizer.updateDelay(self._scheduler.speedUp());
        }

        self._onClickPlay = function () {
            self._scheduler.play();
        }

        self._onClickPause = function () {
            self._scheduler.pause();
        }

        self.initialize = function() {
            self._visualizer = new Visualizer($view, thumbnailUrl, self._videoId, {
                onClickPause: self._onClickPause,
                onClickPlay: self._onClickPlay,
                onClickForward: self._onClickForward,
                onClickBackward: self._onClickBackward,
                onAddTag: self._onAddTag,
                initialDelay: DELAY
            });
            self._scheduler = new Scheduler(self._visualizer, {
                delay: DELAY
            });

            self._socket = new WebSocket('ws://localhost:666/subscribe/video/analyze');
            self._socket.onopen = self.onopen;
            self._socket.onclose = self.onclose;
            self._socket.onmessage = self.onmessage;

            self.events();
        };


        self.send = function(message) {
            self._socket.send(JSON.stringify(message));
        }

        self.onopen = function () {
            // send request
            self.send({
                action: 'gcv',
                videoId: videoId
            });
            self._scheduler.play();
        }

        self.onclose = function () {
            console.log("Connection closed");
        }


        self.initialize();
    }

    window.Analyzer = Analyzer;
});