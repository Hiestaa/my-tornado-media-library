$(function () {
    function TagsDisplayer() {
        var self = this;
        self.template = '\
<div id="tags-displayer" style="display: none">\
    <table class="uk-table uk-table-striped">\
        <caption id="title-display"></caption>\
        <thead>\
            <tr>\
                <th width="50%" colspan="2" id="time-title">Time\
                    <i class="close uk-icon-close" title="Close"/>\
                </th>\
                <th id="time-display" colspan="2" width="50%"></th>\
            </tr>\
            <tr class="small">\
                <th width="50%" id="resolution-title">Resolution</th>\
                <td id="resolution-display" width="25%"></td>\
                <td id="fps-display" width="25%"></td>\
                <td id="size-display" width="25%"></td>\
            </tr>\
            <tr class="small hidden" id="analysis-row">\
                <th width="25%" id="analysis-title">Face ratio/time/prop</th>\
                <td id="face-ratio-display" width="25%"></td>\
                <td id="face-time-display" width="25%"></td>\
                <td id="face-prop-display" width="25%"></td>\
            </tr>\
            <tr class="small">\
                <th width="50%" colspan="2" id="created-title">Created <i class="uk-icon-calendar" /></th>\
                <td id="created-display" colspan="2" width="50%"></td>\
            </tr>\
            <tr class="small">\
                <th width="35%" id="display-title">Display <i class="uk-icon-slack" /> / <i class="uk-icon-calendar" /></th>\
                <th id="display-display" width="15%"></th>\
                <td id="last-display-display" colspan="2" width="50%"></td>\
            </tr>\
            <tr class="small">\
                <th width="35%" id="seen-title">Watched <i class="uk-icon-slack" /> / <i class="uk-icon-calendar" /></th>\
                <th id="seen-display" width="15%"></th>\
                <td id="last-seen-display" colspan="2" width="50%"></td>\
            </tr>\
            <tr class="small">\
                <th width="35%" id="favorite-title">Starred <i class="uk-icon-slack" /> / <i class="uk-icon-calendar" /></th>\
                <th id="favorite-display" width="15%"></th>\
                <td id="last-favorite-display" colspan="2" width="50%"></td>\
            </tr>\
            <tr class="small">\
                <th width="35%" id="tagged-title">Tags <i class="uk-icon-slack" /> / <i class="uk-icon-calendar" /></th>\
                <th id="tagged-display" width="15%"></th>\
                <td id="last-tagged-display" colspan="2" width="50%"></td>\
            </tr>\
        </thead>\
        <tfoot><tr><td id="activity-history" colspan="4"></td></tr></tfoot>\
        <tbody id="tags-list">\
        </tbody>\
    </table>\
</div>\
';
        self.tagTemplate = '\
    <tr><td colspan="2">{{name}}</td><td colspan="2">{{value}}</td></tr>\
    '
        self.hideTimeout = null;
        $('body').append(self.template);

        self.updateVideoDetails = function (video, tagsList) {
            $('#tags-displayer #title-display').html(video.name);
            $('#tags-displayer #time-display').html(video.duration_str);
            $('#tags-displayer #time-display').css('color', colorMapping('duration', video.duration));
            $('#tags-displayer #size-display').html(video.fileSize_str);
            $('#tags-displayer #size-display').css('color', colorMapping('size', video.fileSize));
            $('#tags-displayer #width-display').html(video.width + ' x ');
            $('#tags-displayer #resolution-display').html(video.width + ' x ' + video.height);
            $('#tags-displayer #resolution-display').css('color', colorMapping('resolution', [video.width, video.height]));
            $('#tags-displayer #fps-display').html(' @ ' + video.fps.toString().slice(0, 5) + ' FPS');
            $('#tags-displayer #fps-display').css('color', colorMapping('fps', video.fps));
            $('#tags-displayer #created-display').html(video.creation_str);
            $('#tags-displayer #display-display').html(video.display);
            $('#tags-displayer #last-display-display').html(video.lastDisplay_str);
            $('#tags-displayer #seen-display').html(video.seen);
            $('#tags-displayer #last-seen-display').html(video.lastSeen_str);
            $('#tags-displayer #favorite-display').html(video.favorite);
            $('#tags-displayer #last-favorite-display').html(video.lastFavorite_str);
            $('#tags-displayer #tagged-display').html(tagsList.length);
            $('#tags-displayer #last-tagged-display').html(video.lastTagged_str);
            if (video.faceTime || video.faceTimeProp || video.faceRatio) {
                $('#tags-displayer #analysis-row').removeClass('hidden');
                var color = colorMapping('faceTimeProp', video.faceTimeProp);
                $('#tags-displayer #face-ratio-display').css('color', color).html(video.faceRatio.toString().slice(0, 6) + ' %');
                $('#tags-displayer #face-time-display').css('color', color).html(video.faceTime + ' frames');
                $('#tags-displayer #face-prop-display').css('color', color).html(video.faceTimeProp.toString().slice(0, 6) + ' %');
            }
            else {
                $('#tags-displayer #analysis-row').addClass('hidden');
            }
        }

        self.updateTagsDetails = function(tagsList) {
            $('#tags-displayer #tags-list').html('')
            for (var i = 0; i < tagsList.length; i++) {
                $('#tags-displayer #tags-list').append(render(self.tagTemplate, {
                    name: tagsList[i].name,
                    value: tagsList[i].value
                }));
            };
        }

        // make the activity sparkline for the video history
        // unit is either 'second', 'minute', 'hour', 'day', 'week' or 'year'
        // period is the number of 'unit' of activity history that should be rendered
        self.makeActivitySparkline = function(video, unit, period) {

            var now = Date.now() / 1000;
            var unitToS = {
                'second': 1,
                'minute': 60,
                'hour': 60 * 60,
                'day': 60 * 60 * 24,
                'week': 60 * 60 * 24 * 7,
                'year': 60 * 60 * 24 * 365,
            }
            var unitInS = unitToS[unit];
            var beginning = now - unitInS * period;

            var emptyDataset = () => {
                const arr = [];
                var cur = beginning;
                for (var cur = beginning; cur < now; cur += unitInS) {
                    arr.push(0);
                }
                return arr;
            }

            var displayData = emptyDataset();
            var displayColor = '#0094F2';
            var seenData = emptyDataset();
            var seenColor = '#00BB0C';
            var starredData = emptyDataset();
            var starredColor = '#FF9C00';
            var taggedData = emptyDataset();
            var taggedColor = '#D60000';

            var fillInDataset = (dataset, eventHistory) => {
                for (var i = 0; i < eventHistory.length; i++) {
                    var eventTs = eventHistory[i];
                    var dIdx = Math.round((eventTs - beginning) / unitInS);
                    if (dIdx < 0) { continue; }
                    if (dIdx >= dataset.length) { dIdx = dataset.length - 1; }
                    dataset[dIdx] = dataset[dIdx] + 1;
                }
            }

            fillInDataset(displayData, video.displayHistory);
            fillInDataset(seenData, video.seenHistory);
            fillInDataset(starredData, video.favoriteHistory);
            fillInDataset(taggedData, video.taggedHistory);

            var finalDataset = [];
            for (var i = 0; i < displayData.length; i++) {
                finalDataset.push([
                    displayData[i],
                    seenData[i],
                    starredData[i],
                    taggedData[i]
                ]);
            }

            $('#tags-displayer #activity-history').sparkline(finalDataset, {
                type: 'bar',
                stackedBarColor: [displayColor, seenColor, starredColor, taggedColor],
                zeroColor: '#D5D5D5',
                barWidth: ((420 - finalDataset.length) / finalDataset.length),
                barSpacing: 1
            });
        }

        self.preventClose = function () {
            $('#tags-displayer #activity-history').off().on('mouseenter', () => {
                clearTimeout(self.hideDelayer);
            }).on('mouseleave', () => {
                self.hide();
            });
        }

        self.show = function(video, tagsList, position) {
            $('#tags-displayer').removeClass('right center left').addClass(position ? position : 'center');

            // headers (video details)
            self.updateVideoDetails(video, tagsList);
            // tags
            self.updateTagsDetails(tagsList);

            // then actually show
            clearTimeout(self.hideTimeout);
            clearTimeout(self.hideDelayer);

            $('#tags-displayer').css('display', 'block')
            // let the time for the window to be drawn
            setTimeout(function () {
                $('#tags-displayer').css('opacity', '1').css('top', '1rem');
                // activity history
                self.makeActivitySparkline(video, 'day', 120);
            }, 10);
            self.preventClose();
        }

        self._doHide = function () {
            $('#tags-displayer').css('opacity', '0').css('top', '-10em')
            self.hideTimeout = setTimeout(function () {
                $('#tags-displayer').css('display', 'none');
            }, 1000)
        }

        self.hide = function () {
            clearTimeout(self.hideDelayer);
            self.hideDelayer = setTimeout(self._doHide, 1000);
        }

        $('#tags-displayer .close').click(this._doHide);
    }
    window.tagsDisplayer = new TagsDisplayer()
});