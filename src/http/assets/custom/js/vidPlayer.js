/*
        <div class="uk-overlay">\
            <img src="{{thumbnail}}" alt="{{title}} thumbnail" width="100%">\
            <div class="uk-overlay-area"></div>\
        </div>\\*/
$(function () {
    function VideoPlayer(videoId) {
        if (!videoId)
            return $.UIkit.notify("Unable to load player: no video selected.", {status:'danger'});
        var self = this;
        self.template = '\
<div class="uk-width-1-1">\
    <div class="uk-panel uk-panel-header uk-panel-box" id="tags-list">\
        <div class="uk-panel-badge uk-badge-left">\
            <div class="uk-button-group">\
                <button class="uk-button uk-button-primary" id="open-add-filter">Add Tag</button>\
                <div data-uk-dropdown="{mode:\'click\'}">\
                    <a class="uk-button uk-button-primary">...</a>\
                    <div class="uk-dropdown uk-dropdown-small">\
                        <ul class="uk-nav uk-nav-dropdown">\
                            <li class="uk-nav-header">Additional Actions</li>\
                            <li><a id="open-folder">Open Folder</a></li>\
                            <li><a id="view-analysis" class="hidden">View Analysis</a></li>\
                            <li><a id="analyze">Analyze</a></li>\
                        </ul>\
                    </div>\
                </div>\
            </div>\
        </div>\
        <div class="uk-panel-badge"><button class="uk-button uk-button-danger" id="delete-video">Delete</button></div>\
        <h2 class="uk-panel-title" id="video-title">\
        <span id="to-watch" class="uk-icon-eye" title="Mark as \'To Watch\'" data-uk-tooltip="{pos: \'top-right\'}"></span>\
        <i class="uk-icon-cogs" title="This video has been analyzed already!" data-uk-tooltip="{pos: \'top-right\'}"></i>\
        <a href="{{url}}" target="_blank" id="video-title-link">{{title}}</a>\
        <span id="star" class="uk-icon-star" title="Star this video" data-uk-tooltip="{pos: \'top-right\'}">&nbsp;({{favorite}})</span>\
        </h2>\
    </div>\
</div>\
<div class="uk-width-1-1 vid-player-parent">\
    <div class="vid-player">\
        <div class="uk-overlay">\
            <img src="{{thumbnail}}" alt="{{title}} thumbnail" width="100%">\
            <div class="uk-overlay-area"></div>\
        </div>\
    </div>\
</div>\
<form class="uk-form uk-form-horizontal uk-width-1-1" id="vid-details" onsubmit="return false;">\
    <fieldset data-uk-margin>\
        <legend>View/Edit Video Details</legend>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="name">Name of this video</label>\
            <div class="uk-form-controls">\
                <input id="name" value="{{name}}" class="uk-width-1-1" type="text" title="Type enter to save" data-uk-tooltip="{pos: \'right\'}">\
            </div>\
        </div>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="description">Description of this video</label>\
            <div class="uk-form-controls">\
                <textarea id="description" class="uk-width-1-1" type="text" title="Type enter to save" data-uk-tooltip="{pos: \'right\'}">{{description}}</textarea>\
            </div>\
        </div>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="width">Resolution & FPS</label>\
            <div class="uk-form-controls uk-grid has-labels">\
                <div class="uk-width-1-3">\
                    Width (in px)\
                     <input id="width" value="{{width}}" type="text" title="Type enter to save" data-uk-tooltip="{pos: \'bottom-left\'}">\
                </div>\
                <div class="uk-width-1-3">\
                    Height (in px)\
                    <input id="height" value="{{height}}" type="text" title="Height (in px)" data-uk-tooltip="{pos: \'bottom-left\'}">\
                </div>\
                <div class="uk-width-1-3">\
                    Frame per Second\
                    <input id="fps" value="{{fps}}" type="text" title="Frame per second" data-uk-tooltip="{pos: \'bottom-left\'}">\
                </div>\
            </div>\
        </div>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="lastFavorite_str">Dates</label>\
            <div class="uk-form-controls uk-grid has-labels">\
                <div class="uk-width-1-4">\
                    Last Favorite\
                    <input id="lastFavorite_str" type="text" disabled value="{{lastFavorite_str}}">\
                </div>\
                <div class="uk-width-1-4">\
                    Last Tagged\
                    <input id="lastTagged_str" type="text" disabled value="{{lastTagged_str}}">\
                </div>\
                <div class="uk-width-1-4">\
                    Last Seen (watched)\
                    <input id="lastSeen_str" type="text" disabled value="{{lastSeen_str}}">\
                </div>\
                <div class="uk-width-1-4">\
                    Last Display\
                    <input id="lastToWatch_str" type="text" disabled value="{{lastDisplay_str}}">\
                </div>\
            </div>\
        </div>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="lastFavorite">Counters</label>\
            <div class="uk-form-controls uk-grid has-labels">\
                <div class="uk-width-1-4">\
                    # of times starred\
                    <input id="favorite" type="text" disabled value="{{favorite}}">\
                </div>\
                <div class="uk-width-1-4">\
                    # of times Seen (watched)\
                    <input id="seen" type="text" disabled value="{{seen}}">\
                </div>\
                <div class="uk-width-1-4">\
                    # of times Displayed\
                    <input id="displayed" type="text" disabled value="{{display}}">\
                </div>\
                <div class="uk-width-1-4">\
                    Last To Watch\
                    <input id="lastToWatch_str" type="text" disabled value="{{lastToWatch_str}}">\
                </div>\
            </div>\
        </div>\
        <div class="uk-form-row" id="analysis-row">\
            <label class="uk-form-label" for="lastFavorite">Analysis Results</label>\
            <div class="uk-form-controls uk-grid has-labels">\
                <div class="uk-width-1-3">\
                    Average Face Ratio\
                    <input id="average-face-ratio" type="text" disabled value="{{averageFaceRatio}}">\
                </div>\
                <div class="uk-width-1-3">\
                    Face Time (frames)\
                    <input id="face-time" type="text" disabled value="{{faceTime}}">\
                </div>\
                <div class="uk-width-1-3">\
                    Face Time (proportion)\
                    <input id="face-prop" type="text" disabled value="{{faceTimeProp}}">\
                </div>\
            </div>\
        </div>\
        <div class="uk-form-row">\
            <label class="uk-form-label" for="ss-frame-rate">Thumbnail</label>\
            <div class="uk-form-controls uk-grid">\
                <input id="ss-frame-rate" value="1/60" type="text" class="uk-width-1-4" style="margin-right: 10px" title="Number of thumbnails / Time period" data-uk-tooltip="{pos: \'bottom-left\'}" />&nbsp;\
                <input id="ss-width" value="1280" type="text" class="uk-width-1-4" style="margin-right: 10px" title="Thumbnails Width (in px)" data-uk-tooltip="{pos: \'bottom-left\'}" />&nbsp;\
                <input id="ss-height" value="720" type="text" class="uk-width-1-4" style="margin-right: 10px" title="Thumbnails Height (in px)" data-uk-tooltip="{pos: \'bottom-left\'}" />&nbsp;\
                <a id="generate-thumbnails" class="uk-button uk-width-1-5" style="float: right">Regenerate</a>\
                <div class="uk-grid uk-width-1-1" id="thumbnail">\
                </div>\
            </div>\
        </div>\
    </fieldset>\
</form>\
<div class="uk-form">\
    <legend>Related Videos</legend>\
</div>\
<div class="uk-width-1-1">\
    <div class="uk-grid" id="vid-related">\
    </div>\
</div>\
<div id="modal-dialog" class="uk-modal">\
    <div class="uk-modal-dialog" id="modal-dialog-content">\
    </div>\
</div>\
<div id="video-analyze-result"></div>\
';
        self.tagTemplate = '\
<div class="uk-button-group" data-tag-id="{{tagId}}" >\
    <button class="uk-button">{{name}}</button>\
    <select id="tag-value"></select>\
    <button class="uk-button uk-button-danger remove-tag"><i class="uk-icon-close"></i></button>\
</div>';
        self.snapshotTemplate = '\
<div class="uk-width-1-3 thumbnail-item">\
    <a class="uk-thumbnail uk-overlay-toggle" href="#!">\
        <div class="uk-overlay">\
            <img src="{{snapshot}}" alt="{{number}}">\
            <div class="uk-overlay-area" id="thumbnail-{{number}}" data-snap-id="{{number}}">\
                <span class="select-thumbnail" title="Select Snapshot {{number}}" data-uk-tooltip="{pos: \'top-left\'}"></span>\
                <span class="remove-thumbnail" title="Delete Snapshot {{number}}" data-uk-tooltip="{pos: \'top-left\'}"></span>\
            </div>\
        </div>\
    </a>\
</div>\
<div class="uk-width-1-3" id="loading-info">\
    <i class="fa fa-spinner fa-spin"></i>\
</div>\
';
        self.deleteModalTemplate = '\
<button type="button" class="uk-modal-close uk-close"/>\
<h1 class="uk-modal-header">Warning!</h1>\
<p>This will permanently delete the video and all the related tags from database AND from your hard drive. There will be no way to retrieve back the video. Are you sure you wish to delete it?</p>\
<div class="uk-modal-footer">\
    <button type="button" class="uk-button uk-modal-close" id="cancel-delete">Cancel</button>\
    <button type="button" class="uk-button uk-button-danger" id="confirm-delete">Confirm</button>\
</div>\
<div class="uk-modal-caption"><img src="{{thumbnail}}" alt="{{title}} thumbnail" width="100%"></div>\
';

        self.$view = $('#vid-player-container');
        self.videoId = videoId;
        self.video = null; // will be populated when receiving the video object
        self.tagFormatters = {}  // associate tag (encoded) names to formatter function
        // associate to each tag name an object, which associate the tag id to the tag value
        self.tagValues = {};
        // associate to each tag id the corresponding name and value.
        self.tagIds = {};

        self.analyzer = null;

        self._doAnalysis = function(force) {
            if (self.analyzer) {
                return self.analyzer.reopenVisualizer();
            }
            else {
                self.analyzer = new Analyzer(
                    self.videoId,
                    self.$view.find('#video-analyze-result'),
                    {
                        thumbnail: self.video.snapshots[self.video.thumbnail],
                        force: force
                    },
                    {
                        onAddTag: function (value) {
                            self.onAddTag('Tag', value);
                        }
                    });
            }
        }

        self.doAnalysis = function() {
            self._doAnalysis(self.video && self.video.analysis && (
                self.video.analysis.faceTime ||
                self.video.analysis.faceTimeProp ||
                self.video.analysis.averageFaceRatio
            ));
        }

        self.viewAnalysis = function () {
            self._doAnalysis(false);
        }

        self.generationProgression = function () {
            $.ajax({
                url: '/api/video/thumbnails/generationProgress',
                type: 'get',
                data: {
                    videoId: self.videoId,
                },
                dataType: 'json',
                success: function (video) {
                    if ($('#vid-details #thumbnail .thumbnail-item').length - 1 < Object.keys(video.snapshots).length) {
                        self.renderThumbnails(video, function () {
                            self.events();
                            if (video.generationFinished) {
                                self.$view.find('#vid-details #thumbnail #loading-info > i')
                                    .removeClass('fa-spinner').removeClass('fa').removeClass('fa-spin')
                                    .addClass('uk-icon-check');
                                setTimeout(function () {
                                    self.$view.find('#vid-details #thumbnail #loading-info > i').remove();
                                }, 10000);
                            }
                        });
                    }
                    if (!video.generationFinished)
                        setTimeout(self.generationProgression, 2000);

                },
                error: function(e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while getting generation progress, see logs for details.", {status:'danger'});
                }
            })
        }

        self.openContainingFolder = function () {
            $.ajax({
                url: '/api/video/folder',
                data: {
                    videoId: self.videoId
                }
            });
        }

        self.generateThumbnails = function () {
            $.ajax({
                url: '/api/video/thumbnails/regenerate',
                type: 'post',
                data: {
                    videoId: self.videoId,
                    frameRate: self.$view.find('#vid-details #ss-frame-rate').val(),
                    width: self.$view.find('#vid-details #ss-width').val(),
                    height: self.$view.find('#vid-details #ss-height').val(),
                },
                dataType: 'json',
                success: function (video) {
                    $('#vid-details #ss-frame-rate').removeClass("unsaved");
                    $('#vid-details #ss-height').removeClass("unsaved");
                    $('#vid-details #ss-width').removeClass("unsaved");
                    self.renderThumbnails(video, function () {
                        self.events();
                        setTimeout(self.generationProgression, 2000);
                    });
                },
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while re-generating snapshots, see logs for details.", {status:'danger'});
                }
            });
        }

        self.loadRelated = function () {
            $.ajax({
                url: '/api/video/related',
                type: 'get',
                dataType: 'json',
                data: {videoId: self.videoId, nbRelated: 4},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while loading related videos, see logs for details.", {status:'danger'});
                },
                success: function (related) {
                    for (var i = 0; i < related.length; i++) {
                        var expand = ['top', 'center']
                        if (i == 0)
                            expand[1] = 'right';
                        if (i == related.length - 1)
                            expand[1] = 'left';
                        var detailsPosition = 'left';
                        if (i < 2) { detailsPosition = 'right'; }
                        new VidSnap('#vid-related', related[i], {
                            width: related.length,
                            expandOnHover: expand.join(' '),
                            append: true,
                            detailsPosition
                        });
                    };
                    for (var i = 0; i < related.length; i++) {
                        var ul = '<div class="uk-width-1-' + related.length + '"><table class="uk-table uk-table-striped"><thead><tr><th>Related by (' + related[i].relatedByScore + '):</th></tr></thead><tbody>';
                        for (var j = 0; j < related[i].relatedBy.length; j++) {
                            ul += '<tr><td>' + related[i].relatedBy[j].name + ' -- ' + related[i].relatedBy[j].value + '</td></tr>';
                        };
                        ul += '</tbody></table>';
                        $(ul).appendTo('#vid-related');
                    };
                }
            });
        }

        self.onSetToWatch = function () {
            var $this = $(this);
            $.ajax({
                url: '/api/video/update',
                type: 'post',
                dataType: 'json',
                data: {videoId: self.videoId, field: 'toWatch', value: !self.video.toWatch},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while marking this video as 'To Watch', see logs for details.", {status: 'danger'});
                },
                success: function () {
                    self.video.toWatch = !self.video.toWatch;
                    $this.toggleClass('to-watch');
                }
            })
        }

        self.onFavorite = function () {
            var $this = $(this);
            $.ajax({
                url: '/api/video/increment',
                type: 'post',
                dataType: 'json',
                data: {videoId: self.videoId, field: 'favorite'},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occurred while marking this video as favorite, see logs for details.", {status: 'danger'});
                },
                success: function () {
                    self.video.favorite += 1;
                    if (!$this.hasClass('starred'))
                        $this.addClass('starred');
                    $this.html('&nbsp;(' + self.video.favorite + ')');
                    $('#vid-details #favorite').val(self.video.favorite);
                }
            })
        }

        self._editThumbnail = function (newThumbnail, successCb) {
            $.ajax({
                url: '/api/video/update',
                type: 'post',
                dataType: 'json',
                data: {videoId: self.videoId, field: 'thumbnail', value: newThumbnail},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while changing thumbnail, see logs for details.", {status:'danger'});
                },
                success: successCb
            });
        }

        self.onEditThumbnail = function () {
            var $this = $(this).parent();
            var newThumbnail = $this.attr('data-snap-id');
            if (newThumbnail == 'random')
                newThumbnail = 'null';
            if (!$this.hasClass('selected')) {
                self._editThumbnail(newThumbnail, function () {
                    $('#vid-details #thumbnail .uk-overlay-area.selected').removeClass('selected');
                    $this.addClass('selected');
                });
            }
        }

        self._deleteThumbnail = function (thumb, successCb) {
            $.ajax({
                url: '/api/video/thumbnails/remove',
                type: 'post',
                dataType: 'json',
                data: {videoId: self.videoId, position: thumb},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while changing thumbnail, see logs for details.", {status:'danger'});
                },
                success: successCb
            });
        }

        self.onDeleteThumbnail = function () {
            var $this = $(this).parent();
            if ($this.attr('data-snap-id') == 'random')
                return $.UIkit.notify("Unable to delete the 'random' thumbnail! (This feature should be removed...)");
            if ($this.hasClass('selected')) {
                self._editThumbnail('null', function () {
                    self._deleteThumbnail($this.attr('data-snap-id'), function (video) {
                        self.renderThumbnails(video);
                    });
                });
            }
            else {
                self._deleteThumbnail($this.attr('data-snap-id'), function (video) {
                    self.renderThumbnails(video);
                });
            }
        }

        self.onEditSSFrameRate = function(e) {
            var vals = $(this).val().split('/');
            if (vals.length != 2) {
                $.UIkit.notify("Thumbnails frame rate must have the format X/Y!", {status: 'warning'});
                return $(this).val('1/60');
            }
            try {
                var v1 = parseInt(vals[0]);
                var v2 = parseInt(vals[1]);
                if (v1 <= 0 || v2 <= 0)
                    throw "error";
            }
            catch (err) {
                $.UIkit.notify("Thumbnails frame rate must have the format X/Y, where both X and Y are positive integers!", {status: 'warning'});
                return $(this).val('1/60');
            }
            $(this).addClass('unsaved');
        }

        self.onEditSSWidth = function (e) {
            var width = 496;
            try {
                width = parseInt($(this).val());
                if (width <= 0)
                    throw "error";
            }
            catch (err) {
                $.UIkit.notify("Thumbnails width must be a positive integer!", {status: 'warning'});
                $(this).val(width);
            }
            var ratio = 496 / 278;
            self.$view.find('#vid-details #ss-height').val(parseInt(width / ratio)).addClass('unsaved');
            self.$view.find('#vid-details #ss-width').val(width).addClass('unsaved');
        }

        self.onEditSSHeight = function (e) {
            var height = 278;
            try {
                height = parseInt($(this).val());
                if (height <= 0)
                    throw "error";
            }
            catch (err) {
                $.UIkit.notify("Thumbnails height must be a positive integer!", {status: 'warning'});
                $(this).val(height);
            }
            var ratio = 496 / 278;
            self.$view.find('#vid-details #ss-width').val(parseInt(height * ratio)).addClass('unsaved');
            self.$view.find('#vid-details #ss-height').val(height).addClass('unsaved');
        }

        self.onEditDetails = function (e) {
            var $this = $(this)
            if (this.id == 'ss-frame-rate' || this.id == 'ss-width' || this.id == 'ss-height')
                return;
            // called when a key is pressed while
            // a detail input is active.
            if (e.keyCode == 13) {
                // validate
                // todo: add validation method?
                $.ajax({
                    url: '/api/video/update',
                    type: 'post',
                    dataType: 'json',
                    data: {videoId: self.videoId, field: $this.attr('id'), value: $this.val()},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while editing " + $this.attr('id') + ", see logs for details.", {status:'danger'});
                    },
                    success: function () {
                        $this.removeClass('unsaved');
                        self.video[$this.attr('id')] = $this.val();
                        if ($this.attr('id') == 'favorite')
                            $('#tags-list #star').html('&nbsp(' + self.video.favorite + ')');
                    }
                })
            }
            else {
                var val = $this.val();
                var valid = (e.keyCode > 47 && e.keyCode < 58)   || // number keys
                    e.keyCode == 32 || e.keyCode == 13   || // spacebar & return key(s) (if you want to allow carriage returns)
                    (e.keyCode > 64 && e.keyCode < 91)   || // letter keys
                    (e.keyCode > 95 && e.keyCode < 112)  || // numpad keys
                    (e.keyCode > 185 && e.keyCode < 193) || // ;=,-./` (in order)
                    (e.keyCode > 218 && e.keyCode < 223);   // [\]' (in order)
                if (valid)
                    val += e.key;
                if (e.keyCode == 8)
                    val = val.substring(0, val.length-1);
                if (val != self.video[$this.attr('id')]) {
                    if (!$this.hasClass('unsaved'))
                        $this.addClass('unsaved');
                }
                else
                    $this.removeClass('unsaved');
            }
        }

        // little trick to remove the right tag if it has been update already
        // since `onEditTag` will be called with the same tag id that was loaded initially, whatever
        // the number of times it has been edited then, editions will fail to remove an update tag.
        // this translates the old if the the new id, if it has been update already.
        self._updatedTagId = {};

        // opts.noReRender: prevent from rendering the tag again (e.g. it already exists, we're just updating it)
        self.onEditTag = function (name, newValue, oldId, opts) {
            opts = opts || {};
            console.log("On edit tag name=" + name + ", newValue=" + newValue + ", oldId=" + oldId);
            // value is an id if the item does already exist, otherwise it is the value of the new tag that should be
            // created
            var tagValues = self.tagValues[name] || {};
            if (newValue in tagValues) {
                // the tag exist - remove the old one
                if (oldId) {
                    toldId = self._updatedTagId[oldId] || oldId;
                    var pos = self.video.tags.indexOf(toldId);
                    if (pos !== -1) {
                        self.video.tags.splice(pos, 1);
                    }
                    $.ajax({
                        url: '/api/video/tag',
                        type: 'post',
                        dataType: 'json',
                        data: {videoId: self.videoId, tagId: toldId, remove: true},
                        error: function (e) {
                            console.error(e);
                            $.UIkit.notify("An error occured while deleting the tag, see logs for details.", {status:'danger'});
                        },
                        success: function () { }
                    });
                }
                // then add the new one
                $.ajax({
                    url: '/api/video/tag',
                    type: 'post',
                    dataType: 'json',
                    data: {videoId: self.videoId, tagId: newValue},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while adding the new tag, see logs for details.", {status:'danger'});

                    },
                    success: function () {
                        if (oldId) {
                            self._updatedTagId[oldId] = newValue;
                        }
                        if (self.video.tags.indexOf(newValue) === -1) {
                            self.video.tags.push(newValue);
                            var encodedName = name.split(' ').join('-');
                            var formatter = self.tagFormatters[encodedName] || function (v) { return v };
                            if (!opts.noReRender) {
                                self.renderTag(name, newValue);
                            }
                        }
                        else {
                            $.UIkit.notify("This tag is already attached to this video!")
                        }
                    }
                });
            }
            else {
                // create a tag
                $.ajax({
                    url: '/api/tag/create',
                    type: 'post',
                    dataType: 'json',
                    data: {name: name, value: newValue},
                    error: function (e) {
                        console.error(e);
                    },
                    success: function (tag) {
                        self.tagValues[tag.name][tag._id] = tag.value;
                        // now that the tag does exist, call onEditTag again.
                        // it will remove the old one and add the newly created tag.
                        self.onEditTag(tag.name, tag._id, oldId)
                    }
                })
            }
        }

        self.onDeleteTag = function () {
            var $this = $(this);
            var tagId = $this.parent().attr('data-tag-id');
            $.ajax({
                url: '/api/video/tag',
                type: 'post',
                dataType: 'json',
                data: {videoId: self.videoId, tagId: tagId, remove: true},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (result) {
                    $this.parent().remove();
                    var i = self.video.tags.indexOf(tagId);
                    self.video.tags.splice(i, 1);
                }
            })
        }

        self.renderTag = function (name, id) {
            var $tagItem = $(render(self.tagTemplate, {
                name: name,
                tagId: id
            }));
            self.$view.find('#tags-list').append($tagItem);
            self.$view.find('#tags-list .remove-tag').off().click(self.onDeleteTag);
            for (var tagId in self.tagValues[name]) {
                $tagItem.find('select#tag-value').append(
                    '<option value="' + tagId + '" ' + (tagId === id ? 'selected' : '') + '>' + self.tagValues[name][tagId] + '</option>');
            };
            $tagItem.find('select#tag-value').selectize({
                create: true,
                onItemAdd: function (newValue, $item) {
                    // FIXME: when editing a tag multiple times, the same 'id' keep being passed as the old id
                    // that is the one that was initially rendered, resulting in not actually removing the right tag.
                    self.onEditTag(name, newValue, id, {noReRender: true});
                },
                onDropdownOpen: function () {
                    // fucking z-index
                    $tagItem.find('.selectize-control').addClass('elevated');
                },
                onDropdownClose: function () {
                    $tagItem.find('.selectize-control').removeClass('elevated');
                }
            });
        }

        self.onAddTag = function (name, value) {
            // 'name' is the name of the tag
            // 'value' is the mongodb id of the tag, or a value which id will be looked for
            //         if the value doesn't match any id, it will be created
            var tagValues = self.tagValues[name];
            Object.keys(tagValues).map(function (tagId) {
                if (tagValues[tagId] && tagValues[tagId].toUpperCase() === value.toUpperCase()) {
                    value = tagId;
                }
            });
            self.onEditTag(name, value);

        }

        self.onRcvTags = function (tags) {
            // create properties manager, and add all tags available
            self.propertiesPanel = new Properties(
                [self.$view.find('#open-add-filter')],
                function (type, name, value) {
                    name = name.split('-').join(' ');
                    self.onAddTag(name, value);
                }, {
                    tagsOnly: true,
                    flipped: false,
                    closeOnSelect: false
                }
            );
            tagNames = [];
            self.tagValues = {};
            for (var i = 0; i < tags.length; i++) {
                var tag = tags[i]
                // populate tagNames array if this name does not exist yet
                if (tagNames.indexOf(tag.name) === -1) {
                    tagNames.push(tag.name)
                    self.tagValues[tag.name] = {};
                }
                // populate tagValues object if this tag does not exist yet
                // (note: should NOT exist though, the condition may not be necessary)
                if (!(tag._id in self.tagValues))
                    self.tagValues[tag.name][tag._id] = tag.value;
            };
            // as render will use existing list of tags to populate the selectize
            // options, it has to be done in a second pass.
            for (var i = 0; i < tags.length; i++) {
                var tag = tags[i]
                // render the tag if it belongs to the video
                if (self.video.tags.indexOf(tag._id) !== -1)
                    self.renderTag(tag.name, tag._id);
            };
            for (var i = 0; i < tagNames.length; i++) {
                var encodedName = tagNames[i].split(' ').join('-');
                var options = self.tagValues[tagNames[i]];
                self.tagFormatters[encodedName] = self.propertiesPanel.addTagProperty(
                    'tag', encodedName, tagNames[i], options);
            };
        }
        self.loadTags = function () {
            $.ajax({
                url: '/api/tag/get',
                dataType: 'json',
                type: 'post',
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: self.onRcvTags
            });
        }
        self.renderThumbnails = function (video, _cb) {
            /*
            Renders the thumbnail of the video in the expected thumbnail div, replacing any existing data.
            WARNING: as the DOM will  be updated, it is advised to call the function `self.events`, when this function is done.
                THis is done automatically if no `_cb` is given, but won't be done if `_cb` is overrided.
                If no `_cb` is provided, the loading info will be removed as well.
            */
            var snapshots = [];
            for (var i in video.snapshots) {
                snapshots.push(video.snapshots[i] + '?' + new Date().getTime());
            };
            preloadPictures(snapshots, function () {
                self.$view.find('#vid-details #thumbnail').html(render(self.snapshotTemplate, {
                    snapshot: '/assets/custom/img/question-mark.png',
                    number: 'random'
                }));
                for (var i in video.snapshots) {
                    $('#vid-details #loading-info:last').remove();
                    self.$view.find('#vid-details #thumbnail').append(render(self.snapshotTemplate, {
                        snapshot: snapshots[i],
                        number: i
                    }));
                };
                if (video.realThumbnail === null)
                    $('#vid-details #thumbnail .uk-overlay-area#thumbnail-random').addClass('selected');
                else
                    $('#vid-details #thumbnail .uk-overlay-area#thumbnail-' + video.realThumbnail).addClass('selected');
                if (_cb)
                    _cb();
                else {
                    self.events()
                    $('#vid-details #loading-info').remove();
                }
            });
        }
        self.renderView = function () {
            document.title = self.video.name;
            var analysis = self.video.analysis;
            self.$view.html(render(self.template, Object.assign({}, self.video, {
                title: self.video.name,
                thumbnail: self.video.snapshots[self.video.thumbnail],
                faceTime: analysis && analysis.faceTime ? analysis.faceTime : '?',
                averageFaceRatio: analysis && analysis.averageFaceRatio ? analysis.averageFaceRatio.toString().slice(0, 7) + ' %' : '?',
                faceTimeProp: analysis && analysis.faceTimeProp ? analysis.faceTimeProp.toString().slice(0, 7) + ' %' : '?',
            })));
            if (analysis && (analysis.faceTime || analysis.faceTimeProp || analysis.averageFaceRatio)) {
                self.$view.find('#analysis-row').removeClass('hidden');
                self.$view.find('#analyze').html('<i class="uk-icon-check-square-o"></i>&nbsp;Re-Analyze');
                self.$view.find('#view-analysis').removeClass('hidden');
            }
            else {
                self.$view.find('#video-title .uk-icon-cogs').addClass('hidden');
                self.$view.find('#view-analysis').addClass('hidden');
                self.$view.find('#analysis-row').addClass('hidden');
            }
            self.renderThumbnails(self.video, function () {
                $('#vid-details #loading-info').remove();
                if (self.video.toWatch)
                    $('#tags-list #to-watch').addClass('to-watch');
                if (self.video.favorite > 0)
                    $('#tags-list #star').addClass('starred');
                self.events();
            });
        };

        self.deleteVid = function () {
            self.$view.find('#cancel-delete').attr('disabled', true);
            self.$view.find('#confirm-delete').replaceWith(
                '<button type="button" class="uk-button uk-button-danger" id="confirmed-delete" disabled>' +
                '<i class="fa fa-spinner fa-spin"></i></button>');
            $.ajax({
                url: '/api/video/' + self.video._id,
                type: 'delete',
                dataType: 'json',
                error: function (e) {
                    console.error(e);
                    self.$view.find('#confirmed-delete').html('<i class="uk-icon-close"></i>');
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (result) {
                    self.$view.find('#confirmed-delete').html('<i class="uk-icon-check"></i>');
                    self.$view.find('#open-add-filter').remove();
                    self.$view.find('#delete-video').remove();
                    self.$view.find('#video-title').html('This video has been deleted!')
                }
            });
        }

        self.playVid = function () {
            $this = $(this);
            $this.find('.uk-overlay-area')
                .attr('style', 'opacity: 0.5 !important')
                .css('background-image', 'url("/assets/custom/img/spinner.gif")')
                .css('background-size', 'auto 80%');
            $.ajax({
                url: '/api/video/play',
                type: 'get',
                dataType: 'json',
                data: {'videoId': self.video._id},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while starting video, see logs for details.", {status: 'danger'});
                },
                success: function () {
                    setTimeout(function () {
                        self.$view.find('#tags-list #to-watch').removeClass('to-watch');
                        $this.find('.uk-overlay-area')
                            .css('background-image', '')
                            .css('opacity', '')
                            .css('background-size', '');
                    }, 10000);
                }
            });
            // var tmp = self.video.filename.split('.');
            // var ext = tmp[tmp.length - 1];
            // if (ext == 'webm' || ext == 'ogg' || ext == 'mp4')
            //     $(this).off().html(
            //         '<video src="' + self.video.url + '" autoplay controls width="100%" poster="' + self.video.snapshots[self.video.thumbnail] + '">' +
            //         '<source src="' + self  .video.url + '">' +
            //         'Sorry, your browser doesn\'t support embedded videos, but don\'t worry, you can <a href="' + self.video.url + '">download it</a> and watch it with your favorite video player!' +
            //         '</video>');
            // else
            //     $(this).off().html(
            //         '<object width="100%"><param name="wmode" value="transparent" />' +
            //         '<embed src="' + self.video.url + '" wmode="transparent" style="height: 576px; width: 100%" />' +
            //         '</object>');
        }

        self.showDeleteModal = function () {
            var modal = self.$view.find("#modal-dialog-content");
            modal.html(render(self.deleteModalTemplate, {
                title: self.video.name,
                thumbnail: self.video.snapshots[self.video.thumbnail],
            }));
            var dialog = $.UIkit.modal('#modal-dialog');
            if (!dialog.isActive()) {
                dialog.show();
                self.events();
            }
        }

        self.events = function () {
            preloadPictures(['/assets/custom/img/spinner.gif']);
            self.$view.find('.vid-player').off('click').on('click', self.playVid);
            $('body').off().keydown(function (e) {
                switch (e.keyCode) {
                    case 46:
                        self.showDeleteModal();
                }
            })
            self.$view.find('#confirm-delete').off().click(self.deleteVid);
            self.$view.find('#vid-details input').off().keydown(self.onEditDetails);
            self.$view.find('#vid-details textarea').off().keydown(self.onEditDetails);
            self.$view.find('#vid-details #thumbnail .uk-overlay-area .select-thumbnail').off().click(self.onEditThumbnail);
            self.$view.find('#vid-details #thumbnail .uk-overlay-area .remove-thumbnail').off().click(self.onDeleteThumbnail);
            self.$view.find('#vid-details #generate-thumbnails').off().click(self.generateThumbnails);
            self.$view.find('#tags-list #to-watch').off().click(self.onSetToWatch);
            self.$view.find('#tags-list #star').off().click(self.onFavorite);
            self.$view.find('#vid-details input#ss-frame-rate').off().blur(self.onEditSSFrameRate)
            self.$view.find('#vid-details input#ss-height').off().blur(self.onEditSSHeight)
            self.$view.find('#vid-details input#ss-width').off().blur(self.onEditSSWidth)
            self.$view.find('#open-folder').off().click(self.openContainingFolder);
            self.$view.find('#analyze').off().click(self.doAnalysis);
            self.$view.find('#view-analysis').off().click(self.viewAnalysis);
            self.$view.find('#delete-video').off().click(self.showDeleteModal);
        };

        self.loadVid = function () {
            spinLoading();
            $.ajax({
                url: '/api/video/display',
                type: 'get',
                dataType: 'json',
                data: {videoId: self.videoId},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (video) {
                    self.video = video;
                    self.renderView();
                    new VidSnap('#vid-player-container .vid-player', video, {
                        width: 1,
                        displayNameOverlay: false,
                        invertHover: false,
                        noLink: true,
                        replace: true,
                        showDetails: false
                    });
                    self.loadTags();
                    spinLoading('stop'); // related can come later
                    self.loadRelated();
                }
            });
        }
        self.loadVid();
    };
    window.VideoPlayer = VideoPlayer;
});