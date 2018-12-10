$(function () {
    function BooleanOption($container, name, title, options) {
        var self = this;
        self.template = '\
            <div class="uk-button-group properties-item compile-option">\
                <label>{{title}}</label>\
                <button class="uk-button uk-button-success {{active}}" id="sender"><i class="uk-icon-toggle-{{toggle}}"></i><span>{{title}}<span></button>\
            </div>';
        self.$view = $(render(self.template, {
            name: name,
            title: title,
            active: options.disabled ? '' : 'uk-active',
            toggle: options.disabled ? 'off' : 'on'
        }));
        $container.append(self.$view);
        self.$view.find('#sender').click(function () {
            $(this).toggleClass('uk-active');
            if ($(this).hasClass('uk-active')) {
                $(this).find('i').addClass('uk-icon-toggle-on').removeClass('uk-icon-toggle-off');
            }
            else {
                $(this).find('i').removeClass('uk-icon-toggle-on').addClass('uk-icon-toggle-off');
            }
        })
        self.isActive = function () {
            return self.$view.find('#sender').hasClass('uk-active');
        }
        self.getValue = function () {
            self.isActive();
        }
    }
    function SelectizeOption($container, name, title, options) {
        var self = this;
        self.template = '\
            <div class="uk-button-group properties-item">\
                <label for="selectize-{{name}}">{{title}}</label>\
                <button class="uk-button uk-button-success {{active}}" id="sender"><i class="uk-icon-toggle-{{toggle}}"></i></button>\
                <select id="selectize-{{name}}"><select>\
            </div>';
        self.optionTemplate = '\
            <option value="{{val}}">{{display}}</option>';
        self.values = options.values;
        self.formatter = options.formatter || function (v) { return v };
        self.$view = $(render(self.template, {
            name: name,
            title: title,
            active: options.disabled ? '' : 'uk-active',
            toggle: options.disabled ? 'off' : 'on'
        }));
        $container.append(self.$view);
        for (var i = 0; i < self.values.length; i++) {
            self.$view.find('#selectize-' + name).append(render(self.optionTemplate, {
                val: self.values[i],
                display: self.formatter(self.values[i])
            }));
        };
        self.$view.find('#selectize-' + name).selectize({
            onDropdownOpen: function ($dropdown) {
                var height = 265;
                if ($dropdown.children().children().length < 8)
                    height = 65 + 25 * $dropdown.children().children().length
                $container.parent().attr('style', 'height: ' + height + 'px !important');
            },
            onDropdownClose: function () {
                $container.parent().attr('style', 'height: 0');
            },
            create: true
        });
        self.$view.find('#sender').click(function () {
            $(this).toggleClass('uk-active');
            if ($(this).hasClass('uk-active')) {
                $(this).find('i').addClass('uk-icon-toggle-on').removeClass('uk-icon-toggle-off');
            }
            else {
                $(this).find('i').removeClass('uk-icon-toggle-on').addClass('uk-icon-toggle-off');
            }
        })

        self.getValue = function () {
            return self.$view.find('#selectize-' + name).val();
        }
        self.isActive = function () {
            return self.$view.find('#sender').hasClass('uk-active');
        }
    }
    function CustomSliderOption($container, name, title, options) {
        var self = this;
        self.template = '\
            <div class="uk-button-group properties-item">\
                <label for="slider-{{name}}">{{title}}</label>\
                <button class="uk-button uk-button-success {{active}}" id="sender"><i class="uk-icon-toggle-{{toggle}}"></i></button>\
                <div class="slider" id="slider-{{name}}" title="{{titleVal}}" data-uk-tooltip="{cls: \'tooltip-{{name}}\', pos:\'top\'}">\
                    <span class="slider-handle">\
                </div>\
            </div>';
        self.name = name;
        self._isActive = false;
        self.initialX = 0;
        self.barL = 0;
        options = options || {};
        self.minVal = options.min || 0;
        self.maxVal = options.max || 100;
        self.initVal = options.val || 0;
        self.formatter = options.formatter || function (v) { return v; };
        self.currentX = 0;
        self.$view = $(render(self.template, {
            name: name,
            title: title,
            titleVal: self.formatter(self.initVal),
            active: options.disabled ? '' : 'uk-active',
            toggle: options.disabled ? 'off' : 'on'
        }));
        $container.append(self.$view);
        self.handler = self.$view.find('.slider-handle');

        self._valToX = function (val) {
            // transform to percentage
            var pc = val / (self.maxVal - self.minVal);
            pc = Math.max(0, Math.min(pc, 1));
            // transform to x
            return pc * self.barL;
        }
        self._XToVal = function (x) {
            // get progress
            var progress = Math.max(0, x);
            // transform to percentage
            var pc = progress / self.barL;
            // transform in min/max space
            return parseInt(self.minVal + pc * (options,self.maxVal - self.minVal));
        };
        self._clamp = function (val) {
            return Math.max(-1, Math.min(self.barL, val));
        };
        self._update = function (posX) {
            self.currentX = self._clamp(posX - 6 - self.initialX + 1);
            self.handler.css('transform', 'translateX(' + self.currentX + 'px)');
            $('.tooltip-' + self.name).html(self.formatter(self._XToVal(self.currentX)));
        }
        self._events = function () {

            self.$view.find('#sender').click(function () {
                $(this).toggleClass('uk-active');
                if ($(this).hasClass('uk-active')) {
                    $(this).find('i').addClass('uk-icon-toggle-on').removeClass('uk-icon-toggle-off');
                }
                else {
                    $(this).find('i').removeClass('uk-icon-toggle-on').addClass('uk-icon-toggle-off');
                }
            });
            self.handler.on('mousedown', function (e) {
                self._isActive = true;
                // in the case where the initial X has not be set set it now
                // (this is most likely to be due to a hidden container that has no position in the flow)
                if (!self.initialX) {
                }
            });
            $container.on('mousemove', function (e) {
                if (self._isActive) {
                    self._update(e.pageX);
                    if ($('.tooltip-' + self.name).css('display') == 'none')
                        $('.tooltip-' + self.name).css('display', 'block')
                }
            }).on('mouseup', function (e) {
                self._isActive = false;
            });
            self.handler.parent().on('mousedown', function (e) {
                self._isActive = true;
                self._update(e.pageX);
            });
        };
        self.getValue = function () {
            return self._XToVal(self.currentX);
        }
        self.isActive = function () {
            return self.$view.find('#sender').hasClass('uk-active');
        }

        if (!self.initialX)
            self.initialX = self.handler.parent().offset().left;
        if (!self.barL)
            self.barL = self.handler.parent().width() - 6;
        if (!self.currentX) {
            self.currentX = self._valToX(self.initVal || 0) - 6;
            self.handler.css('transform', 'translateX(' + self.currentX + 'px)');
        }

        self._events();
        return self;
    }
    function TextOption($container, name, title, inputType) {
        var self = this;
        self.template = '\
            <div class="uk-button-group properties-item">\
                <form class="uk-form">\
                    <button class="uk-button uk-button-success {{active}}" id="sender"><i class="uk-icon-toggle-{{toggle}}"></i></button>\
                    <input type="{{inputType}}" id="{{name}}-value" style="width: 210px;">\
                </form>\
            </div>';
        self.$view = $(render(self.template, {
            name: name,
            title: title,
            inputType: inputType,
            active: options.disabled ? '' : 'uk-active',
            toggle: options.disabled ? 'off' : 'on'
        }));
        $container.append(self.$view);
        self.$view.find('#sender').click(function () {
            $(this).toggleClass('uk-active');
            if ($(this).hasClass('uk-active')) {
                $(this).find('i').addClass('uk-icon-toggle-on').removeClass('uk-icon-toggle-off');
            }
            else {
                $(this).find('i').removeClass('uk-icon-toggle-on').addClass('uk-icon-toggle-off');
            }
        });

        self.getValue = function () {
            return self.$view.find('#' + name + '-value').val();
        }
        self.isActive = function () {
            return self.$view.find('#sender').hasClass('uk-active');
        }
        return self;
    }
    function OptionsManager($container) {
        var self = this;

        self._options = {};
        self.$container = $container;

        self.addTimeSlider = function (name, title, bounds, disabled) {
            var formatter = function (v) {
                return (parseInt(v / 60)) + ' min, ' + v % 60 +' s';
            }

            self._options[name] = new CustomSliderOption(
                self.$container, name, title, {
                    min: bounds[0],
                    val: bounds[1],
                    max: bounds[2],
                    formatter: formatter,
                    disabled: !!disabled
                });

        }

        self.addIntegerSlider = function (name, title, bounds, disabled) {
            var formatter = function (v) {
                return v;
            }

            self._options[name] = new CustomSliderOption(
                self.$container, name, title, {
                    min: bounds[0],
                    val: bounds[1],
                    max: bounds[2],
                    formatter: formatter,
                    disabled: !!disabled
                });

        }

        self.addSelectizeOption = function (name, title, values, disabled, displayText) {
            self._options[name] = new SelectizeOption(
                self.$container, name, title, {
                    values: values,
                    formatter: function(v) {
                        return displayText ? displayText[v] : v[0].toUpperCase() + v.slice(1);
                    },
                    disabled: !!disabled
                }
            );
        }

        self.addBooleanOption = function (name, title, disabled) {
            self._options[name] = new BooleanOption(
                self.$container, name, title, {
                    disabled: !!disabled
                }
            );
        }

        self.render = function() {
            self.addTimeSlider('duration', "Expected Duration:", [120, 600, 3600]);
            self.addTimeSlider('minSegmentLength', "Min Segment Duration:", [5, 60, 300]);
            self.addTimeSlider('maxSegmentLength', "Max Segment Duration:", [10, 120, 1200]);
            self.addTimeSlider('fadeDuration', "Fade In/Out Duration:", [1, 5, 60]);
            self.addTimeSlider('crossfadeDuration', "CrossFade Duration:", [1, 30, 60]);
            self.addIntegerSlider('segmentLimit', "Max Nb. Segment:", [1, 3, 10], true);
            self.addSelectizeOption('strategy', "Selection Strategy:", [
                'random'
            ]);
            self.addSelectizeOption('reorder', "Reorder Segments:", [
                'original',
                'durationAsc',
                'durationDesc',
                'video'
            ], false, {
                'original': 'Original Order',
                'durationAsc': 'Duration (asc)',
                'durationDesc': 'Duration (desc)',
                'video': 'Order by video'
            });
            self.addBooleanOption('hardLimits', 'Hard Limits', true);
        }

        self.getValues = function() {
            return Object.keys(self._options).reduce(function(acc, name) {
                if (self._options[name].isActive()) {
                    acc[name] = self._options[name].getValue();
                }
                return acc;
            }, {});
        }

        self.render();
    }

    function SegmentsVisualizer($view, $logs, coverflowDivId) {
        var self = this;

        self.$view = $view;
        self.$logs = $logs;
        self.$refresh = self.$view.find('.refresh');
        self._segmentsPlaylist = [];
        self._segmentsViewOutOfDate = 0;

        self._coverflow = function() {
            self.$view.find('#' + coverflowDivId).html('');
            self.$view.find('#' + coverflowDivId).coverflow({
                flash: '/assets/js-cover-flow/coverflow.swf',
                playlist: self._segmentsPlaylist,
                width: 'auto',
                height: 500,  // also update compiler.css:#visualization #candidates-section
                backgroundopacity: 0,
                coverwidth: 480
            });
            self.$refresh.find('#content').text('');
        }

        self.prepare = function(data, done) {
            var t = Date.now();
            data.preloadUrls = [];
            for (var i = data.data.startMinividFrame; i < data.data.startMinividFrame + 1; i++) {
                data.preloadUrls.push('/download/minivid/' + data.data.videoId + '/' + i);
            }
            preloadPictures(data.preloadUrls, function () {
                data._preloadDuration = Date.now() - t;
                done(data);
            });
        }

        self.addSegment = function(data) {
            self._segmentsPlaylist.push({
                title: 'minivid/' + data.data.startMinividFrame + ' -> minivid/' + data.data.endMinividFrame,
                description: data.file,
                file: data.file,
                image: data.preloadUrls[0],  // TODO: find a way to cycle segments belonging to the same files here on hover
                link: '/videoplayer/' + data.data.videoId
            });
            self._segmentsViewOutOfDate += 1;
            self.$refresh.find('#content').text(self._segmentsViewOutOfDate);
            return self._segmentsPlaylist;
        }

        self.getLastSegment = function() {
            if (self._segmentsPlaylist.length > 0)
                return self._segmentsPlaylist[self._segmentsPlaylist.length - 1]
            return null
        }

        self.execute = function(data) {
            var dur = data.duration.toString().substring(0, 8);
            var msg = (
                '[' + data.dataType + '][t=' + dur + '][file=' + data.file +
                '] ' + data.step + ': minivid/' + data.data.startMinividFrame +
                ' -> minvid/' + data.data.endMinividFrame);
            console.log(msg, data.data);
            self.$logs.append(msg + '<br>');
        }

        self._onRefresh = function() {
            self._segmentViewOutOfDate = 0;
            self._coverflow();
        }

        self.$refresh.click(self._onRefresh);
    }
    function CandidateSegmentsVisualizer($view, $logs) {
        var self = this;

        self.segmentsVisualizer = new SegmentsVisualizer($view, $logs, 'coverflow-candidates');

        self.prepare = function(data, done) {
            return self.segmentsVisualizer.prepare(data, done);
        }

        self._lastSegmentCandidateFile = null;
        self._nbSegmentCandidatesPerVideo = {};
        self._updateSegmentCandidatesPlaylist = function(data) {
            self._nbSegmentCandidatesPerVideo[data.file] = (self._nbSegmentCandidatesPerVideo[data.file] || 0) + 1;
            var prevItem = self.segmentsVisualizer.getLastSegment();
            if (prevItem) {
                prevItem.description = prevItem.file + ' (' + (self._nbSegmentCandidatesPerVideo[prevItem.file] || 0) + ' segments)';
            }
            if (self._lastSegmentCandidateFile != data.file) {
                self._lastSegmentCandidateFile = data.file;
                self.segmentsVisualizer.addSegment(data);
            }
        }


        self.execute = function(data) {
            self._updateSegmentCandidatesPlaylist(data);
            self.segmentsVisualizer.execute(data);
        }
    }
    function SelectedSegmentsVisualizer($view, $logs) {
        var self = this;

        self.segmentsVisualizer = new SegmentsVisualizer($view, $logs, 'coverflow-selected');

        self.prepare = function(data, done) {
            return self.segmentsVisualizer.prepare(data, done);
        }

        self.execute = function(data) {
            self.segmentsVisualizer.addSegment(data);
            self.segmentsVisualizer.execute(data);
        }
    }
    function Visualizer($view, options) {
        var self = this;

        options = options || {};
        self._initialDelay = options.initialDelay || 1000.0 / 12.0;
        self.$view = $view;
        self.$logs = self.$view.find('#compilation-logs');

        self._candidateSegmentsVisualizer = new CandidateSegmentsVisualizer(
            self.$view.find('#candidates-section'),
            self.$logs);

        self._selectedSegmentsVisualizer = new SelectedSegmentsVisualizer(
            self.$view.find('#selected-section'),
            self.$logs);


        self.prepareDisplayRaw = function (data, done) {
            return done(data);
        }

        self.displayRaw = function (data) {
            var dur = data.duration.toString().substring(0, 8);
            var msg = '[' + data.dataType + '][t=' + dur + '][file=' + data.file + '] ' + data.step;
            console.log(msg, data.data);
            self.$logs.append(msg + '<br>');
        }

        self.getActionPreparators = function () {
            return {
                init: self.prepareDisplayRaw,
                segment_candidate: self._candidateSegmentsVisualizer.prepare,
                segment_select: self._selectedSegmentsVisualizer.prepare,
                segment_compiled: self.prepareDisplayRaw,
                result: self.prepareDisplayRaw,
            };
        }

        self.getActionExecutors = function () {
            return {
                init: self.displayRaw,
                segment_candidate: self._candidateSegmentsVisualizer.execute,
                segment_select: function(data) {
                    self._selectedSegmentsVisualizer.execute(data);
                },
                segment_compiled: self.displayRaw,
                result: function(data) {
                    // update coverflows with data that may not have been rendered yet
                    self._candidateSegmentsVisualizer.segmentsVisualizer._coverflow()
                    self._selectedSegmentsVisualizer.segmentsVisualizer._coverflow()
                    self.displayRaw(data);
                }
            };
        }
    }

    function Compiler() {
        var self = this;
        var DELAY = 100.0;

        self.$view = null;
        self._filter = null;
        self._options = null;
        self._socket = null;
        self._visualizer = null;
        self._scheduler = null;

        self._uid = 0;

        self.events = function() {
            self.$view.find('#generate').click(self.startGeneration);
        };

        //reopen the visualizer if it has been closed
        self.reopenVisualizer = function () {
            if (self._visualizer) {
                self._visualizer.show();
            }
        }


        self.onmessage = function (message) {
            var data = JSON.parse(message.data);
            if (data.error) {
                $.UIkit.notify("An error occurred while compiling videos, see logs for details");
                return console.error(data.error);
            }

            self._scheduler.scheduleNextStep(self._uid++, data.dataType, data);
        }

        self.initialize = function () {
            self.$view = $('#compiler-container');
            self._filter = new Filter(self.$view.find('#filters-list'),
                                     self.$view.find('#open-add-filter'));
            self._options = new OptionsManager(self.$view.find('#options'));

            self._visualizer = new Visualizer(self.$view.find('#visualization'), {
                initialDelay: DELAY
            });
            self._scheduler = new Scheduler(self._visualizer, {
                delay: DELAY
            });


            self._socket = new WebSocket('ws://localhost:666/subscribe/video/compile');
            self._socket.onopen = self.onopen;
            self._socket.onclose = self.onclose;
            self._socket.onmessage = self.onmessage;

            self.events();
        }

        self.startGeneration = function() {
            var options = self._options.getValues();
            var filters = self._filter.getCriteria();

            self.send({action: 'start', options: options, filters: filters});
        }

        self.send = function(message) {
            self._socket.send(JSON.stringify(message));
        }

        self.onopen = function () {
            self._scheduler.play();
        }

        self.onclose = function () {
            console.log("Connection closed");
        }

        self.initialize();

    }

    new Compiler();
});
