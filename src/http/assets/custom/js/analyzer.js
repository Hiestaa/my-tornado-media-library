
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
    var EXTENDED_FACE_FRAME_COLOR = '#FF3000';
    var CROP_FRAME_COLOR = '#00C4E1';
    function Visualizer($view, thumbnail, videoId, options) {
        var self = this;

        self.$view = $view;

        options = options || {};
        self._onClickPlay = options.onClickPlay || function () {};
        self._onClickPause = options.onClickPause || function () {};
        self._onClickForward = options.onClickForward || function () {};
        self._onClickBackward = options.onClickBackward || function () {};
        self._onClickStep = options.onClickStep || function () {};
        self._onClickReverse = options.onClickReverse || function () {};
        self._onClickInterrupt = options.onClickInterrupt || function () {};
        self._onClickCleanup = options.onClickCleanup || function () {};
        self._onAddTag = options.onAddTag || function () {};
        self._initialDelay = options.initialDelay || 1000.0 / 12.0;
        self._onGoToStepId = options.onGoToStepId || function () {};
        self._initialThumbnail = thumbnail;

        self._template = '\
<div id="analyze-modal" class="uk-modal">\
    <div class="uk-modal-dialog large">\
        <button type="button" class="uk-modal-close uk-close"/>\
        <h1 class="uk-modal-header">\
            <span id="title">Analyze in progress...</span>\
            <div class="uk-panel-badge">\
                <button class="uk-button uk-button-warning" id="interrupt" title="Interrupt and close the modal" data-uk-tooltip="{pos: \'top-right\'}">Interrupt</button>\
                <button class="uk-button uk-button-danger hidden" id="clean-up" title="Clean-up generated images and close the modal data-uk-tooltip="{pos: \'top-right\'}">Clean-up</button>\
            </div>\
        </h1>\
        <p>A visualization of the progress of the analysis will appear below.</p>\
        <div id="board-container">\
            <!-- If the annotations are off, it may be that these dimensions are not matching the ones defined in the config -->\
            <img class="default-size" id="image-board" src="{{thumbnail}}"></img>\
            <canvas width="800" height="450" id="image-board-canvas"></canvas>\
            <canvas width="800" height="450" id="canvas-board"></canvas>\
            <span class="status row-0 left underline">#<span id="frame"></span></span>\
            <span class="status row-0 right" id="reverse"><i class="uk-icon-history"></i></span>\
            <span class="status row-1 center-left" id="step-reverse"><i class="uk-icon-step-backward"></i></span>\
            <span class="status row-1 center" id="pause"><i class="uk-icon-pause"></i></span>\
            <span class="status row-1 center hidden" id="play"><i class="uk-icon-play"></i></span>\
            <span class="status row-1 center-right" id="step"><i class="uk-icon-step-forward"></i></span>\
            <span class="status row-1 left" id="forward"><i class="uk-icon-backward"></i></span>\
            <span class="status row-1 right" id="backward"><i class="uk-icon-forward"></i></span>\
            <span class="status row-2 center large"><i class="uk-icon-clock-o"></i><span id="delay">{{delay}}</span><span id="overtime"></span></span>\
        </div>\
        <hr>\
        <h3>Computed Properties</h3>\
        <div id="computed-properties">\
            <h4>Detection Confidence<span id="average-face-time-ratio"></span></h4>\
            <div id="face-detection-confidence"></div>\
            <h4>Face Ratio<span id="average-face-ratio"></span></h4>\
            <div id="face-ratio"></div>\
        </div>\
        <div class="uk-modal-footer">\
            <h3>More details...</h3>\
            <pre id="details-board"></pre>\
        </div>\
    </div>\
</div>';

        self._imageCanvas = null;
        self._imageCanvasCtx = null;
        self.$imageBoard = null;
        self.$detailsBoard = null
        self._canvas = null;
        self._canvasCtx = null;
        self.$tagsBoard = null;
        self.$tagsLimit = null;
        self.$averageFaceRatio = null;
        self.$faceTime = null;
        self._videoId = videoId;

        // called by the scheduler when the execution of an action took longer than the time between two actions
        self._overtimeHideTimeout = null;
        self.notifyOvertime = function(duration) {
            if (self._overtimeHideTimeout) { clearTimeout(self._overtimeHideTimeout); }
            if (duration) {
                self.$overtime.text('(' + duration + ')').removeClass('hidden');
            }
            else {
                self._overtimeHideTimeout = setTimeout(function () {
                    self.$overtime.text('').addClass('hidden');
                }, 5000);
            }
        }

        self.notifyComplete = function () {
            self.$view.find('#interrupt').addClass('hidden');
            self.$view.find('#clean-up').removeClass('hidden');
            self.$view.find('#title').text('Analysis complete!');
        }

        self.renderView = function () {
            self.$view.html(render(self._template, {
                thumbnail: thumbnail,
                delay: self._initialDelay
            }));
            self.$imageBoard = self.$view.find('#image-board');
            self._imageCanvas = document.getElementById('image-board-canvas');
            self._imageCanvasCtx = self._imageCanvas.getContext('2d');
            self.$detailsBoard = self.$view.find('#details-board');
            self._canvas = document.getElementById('canvas-board');
            self._canvasCtx = self._canvas.getContext('2d');
            self.$computedProperties = self.$view.find('#computed-properties');
            self.$delay = self.$view.find('#delay');
            self.$frame = self.$view.find('#frame');
            self.$overtime = self.$view.find('#overtime');
            self.$averageFaceRatio = self.$view.find('#average-face-ratio');
            self.$faceTime = self.$view.find('#average-face-time-ratio');
            self.show();
        }

        self.doPause = function () {
            self.$view.find("#board-container #pause").addClass('hidden');
            self.$view.find("#board-container #play").removeClass('hidden');
            self._onClickPause();
        }

        self.events = function () {
            self.$view.find("#board-container #pause").click(self.doPause);
            self.$view.find("#board-container #play").click(function () {
                self.$view.find("#board-container #pause").removeClass('hidden');
                self.$view.find("#board-container #play").addClass('hidden');
                self._onClickPlay();
            });
            self.$view.find("#board-container #forward").click(function () {
                self._onClickForward();
            });
            self.$view.find("#board-container #backward").click(function () {
                self._onClickBackward();
            });
            self.$view.find("#board-container #reverse").click(function () {
                self.$view.find('#board-container #reverse').toggleClass('underline');
                self._onClickReverse();
            });
            self.$view.find("#board-container #step").click(function () {
                self._onClickStep();
            });
            self.$view.find("#board-container #step-reverse").click(function () {
                self._onClickStep(true);
            });
            self.$view.find('#tags-limit').change(function () {
                self._displayLabels();
            });
            self.$view.find('#clean-up').click(function () {
                self.doPause();
                self._onClickCleanup();
            });
            self.$view.find('#interrupt').click(function () {
                self._onClickInterrupt();
                self.$view.find('#interrupt').addClass('hidden');
                self.$view.find('#clean-up').removeClass('hidden');
                self.$view.find('#title').text('Analysis interrupted.');
            });
        }

        self.updateDelay = function (value) {
            self.$view.find('#delay').text(value.toString().slice(0, 5));
        }

        self.show = function () {
            var dialog = $.UIkit.modal('#analyze-modal');
            if (!dialog.isActive())
                dialog.show();
        }

        self.hide = function () {
            var dialog = $.UIkit.modal('#analyze-modal');
            if (dialog) { dialog.hide(); }
        }

        self.prepareDisplayFrame = function (data, done) {
            var t = Date.now();
            data.preloadUrl = '/download/minivid/' + self._videoId + '/' + data.frame
            preloadPictureBatched(data.preloadUrl, function (image) {
                data._preloadDuration = Date.now() - t;
                data.preloadImage = image;
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
            var pictures = (webData.full_matching_images || []).map(function(img) { return img.url; });
            preloadPictures(pictures, function () {
                if (stopped) {
                    return;
                }
                stopped = true
                done(pictures.map(function (url, idx) {
                    if ((webData.pages_with_matching_images || []).length > idx) {
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
            preloadPictureBatched(data.preloadUrl, function (image) {
                data._preloadDuration = Date.now() - t;
                data.preloadImage = image;
                done(data);
                // gcv stuff - don't care anymore?
                // self._tryLoad(data.annotation.web || {}, function (loadedWebData) {
                //     data.loadedWebData = loadedWebData;
                //     // if (loadedWebData.length != data.annotation.web.full_matching_images.length) { debugger; }
                //     done(data);
                // })
            });
        }

        self.prepareDisplayAnnotationPP = function (data, done) {
            var t = Date.now();
            data.preloadUrl = '/download/minivid/' + self._videoId + '/' + data.frame
            preloadPictureBatched(data.preloadUrl, function (image) {
                data._preloadDuration = Date.now() - t;
                data.preloadImage = image;
                done(data);
            });
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
            // console.log(msg, data);
            self.$detailsBoard.html(msg);
            self._imageCanvasCtx.drawImage(data.preloadImage, 0, 0);
            self.$frame.text(frame)
        }

        self._displayLandmark = function (landmark) {
            var RADIUS = 1;
            self._canvasCtx.beginPath();
            self._canvasCtx.arc(landmark.x, landmark.y, RADIUS, 0, 2 * Math.PI, false);
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
            var bounds = [
                faceData.boundaries[0].x,
                faceData.boundaries[0].y,
                faceData.boundaries[1].x,
                faceData.boundaries[1].y
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

            // early abord if we have no landmarks - two other frames are landmark based.
            if (faceData.landmarks.length === 0) { return; }

            faceData.landmarks.map(function (landmark) {
                if (minPosY == -1 || landmark.y < minPosY) {
                    minPosY = landmark.y;
                }
                if (minPosX == -1 || landmark.x < minPosX) {
                    minPosX = landmark.x;
                }
                if (maxPosY == -1 || landmark.y > maxPosY) {
                    maxPosY = landmark.y;
                }
                if (maxPosX == -1 || landmark.x > maxPosX) {
                    maxPosX = landmark.x;
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
                Math.min(minPosX, faceData.boundaries[0].x),
                Math.min(minPosY, faceData.boundaries[0].y),
                Math.max(maxPosX, faceData.boundaries[1].x),
                Math.max(maxPosY, faceData.boundaries[1].y)
            ];
            self._canvasCtx.beginPath();
            self._canvasCtx.rect(
                bounds[0] - MARGIN,
                bounds[1] - MARGIN,
                bounds[2] - bounds[0] + MARGIN,
                bounds[3] - bounds[1] + MARGIN);
            self._canvasCtx.lineWidth = 1;
            self._canvasCtx.strokeStyle = FACE_FRAME_COLOR;
            self._canvasCtx.stroke();
        }

        self._displayCrop = function (cropData) {
            var bounds = [
                cropData.boundaries[0].x,
                cropData.boundaries[0].y,
                cropData.boundaries[1].x,
                cropData.boundaries[1].y
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

            // create the tags board only if necessary
            if (self.sortedTags.length > 0 && !self.$tagsBoard) {
                self.$computedProperties.append('\
                    <hr>\
                    <h3>Suggested Tags<input style="float: right" type="number" id="tags-limit" value="30" /></h3>\
                    <div id="tags-board">\
                    </div>'
                );
                self.$tagsBoard = self.$computedProperties.find('#tags-board');
                self.$tagsLimit = self.$view.find('#tags-limit');
            }

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

            if (loadedWebData && loadedWebData.length && !self.$imgsBoard) {
                self.$computedProperties.append('\
                    <hr>\
                    <h3>Related Images</h3>\
                    <div id="imgs-board" class="uk-grid">\
                    </div>\
                ');
                self.$imgsBoard = self.$view.find('#imgs-board');
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


        self._sparklineRegionChangeTimeout = null;
        self._onSparklineRegionChange = function (ev, frameToStepId) {
            var sparkline = ev.sparklines[0];
            var region = sparkline.getCurrentRegionFields();
            if (region.x === undefined) { return; }
            if (self._sparklineRegionChangeTimeout) { clearTimeout(self._sparklineRegionChangeTimeout); }

            // add a delay to the call to this event, as swift move over the sparkline
            // would generate a large number of events
            // this is a way to 'debounce' the events while only retaining
            // the last call (rather than the first)
            self._sparklineRegionChangeTimeout = setTimeout(function () {
                self._onGoToStepId(frameToStepId[region.x]);
            }, 2);
        }

        self._faceDetectionConfidence = [];
        self._faceDetectionFrameToStepId = {};
        self._displayFaceDetectionConfidence = function(frame, faceDetectionConfidence, stepId) {
            faceDetectionConfidence = parseInt(faceDetectionConfidence * 10000) / 10000.0;
            if (frame < self._faceDetectionConfidence.length &&
                self._faceDetectionConfidence[frame] == faceDetectionConfidence) { return; }

            while (frame >= self._faceDetectionConfidence.length) {
                self._faceDetectionConfidence.push(0);
            }
            self._faceDetectionConfidence[frame] = faceDetectionConfidence;
            self._faceDetectionFrameToStepId[frame] = stepId;
            self.$view.find('#face-detection-confidence').sparkline(self._faceDetectionConfidence, {
                type: 'line',
                width: '98%',
                height: '50px'
            });
            self.$view.find('#face-detection-confidence').bind(
                'sparklineRegionChange',
                (ev) => self._onSparklineRegionChange(ev, self._faceDetectionFrameToStepId));
        }

        self.displayAnnotationRaw = function (data, stepId) {
            self._clearCanvas();
            var filename = data.annotation.name;
            var frame = data.frame;
            self.$frame.text(frame)
            var loadedWebData = data.loadedWebData;
            var annotation = data.annotation;
            var confidence = 0;
            var msg = (
                "Executing action: displayAnnotationRaw, frame#" + frame +
                " for file:" + filename);
            // console.log(msg, annotation);
            self.$detailsBoard.html(msg);
            self._imageCanvasCtx.drawImage(data.preloadImage, 0, 0);

            if (annotation.faces) {
                annotation.faces.map(self._displayFace);
                if (annotation.faces.length > 0) {
                    confidence = annotation.faces.reduce(function (acc, itm) {
                        return acc + itm.detection_confidence
                    }, 0) / annotation.faces.length;
                }
                self._displayFaceDetectionConfidence(frame, confidence, stepId);
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
        self._faceRatioFrameToStepId = {};
        self._displayFaceRatio = function(frame, faceRatio, stepId) {
            faceRatio = parseInt(faceRatio * 10000) / 10000.0;
            if (frame < self._faceRatios.length && self._faceRatios[frame] == faceRatio) { return; }

            while (frame >= self._faceRatios.length) {
                self._faceRatios.push(0);
            }
            self._faceRatios[frame] = faceRatio
            self._faceRatioFrameToStepId[frame] = stepId;
            self.$view.find('#face-ratio').sparkline(self._faceRatios,  {
                type: 'line',
                width: '98%',
                height: '50px'
            });
            self.$view.find('#face-ratio').bind(
                'sparklineRegionChange',
                (ev) => self._onSparklineRegionChange(ev, self._faceRatioFrameToStepId));

        }

        // add face detection confidence - compute average face frame ratio (nb frame with face, not accounting for its size)

        self.displayAnnotationPP = function (data, stepId) {
            self._clearCanvas();
            var filename = data.annotation.name;
            var frame = data.frame;
            self.$frame.text(frame)
            var annotation = data.annotation;
            var msg = (
                "Executing action: displayAnnotationPP, frame#" + frame +
                ", file:" + filename);
            // console.log(msg, annotation);
            self.$detailsBoard.html(msg);
            self._imageCanvasCtx.drawImage(data.preloadImage, 0, 0);

            if (annotation.faces) {
                annotation.faces.map(self._displayFace);
            }
            if (annotation.crop) {
                annotation.crop.map(self._displayCrop);
            }
            self._displayFaceRatio(frame, annotation.faceRatio || 0, stepId);
        }

        self.displayResult = function (data) {
            var msg = "Executing action: displayResult"
            // console.log(msg, data);
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
            if (self.$imgsBoard) {
                self.$imgsBoard.html('');
            }
            self._referencedPages = {};
            self._faceRatios = [];
            self._faceDetectionConfidence = [];
            self.$averageFaceRatio.html('');
            self.$view.find('#face-ratio').html();
            self.$view.find('#face-detection-confidence').html();
            self.$faceTime.html('');
            self.$view.find('#interrupt').removeClass('hidden');
            self.$view.find('#clean-up').addClass('hidden');
            self.$view.find("#board-container #pause").removeClass('hidden');
            self.$view.find("#board-container #play").addClass('hidden');
            self.$view.find('#title').text('Analysis in progress...');
            self.$imageBoard.attr('src', self._initialThumbnail);
            self._imageCanvasCtx.clearRect(0, 0, self._imageCanvas.width, self._imageCanvas.height);
            self.$view.find('#board-container #step-reverse').removeClass('hover');
            self.$frame.text(0)
        }

        self.initialize();
    }

    /*
     * Object tuned in with the analyzer thread, will expect to receive updates of a
     * result object as it is being constructed by the thread and sent over the socket.
     */
    function Analyzer(videoId, $view, {thumbnail, force}, callbacks) {
        var self = this;
        var DELAY = 100.0;

        self._socket = null;

        self._visualizer = null;
        self._scheduler = null;
        self._videoId = videoId;
        self._thumbnailUrl = thumbnail;
        self._force = force || false;
        self._restartOnReopen = false;
        self._connectionInterrupted = false;

        self._currentFrame = 0;

        callbacks = callbacks || {};
        self._onAddTag = callbacks.onAddTag;

        self.reopenConnection = function () {
            self._connectionInterrupted = false;
            self._socket = new WebSocket('ws://localhost:666/subscribe/video/analyze');
            self._socket.onopen = self.onopen;
            self._socket.onclose = self.onclose;
            self._socket.onmessage = self.onmessage;
        }

        self.start = function () {
            self._scheduler.reset();
            self._visualizer.reset();
            self._currentFrame = 0;
            self._restartOnReopen = false;

            if (self._connectionInterrupted) {
                self.reopenConnection();
            }
            else {
                self.send({
                    action: 'start',
                    videoId: self._videoId,
                    force: self._force
                });

            }
            self._scheduler.play();
        }

        //reopen the visualizer if it has been closed
        self.reopenVisualizer = function () {
            if (self._visualizer) {
                self._visualizer.show();
                if (self._connectionInterrupted) {
                    self.reopenConnection();
                }
                // no need to call 'start' if reopening the connection:
                // it is done automatically when the conenction is established
                else if (self._restartOnReopen) {
                    self.start();
                }
            }
        }

        // schedule next available frames for display
        // returns the index right after the last scheduled frame
        self._scheduleNextFrames = function (data) {
            var i = self._currentFrame;
            for (i = self._currentFrame; i < data.nb_frames; i++) {
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
            // if the generation is complete tho (might have been already when starting the analysis),
            // let's display the analysis progress
            if (!data.generation_complete) {
                if (self._currentFrame < data.nb_frames && data.data_type === 'frame') {
                    self._currentFrame = self._scheduleNextFrames(data);
                }
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
                self._visualizer.notifyComplete();
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

        self._onClickReverse = function () {
            self._scheduler.reverse();
        }

        self._onClickStep = function (reverse) {
            self._scheduler.step(reverse);
        }

        self._onGoToStepId = function (stepId) {
            self._scheduler.goto(stepId);
        }

        self._onClickInterrupt = function () {
            self.send({
                action: 'stop'
            });
        }

        self._onClickCleanup = function () {
            self.send({
                action: 'clean-up',
                videoId: self._videoId
            });
            self._restartOnReopen = true;
            self._visualizer.hide();
        }

        self.initialize = function() {
            self._visualizer = new Visualizer($view, self._thumbnailUrl, self._videoId, {
                onClickPause: self._onClickPause,
                onClickPlay: self._onClickPlay,
                onClickForward: self._onClickForward,
                onClickBackward: self._onClickBackward,
                onAddTag: self._onAddTag,
                onClickReverse: self._onClickReverse,
                onClickStep: self._onClickStep,
                initialDelay: DELAY,
                onGoToStepId: self._onGoToStepId,
                onClickInterrupt: self._onClickInterrupt,
                onClickCleanup: self._onClickCleanup
            });
            self._scheduler = new Scheduler(self._visualizer, {
                delay: DELAY
            });

            self.reopenConnection();
            self.events();
        };


        self.send = function(message) {
            self._socket.send(JSON.stringify(message));
        }

        self.onopen = function () {
            // start right away
            self.start();
        }

        self.onclose = function () {
            $.UIkit.notify("Connection interrupted - close and re-open the analysis model to attempt re-connecting.", {status:'warning'});
            self._connectionInterrupted = true;
        }


        self.initialize();
    }

    window.Analyzer = Analyzer;
});