

$(function () {
    var snapTemplate = '\
<div class="uk-width-1-{{width}} vid-snap-parent">\
    <a class="uk-thumbnail uk-overlay-toggle vid-snap {{expandOnHover}}" id="vid-snap-{{_id}}" href="/videoplayer/videoId={{_id}}">\
        <div class="uk-overlay">\
            <div class="uk-overlay-area">\
                <span class="name">{{name}}</span>\
                <span class="duration"><span style="color: {{duration_color}}">{{duration}}</span></span>\
                <span class="size"><span style="color: {{size_color}}">{{size}}</span></span>\
                <span class="resolution"><span style="color: {{resolution_color}}">{{resolution}}</span></span>\
            </div>\
        </div>\
    </a>\
</div>';
    function VidSnap(selector, video, options) {
        /*
        Available options:
        * displayNameOverlay: boolean. Whether or not displaying the name on the overlay area. True by default.
        * noLink: boolean. If set to true, the snapshot will not act as a link to the video player (default is false)
        * replace: boolean. If set to true, the data in the given selector will be overriden by the snapshot.
          Otherwise it will only be prepended.
        * append: boolean. If set to true, the data will be appended to the DOM item retrieved via the given selector.
          By default (and unless options.replace is set to true), data are prepended.
          Note: replace will have a higher priority than append, meaning that setting options.append to true will have no
          effect if options.replace is true as well.
        * showDetails: boolean. If set to false, the details (tags, duration, name) will not be displayed when hovering the video
        * detailsPosition: string. The position where to display the details (tags, duration, name).
          Default is 'center'. Available values are 'center', 'right' or 'left'
        * expandOnHover: string. if set, this option allow to expand the size of the thumbnail when hovering.
          available values are any combination of a vertical expand ('top', 'middle', 'bottom') and
          an horizontal expand ('right', 'center', 'left') separated by a space. E.g: 'top left', 'middle center', etc...
        * contextInfoCb: function that takes a video object and returns the context information that
          should be displayed on the overlay if details are shown as a {text. color} object.
          Returns `{text: video.filesize_str, color:  colorMapping('size', video.fileSize)}` by default if not provided.
        */
        var self = this;
        options = options || {}
        self.displayNameOverlay = options.displayNameOverlay !== undefined ? options.displayNameOverlay : true;
        self.width = options.width || 3
        self.noLink = options.noLink !== undefined ? options.noLink : false;
        self.replace = options.replace !== undefined ? options.replace : false;
        self.append = options.append !== undefined ? options.append : false;
        self.showDetails = options.showDetails !== undefined ? options.showDetails : true;
        self.detailsPosition = options.detailsPosition !== undefined ? options.detailsPosition : 'center';
        self.expandOnHover = options.expandOnHover;
        self.selector = selector;
        self.snapshotCreated = false;
        self.mouseIn = false;
        self.firstEnter = true;
        self.overlayHeight = 0;
        self.initOverlayHeight = 0;
        self.contextInfoCb = options.contextInfoCb || function(video) {
            return {text: video.fileSize_str, color: colorMapping('size', video.fileSize)};
        };
        // will append the snapshot of the video to the given element
        var res = render(snapTemplate, {
            _id: video._id,
            width: self.width,
            thumbnail: video['thumbnail'],
            name: self.displayNameOverlay ? video['name'] : '',
            duration: video['duration_str'],
            resolution: video['width'] + ' x ' + video['height'],
            size: self.contextInfoCb(video).text,
            duration_color: colorMapping('duration', video['duration']),
            resolution_color: colorMapping('resolution', [video['width'], video['height']]),
            size_color: self.contextInfoCb(video).color,
            expandOnHover: self.expandOnHover ? 'expand-on-hover ' + self.expandOnHover : ''
        });

        self.$div = null;
        if (self.replace)
            self.$div = $(self.selector).html(res);
        else if (self.append)
            self.$div = $(res).appendTo(self.selector);
        else
            self.$div = $(res).prependTo(self.selector);
        if (self.noLink)
            $(self.selector + ' a.uk-thumbnail').attr('href', '#!').attr('target', '')

        // create all snapshots
        self.createSnapshots = function (callback) {
            if (self.snapshotCreated && self.$div.find('#vid-snap-' + video['_id'] + ' img').length > 1)
                return callback();
            self.snapshotCreated = true
            toPreload = [];
            // preload the first pictures
            for (var key in video.snapshots)
                if (key < video.thumbnail)
                    toPreload.push(video.snapshots[key]);
            preloadPictures(toPreload, function () {
                self.$div.find('#vid-snap-' + video['_id'] + ' .uk-overlay').addClass('no-transition');
                for (var i = 0; i < video['thumbnail'] ; i++) {
                    self.$div.find('#vid-snap-' + video['_id']).find('.thumbnail').before(
                        '<img src="' + video['snapshots'][i] + '" style="transform: translate(0, -' + video['thumbnail'] + '00%)">').css(
                        'transform', 'translate(0, -' + (i + 1) + '00%)');
                    if (i == video['nbSnapshots'] - 1) {
                        // commented as it introduced a bug when hovering a vidSnap quickly on page load
                        // self.overlayHeight = self.$div.find('#vid-snap-' + video['_id']).find('.uk-overlay').height();
                        // self.initOverlayHeight = self.overlayHeight;
                    }
                };
                for (var i = video['nbSnapshots'] - 1; i > video['thumbnail']; i--) {
                    self.$div.find('#vid-snap-' + video['_id']).find('.thumbnail').after(
                        '<img src="' + video['snapshots'][i] + '" style="transform: translate(0, -' + video['thumbnail'] + '00%)">');
                    if (i == video['nbSnapshots'] - 1) {
                        // commented as it introduced a bug when hovering a vidSnap quickly on page load
                        // self.overlayHeight = self.$div.find('#vid-snap-' + video['_id']).find('.uk-overlay').height()
                        // self.initOverlayHeight = self.overlayHeight;
                    }
                };
                callback();
            });
        }
        self.$div.find('#vid-snap-' + video['_id']).find('.uk-overlay').prepend(
            '<img class="thumbnail" src="' + video['snapshots'][video['thumbnail']] + '" style="transform: translate(0, 0)">');
        // adjust overlay height -- why ? overlay_height being initialized to 0, it just hide the picture when displayed on the
        // home page for some reason!
        // WHY NOT! Just for the reason you stated, overlay heigth HAS to be adjusted when the picture is added...
        self.overlayHeight = self.$div.find('#vid-snap-' + video['_id']).width() * 0.5604;
        self.initOverlayHeight = self.overlayHeight;

        self.$div.find('#vid-snap-' + video['_id']).find('.uk-overlay').css('height', self.overlayHeight + 'px');
        // FOR WHAT REASON ? This fixes the problem of the 'top: -30%' not being applied. This also fix the 'not out of flow' problem that moves the position of the snapshots
        self.$div.css('height', (self.overlayHeight - 3) + 'px');

        // manage hover
        self.next_timer = null
        self.creatingSnapshots = false;

        self.onMouseEnter = function () {
            // show details of the video if needed
            if (self.showDetails)
                tagsDisplayer.show(video, video.tags_list, self.detailsPosition);
            // create snapshots
            self.mouseIn = true;
            if (self.creatingSnapshots)
                return;
            self.creatingSnapshots = true;
            self.createSnapshots(function () {
                self.creatingSnapshots = false;

                if (!self.mouseIn)
                    return clearTimeout(self.next_timer);
                // manage picture scrolling
                var call_next = (idx) => function () {
                    self.$div.find('#vid-snap-' + video['_id'] + ' .uk-overlay').removeClass('no-transition');
                    if (idx !== undefined)
                        self.next(idx);
                    else
                        self.next();
                    self.next_timer = setTimeout(call_next(), 1000);
                };
                self.next_timer = setTimeout(self.firstEnter ? call_next(0) : call_next(), 1000);
                self.firstEnter = false;
                // change height (width is handled by the css)
                self.$div.find('.vid-snap').addClass('hover');
                fullPageOverlay.show();
                if (self.expandOnHover) {
                    self.overlayHeight = self.initOverlayHeight * 1.6;
                    // add '.hover' class manually rather than using :hover,
                    // we don't want hover state to be applied during the initialization
                    // because the width is controlled by this hover class and the
                    // height is set explicitely, and weird thing happens if
                    // `initOverlayHeight` is initialized while the :hover state is on
                    self.$div.find('.expand-on-hover').addClass('hover');
                    self.$div.find(
                        '.uk-overlay').css('height', self.overlayHeight + 'px');
                }
            });
        }
        self.onMouseLeave = function () {
            // hide details if shown
            if (self.showDetails)
                tagsDisplayer.hide()
            self.mouseIn = false;
            if (self.next_timer) {
                clearTimeout(self.next_timer);
                // self.next(video['thumbnail']);
                self.next_timer = null;
            }
            // change overlay height
            self.$div.find('.vid-snap').removeClass('hover');
            fullPageOverlay.hide();

            if (self.expandOnHover) {
                self.overlayHeight = self.initOverlayHeight;
                self.$div.find(
                    '.uk-overlay').css('height', self.overlayHeight + 'px');
            }
        }

        self.updateEvents = function () {
            if (self.$div.is(':hover'))
                self.onMouseEnter();
            self.$div.off().mouseenter(
                self.onMouseEnter).mouseleave(self.onMouseLeave);
        };
        self.updateEvents();

        self.notifyToggleFullscreen = function () {
            // when going full screen, the vidsnap has to hook up another HTML element
            self.$div = $(self.selector).find('#vid-snap-' + video['_id']);
            self.updateSize();
        }

        self.updateSize = function () {
            if (self.next_timer)
                clearTimeout(self.next_timer);
            var firstImg = self.$div.find('.uk-overlay').find('img')[0];
            if (!firstImg) {
                console.log ('Unable to update size of video ' + video['filename']);
                return;
            }
            self.overlayHeight = self.$div.find('.uk-overlay').find('img')[0].height;
            self.$div.find('.uk-overlay').css('height', self.overlayHeight + 'px');
            self.$div.parent().css('height', self.overlayHeight + 'px');
            self.updateEvents();
        }
        var img = $('#vid-snap-' + video['_id']).find('.uk-overlay').find('img')
        img.load(self.updateSize);
        // setTimeout(self.updateSize, 1000);
        self.thumbnail = video['thumbnail'];

        if (img.length == 0) {
            console.log("An error occured while creating snapshot for video: " + video['_id']);
        }

        self.next = function (idx) {
            if (idx !== 0)
                idx = idx % video['nbSnapshots'] || (self.thumbnail + 1) % video['nbSnapshots'];
            self.$div.find('#vid-snap-' + video['_id']).find('.uk-overlay').find('img').css(
                'transform', 'translate(0, -' + idx + '00%)');
            self.thumbnail = idx;
        }
    }
    window.VidSnap = VidSnap;
});