$(function () {
    function SessionManager(onReload) {
        var self = this;

        self.session = qs.parse(location.search);

        self.update = function (key, value) {
            if (value === self.session[key]) { return; }

            self.session[key] = value;

            history.pushState(
                self.session,
                document.title,
                document.location.href.split('?')[0] + '?' + qs.stringify(self.session));
        }

        self.get = function(key) {
            return self.session[key];
        }

        self.deleteFilter = function(type, uid) {
            const filters = self.getFilters();
            if (!filters[type]) { filters[type] = {}; }
            if (filters[type][uid]) { delete filters[type][uid]; }
            if (Object.keys(filters[type]).length === 0) { delete filters[type]; }
            self.update('filters', JSON.stringify(filters));
        }

        self.addFilter = function(type, uid, name, value) {
            const filters = self.getFilters();
            if (!filters[type]) { filters[type] = {}; };
            filters[type][uid] = {'type': type, 'name': name, 'value': value};
            self.update('filters', JSON.stringify(filters));
        }

        self.negateFilter = function(type, uid) {
            const filters = self.getFilters();
            filters[type][uid].negated = !filters[type][uid].negated;
            self.update('filters', JSON.stringify(filters));
        }

        self.getFilters = function () {
            return JSON.parse(self.get('filters') || '{}');
        }

        window.onpopstate = function (event) {
            self.session = qs.parse(location.search);
            onReload(self.session);
        }
    }

    function VidList() {
        var self = this;
        self.isFullScreen = false;
        self.vidSnaps = [];
        self.lastLoadResult = null;
        self.loadingVids = false;
        self.filter = null;
        // for each video property, associate the id to the real displayed name
        self.vpId2display = {
            name: 'Video Title',
            maxDuration: 'Max. Length',
            minDuration: 'Min. Length',
            resolution: 'Min. Resolution',
            minFavorite: 'Min. Favorite',
            maxFavorite: 'Max. Favorite',
            toWatch: 'To Watch',
            minSeen: 'Min. Times Watched',
            maxSeen: 'Max. Times Watched'
        }
        // for each video property, associate the id to the corresponding video document field
        self.vpId2name = {
            name: 'name',
            maxDuration: 'duration',
            minDuration: 'duration',
            resolution: 'resolution',
            minFavorite: 'favorite',
            maxFavorite: 'favorite',
            toWatch: 'toWatch',
            minSeen: 'seen',
            maxSeen: 'seen'
        }
        // for each property, associate the id to the formatter that transform
        // the value into the displayed name
        self.formatters = {}
        self.defaultCombineType = $('#filters-list .filters-combine.uk-active').data('combine');
        self.defaultSort = [
            $('#filters-list #sorting').val(),
            parseInt($('#filters-list .sorting-order.uk-active').data('order'), 10)
        ];
        self.criteria = {
            video: {},
            tag: {},
            type: self.defaultCombineType,
            sort: self.defaultSort
        }
        self.tagNames = []
        self.tagValues = {}
        self.uid = 0

        // get context information for the video, that is the data to display depending on
        // the selected sort field
        self.getContextInfo = function(video) {
            var sort = self.criteria.sort[0];
            switch (sort) {
                case 'duration':
                    return {text: video.duration_str, color: colorMapping('duration', video['duration'])};
                    break;
                case 'fileSize':
                    return {text: video.fileSize_str,
                            color: colorMapping('size', video.fileSize)};
                    break;
                case 'fps':
                    return {text: video.fps, color: colorMapping('fps', video.fps)};
                    break;
                case 'faceRatio':
                case 'faceTime':
                case 'faceTimeProp':
                case 'popularity':
                    return {text: (video[sort] || '').toString().slice(0, 8),
                            color: '#C5CC00'};
                            break;
                case 'lastDisplay':
                case 'lastSeen':
                case 'creation':
                case 'lastTagged':
                case 'lastFavorite':
                    return {text: video[sort + '_str'], color: '#C5CC00'};
                    break
                case 'display':
                case 'seen':
                case 'favorite':
                case 'nbTags':
                default:
                    return {text: video[sort], color: '#C5CC00'};
                    break;

            }
        }

        self.toggleFullScreen = function () {
            if (!self.isFullScreen) {
                spinLoading();
                self.isFullScreen = true;
                $('#full-screen-container').html($('#videos-container').parent().html()).css('display', 'block');
                $('#full-screen-container').append('<i class="uk-icon-compress full-screen" id="full-screen" \
data-uk-tooltip="{pos:\'left\'}" title="Quit Full-Screen" style="top: 15px; z-index: 15"></i>')
                $('#full-screen-container #full-screen').click(self.toggleFullScreen);
                $('#std-container').css('display', 'none');
                self.updatePagination(self.lastLoadResult['page'], self.lastLoadResult['count']);
                $.UIkit.notify("Press ESC to quit full-screen mode.", {status:'info'});
                setTimeout(function () {
                    for (var i = 0; i < self.vidSnaps.length; i++) {
                        self.vidSnaps[i].notifyToggleFullscreen();
                        self.vidSnaps[i].updateSize();
                    };
                    spinLoading('stop');
                }, 200);
            }
            else {
                self.isFullScreen = false;
                $('#std-container').css('display', 'block');
                $('#full-screen-container').html('').css('display', 'none');
                self.loadVids(self.lastLoadResult['page'])
            }
        };

        self.initialContainerHTML = $('#videos-container').html();
        self.resetContainer = function () {
            $('#videos-container').html(self.initialContainerHTML);
            self.vidSnaps = self.vidSnaps.splice(0, 0);
        }
        self.loadVids = function (page) {
            if (self.loadingVids)
                return;
            self.loadingVids = true;
            // update saved page
            spinLoading();
            var crit = {
                video: [],
                tags: [],
                type: self.criteria.type,
                sort: [self.criteria.sort]
            };
            for (var vf in self.criteria.video)
                crit.video.push(self.criteria.video[vf])
            for (var tf in self.criteria.tag)
                crit.tags.push(self.criteria.tag[tf])
            $.ajax({
                'type': 'get',
                'dataType': 'json',
                'url': '/api/video/filter',
                'data': {'page': page || 0, criteria: JSON.stringify(crit)},
                success: function (results) {
                    self.lastLoadResult = results;
                    var videos = results.videos;
                    // preload all thumbnails
                    var thumbnails = [];
                    for (var i = 0; i < videos.length; i++) {
                        if (videos[i].thumbnail === null || videos[i].nbSnapshots == 0 || videos[i].snapshots.length == 0) {
                            console.error(videos[i]);
                            // todo: replace by an error (like a cross) image
                            videos[i].snapshots = ['/assets/custom/img/question-mark.png'];
                            videos[i].thumbnail = 0;
                            $.UIkit.notify("Unable to get any thumbnail for video: " + videos[i].name + " (id=" + videos[i]._id + ")", {status:'danger'});
                        }
                        thumbnails.push(videos[i].snapshots[videos[i].thumbnail]);
                    };
                    preloadPictures(thumbnails, function () {
                        self.resetContainer();
                        self.updatePagination(results.page, results.count);
                        for (var i = videos.length - 1; i >= 0 ; i--) {
                            var expand = ['bottom', 'right'];
                            if (i >= 6)
                                expand[0] = 'top';
                            else if (i >= 3)
                                expand[0] = 'middle';
                            if (i % 3 == 2)
                                expand[1] = 'left';
                            if (i % 3 == 1)
                                expand[1] = 'center';
                            self.vidSnaps.push(
                                new VidSnap('#videos-container', videos[i], {
                                    detailsPosition: i % 3 == 0 ? 'right' : i % 3 == 1 ? 'left' : 'left',
                                    expandOnHover: expand.join(' '),
                                    contextInfoCb: self.getContextInfo
                                }));
                        };
                        setTimeout(function () {
                            for (var i = 0; i < self.vidSnaps.length; i++) {
                                self.vidSnaps[i].updateSize()
                            };
                        }, 200);
                        self.loadingVids = false;
                        spinLoading('stop');
                    });

                },
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                    spinLoading('stop');
                }
            });
        };

        self.reloadSession = function () {
            self.filter.clear();
            self.loadSortingOrder(self.session.get('sort') || self.defaultSort);
            self.loadCombineType(self.session.get('combine') || self.defaultCombineType);
            self.filter.loadExistingFilters(self.session.getFilters(), () => {
                self.loadCurrentPage(self.session.get('page') || '0');
            });
        }

        self.loadSortingOrder = function (sort) {
            var field = sort[0];
            var order = sort[1];
            self.criteria.sort = [field, order];
            // set the toggle
            $('.sorting-order-container button').each(function () {
                if ($(this).attr('data-order') == order && !$(this).hasClass('uk-active'))
                    $(this).addClass('uk-active');
                if ($(this).attr('data-order') != order && $(this).hasClass('uk-active'))
                    $(this).removeClass('uk-active');
            });
            // set the sorting order
            self.ignoreSortEvent = true;
            $('#sorting')[0].selectize.addItem(field, true);
            self.ignoreSortEvent = false;
        };

        self.loadCombineType = function (type) {
            self.criteria.type = type;
            $('.filters-combine-container button').each(function () {
                if ($(this).attr('data-combine') == type && !$(this).hasClass('uk-active'))
                    $(this).addClass('uk-active');
                if ($(this).attr('data-combine') != type && $(this).hasClass('uk-active'))
                    $(this).removeClass('uk-active');
            });
        }

        self.loadCurrentPage = function (page) {
            self.loadVids(parseInt(page));
        };

        self.updatePagination = function (page, count) {
            $.UIkit.pagination($('.uk-pagination').first(), {
                items: count,
                itemsOnPage: 9,
                currentPage: page + 1,
                onSelectPage: self.changePage
            });
        }

        self.changePage = function (page) {
            self.session.update('page', page);
            self.loadVids(page);
        }

        self.events = function () {
            $('#full-screen').off().click(self.toggleFullScreen);
            $('body').off().keydown(function (event) {
                switch (event.keyCode) {
                    case 27: // escape
                        self.toggleFullScreen();
                        break;
                    case 37:  // left
                        if (self.lastLoadResult['page'] > 0) {
                            self.changePage(self.lastLoadResult['page'] - 1);
                        }
                        break;
                    case 39: // right
                        if (self.lastLoadResult['page'] < Math.floor(self.lastLoadResult['count'] / 9))
                            self.changePage(self.lastLoadResult['page'] + 1);
                        break;
                }
            });
            $('.filters-combine-container .filters-combine').off().click(function (){
                self.criteria.type = $(this).attr('data-combine')
                self.session.update('combine', self.criteria.type);
                self.loadVids();
            });
            $('#sorting').selectize({
                onItemAdd: function (value) {
                    // stupid selectize doens't let us differenciate user actions from calls to `addItems`...
                    if (self.ignoreSortEvent) { return; }
                    self.criteria.sort = [value, self.criteria.sort[1]];
                    self.session.update('sort', self.criteria.sort);
                    self.loadVids();
                }
            });
            $('.sorting-order-container .sorting-order').off().click(function () {
                self.criteria.sort = [self.criteria.sort[0], parseInt($(this).attr('data-order'), 10)];
                self.session.update('sort', self.criteria.sort);
                self.loadVids();
            })
        }

        self.onReload = function () {
            self.reloadSession();
        }

        self.initialize = function () {
            self.filter = new Filter(
                $('#filters-list'),
                $('#open-add-filter'), {
                    onCriteriaUpdated: (criteria, options) => {
                        // reload
                        self.criteria = Object.assign({}, self.criteria, criteria);
                        if (!options.do_not_reload)
                            self.loadVids();
                    },
                    onFilterAdded: (type, uid, fid, value, options) => {
                        // notify session
                        if (!options.do_not_save)
                            self.session.addFilter(type, uid, fid, value);
                    },
                    onFilterRemoved: (type, filterUid) => {
                        self.session.deleteFilter(type, filterUid);
                        self.loadVids();
                    },
                    onFilterNegated: (type, uid, criteria) => {
                        self.criteria = Object.assign({}, self.criteria, criteria);
                        self.session.negateFilter(type, uid);
                        self.loadVids();
                    }
                }
            );

            self.session = new SessionManager(self.onReload);

            self.events();
            self.reloadSession();

        }

        self.initialize();
    }
    vidList = new VidList();
})