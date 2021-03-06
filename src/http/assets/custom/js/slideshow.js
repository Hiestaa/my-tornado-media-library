$(function () {
    var CURSOR_DISAPPEAR_TIMEOUT = 5000;

    function Controls(album, deleteModal, currentPic=0) {
        var self = this;
        self.album = album;
        self.$view = $('#controls');
        self.titleTemplate = '\
<span id="cover" class="uk-icon-picture-o" title="Define as cover picture" data-uk-tooltip="{pos: \'top-right\'}"></span>\
{{title}}\
<span id="counter">{{current}}/{{total}}</span>\
<span id="star" class="uk-icon-star" title="Mark this picture as favorite" data-uk-tooltip="{pos: \'top-left\'}"></span>\
'
        self.$view.find('#album-title').html(render(self.titleTemplate, {
            'title': self.album.name,
            'current': currentPic + 1,
            'total': self.album.picturesDetails.length,
        }));
        self.currentPicture = null;
        self.deleteModal = deleteModal;
        self.tagTemplate = '\
<div class="uk-button-group" data-tag-id="{{tagId}}" >\
    <button class="uk-button">{{name}}</button>\
    <select id="tag-value"></select>\
    <button class="uk-button uk-button-danger remove-tag"><i class="uk-icon-close"></i></button>\
</div>';

        self.isActive = false;
        self.formatters = {};
        // list of tag names
        self.tagNames = [];
        // associate to each tag name an object, which associate the tag id to the tag value
        self.tagValues = {};
        // associate to each tag id the corresponding name and value.
        self.tagIds = {};
        self.onStar = function () {
            console.log("Star clicked!");
            // save, in case it changes
            var pic = self.currentPicture;
            if (!self.album.picturesDetails[pic].starred){
                console.log("Starring picture" + pic + "...")
                $.ajax({
                    url: '/api/album/star',
                    type: 'post',
                    dataType: 'json',
                    data: {albumId: self.album['_id'], pictureIdx: pic},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while starring this picture, see logs for details.", {status:'danger'});
                    },
                    success: function () {
                        self.$view.find('#album-title #star').addClass('starred');
                        self.album.picturesDetails[pic].starred = true;
                    }
                });
            }
            else {
                console.log("UN-Starring picture" + pic + "...")
                $.ajax({
                    url: '/api/album/star',
                    type: 'post',
                    dataType: 'json',
                    data: {albumId: self.album['_id'], pictureIdx: pic, remove: true},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while unstarring this picture, see logs for details.", {status:'danger'});
                    },
                    success: function () {
                        self.$view.find('#album-title #star').removeClass('starred');
                        self.album.picturesDetails[pic].starred = false;
                    }
                });
                self.$view.find('#album-title #star').removeClass('starred');
            }
        }
        self.onSelectCover = function () {
            console.log("Cover clicked!");
            // save, in case it changes
            var pic = self.currentPicture;
            if (self.album.cover === pic)
                return;
            else {
                console.log("Selecting picture" + pic + " as cover...")
                $.ajax({
                    url: '/api/album/cover',
                    type: 'post',
                    dataType: 'json',
                    data: {albumId: self.album['_id'], pictureIdx: pic},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while selecting this picture as cover, see logs for details.", {status:'danger'});
                    },
                    success: function () {
                        self.$view.find('#album-title #cover').addClass('selected');
                        self.album.cover = pic;
                    }
                });
            }
        }
        self.updateCurrentPicture = function (currentPicture) {
            self.currentPicture = currentPicture;

            if (self.album.picturesDetails[self.currentPicture].starred)
                self.$view.find('#album-title #star').addClass('starred');
            else
                self.$view.find('#album-title #star').removeClass('starred');
            if (self.album.cover == self.currentPicture && !self.$view.find('#album-title #cover').hasClass('selected'))
                self.$view.find('#album-title #cover').addClass('selected');
            if (self.album.cover != self.currentPicture && self.$view.find('#album-title #cover').hasClass('selected'))
                self.$view.find('#album-title #cover').removeClass('selected');

            self.$view.find('#album-title #counter').html(
                (self.currentPicture + 1) + ' / ' + self.album.picturesDetails.length);

            // update the thumbnail displayed on the delete modal

            $('#delete-modal .uk-modal-caption img').attr(
                'src', self.album.picturesDetails[self.currentPicture].url);
        }
        self.updateCurrentPicture(currentPic);
        self.show = function () {
            self.$view.css('top', '10%');
            self.isActive = true;
        }

        self.hide = function () {
            self.$view.css('top', '');
            self.isActive = false;
        }

        self.events = function () {
            $('body').keydown(function (e) {
                switch (e.keyCode) {
                    case 38: // keyup
                    case 27: // escape
                        if (self.isActive)
                            self.hide();
                        else
                            self.show();
                        break;
                    case 83:  // s
                        if (self.isActive)
                            self.onStar()
                        else {
                            self.show();
                            setTimeout(function() {
                                self.onStar();
                                setTimeout(function () {
                                    if (self.isActive)
                                        self.hide();
                                }, 400);
                            }, 1000)
                        }
                        break;
                }
            });
            self.$view.find('#open-delete-modal').click(function () {
                self.deleteModal.show();
            })
            self.$view.find('#star').click(self.onStar);
            self.$view.find('#cover').click(self.onSelectCover);
        }
        self.events();

        self.onEditTag = function (name, newValue, oldId) {
            console.log("On edit tag name=" + name + ", newValue=" + newValue + ", oldId=" + oldId);
            if (self.album['_id'] == 'random' || self.album['_id'] == 'starred')
                return
            // value is an id if the item does already exist, otherwise it is the value of the new tag that should be
            // created
            if (newValue in self.tagValues[name]) {
                // the tag exist
                // remove the old one
                $.ajax({
                    url: '/api/album/tag',
                    type: 'post',
                    dataType: 'json',
                    data: {albumId: self.album['_id'], tagId: oldId, remove: true},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while deleting the tag, see logs for details.", {status:'danger'});
                    },
                    success: function () { }
                });
                // add the new one
                $.ajax({
                    url: '/api/album/tag',
                    type: 'post',
                    dataType: 'json',
                    data: {albumId: self.album['_id'], tagId: newValue},
                    error: function (e) {
                        console.error(e);
                        $.UIkit.notify("An error occured while adding the new tag, see logs for details.", {status:'danger'});

                    },
                    success: function () { }
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
                        self.tagValues[name][tag._id] = tag.value;
                        // now that the tag does exist, call onEditTag again.
                        // it will remove the old one and add the newly created tag.
                        self.onEditTag(tag.name, tag._id, oldId)
                    }
                })
            }
        }

        self.onDeleteTag = function () {
            if (self.album['_id'] == 'random' || self.album['_id'] == 'starred')
                return
            var $this = $(this);
            var tagId = $this.parent().attr('data-tag-id');
            $.ajax({
                url: '/api/album/tag',
                type: 'post',
                dataType: 'json',
                data: {albumId: self.album['_id'], tagId: tagId, remove: true},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured, see logs for details.", {status:'danger'});
                },
                success: function (result) {
                    $this.parent().remove();
                    var i = self.album.tags.indexOf(tagId);
                    self.album.tags.splice(i, 1);
                }
            })
        }

        self.renderTag = function (name, value, id) {
            if (self.album['_id'] == 'random' || self.album['_id'] == 'starred')
                return
            self.$view.find('#tags-list').append(render(self.tagTemplate, {
                name: name,
                // value: value,
                tagId: id
            }));
            self.$view.find('#tags-list .remove-tag').off().click(self.onDeleteTag);
            for (var tagId in self.tagValues[name]) {
                self.$view.find('#tags-list select#tag-value').last().append(
                    '<option value="' + tagId + '" ' + (tagId === id ? 'selected' : '') + '>' + self.tagValues[name][tagId] + '</option>');
            };
            self.$view.find('#tags-list select#tag-value').last().selectize({
                create: true,
                onItemAdd: function (newValue, $item) {
                    self.onEditTag(name, newValue, id);
                }
            });
        }

        self.onAddTag = function (type, tid, value) {
            if (self.album['_id'] == 'random' || self.album['_id'] == 'starred')
                return
            // 'type' should always be 'tag' here.
            // 'tid' is the index in the name array
            // 'value' is the mongodb id of the tag
            console.log ("Adding tag: ", tid, value);
            // send ajax query to notify server-side
            $.ajax({
                url: '/api/album/tag',
                type: 'post',
                dataType: 'json',
                data: {tagId: value, albumId: self.album['_id']},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while adding the tag, see logs for details.", {status:'danger'});
                },
                success: function (res) {
                    if (self.album.tags.indexOf(value) === -1) {
                        self.album.tags.push(value);
                        var formatter = self.formatters[tid] || function (v) { return v };
                        var name = self.tagNames[tid];
                        self.renderTag(name, formatter(value), value);
                    }
                    else {
                        $.UIkit.notify("This tag is already attached to this album!")
                    }
                }
            })

        }

        self.onRcvTags = function (tags) {
            // create properties manager, and add all tags available
            self.propertiesPanel = new Properties(
                [self.$view.find('#open-add-filter')],
                self.onAddTag, {
                    tagsOnly: true,
                    flipped: false
            });
            self.tagNames = [];
            self.tagValues = {};
            for (var i = 0; i < tags.length; i++) {
                var tag = tags[i]
                // populate tagNames array if this name does not exist yet
                if (self.tagNames.indexOf(tag.name) === -1) {
                    self.tagNames.push(tag.name)
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
                // render the tag if it belongs to the album
                if (self.album.tags.indexOf(tag._id) !== -1)
                    self.renderTag(tag.name, tag.value, tag._id);
            };
            for (var i = 0; i < self.tagNames.length; i++) {
                var name = self.tagNames[i];
                var options = self.tagValues[name];
                self.formatters[i] = self.propertiesPanel.addTagProperty(
                    'tag', i, name, options);
            };
        }
        self.loadTags = function () {
            if (self.album['_id'] == 'random' || self.album['_id'] == 'starred')
                return

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
    }

    function Slideshow(albumId, firstPic) {
        var self = this;

        self.albumId = albumId
        self.album = null;
        self.ukSlideshow = null;
        self.deleteModal = $.UIkit.modal("#delete-modal");
        self.maxSimulateousLoad = 7;  // does not work if mod 2 == 0
        self.currentSlide = 0;
        self.appearingSlide = 0;
        self.slideSetSize = 0;
        self.realCurrentSlide = firstPic;
        self.pause = true;

        self.controls = null;

        // set the proper position for the kenburns (zoom) focus of the coming image
        // also set the position of the face markers
        self.beforeShowNext = function (event, newIndex, direction) {
            // fix issue where direction is inverted (1 should be front)
            direction = -direction;
            // fix issue where going from 0 to X (reverse) actually returns a normal direction
            if (direction == 1 && newIndex == self.slideSetSize - 1 && self.currentSlide == 0)
                direction = -1;
            if (direction == -1 && newIndex == 0 && self.currentSlide == self.slideSetSize - 1)
                direction = 1;

            realCurrentSlide = self.realCurrentSlide + direction;
            if (realCurrentSlide < 0)
                realCurrentSlide += self.album.picturesDetails.length;
            if (realCurrentSlide >= self.album.picturesDetails.length)
                realCurrentSlide -= self.album.picturesDetails.length;

            self.appearingSlide = newIndex;

            var pic = self.album.picturesDetails[realCurrentSlide];

            var isWideScreen = $('body').width() / $('body').height() > pic.width / pic.height;

            var toCanvasX = function (x) {
                var sw = $('body').width();
                var pw = pic.width;
                var sh = $('body').height();
                var ph = pic.height;
                if (isWideScreen)  // only works if the screen is wider than the image
                    return sw / 2 - (pw / 2 - x) * sh / ph;
                else  // only works if the screen is narrower than the image
                    return sw / 2 - (pw / 2 - x) * sw / pw;
            }

            var toCanvasY = function (y) {
                var sw = $('body').width();
                var pw = pic.width;
                var sh = $('body').height();
                var ph = pic.height;
                if (isWideScreen)
                    return sh / 2 - (ph / 2 - y) * sh / ph;
                else
                    return sh / 2 - (ph / 2 - y) * sw / pw;
            }


            console.log("Faces for pic " + pic.filename, pic.faces);
            if (pic.faces && pic.faces.length > 0) {
                var face = pic.faces[0];
                var x = toCanvasX(face.boundaries[0].x);// + (face.boundaries[1].x - face.boundaries[0].x) / 2
                var y = toCanvasY(face.boundaries[0].y);
                var centerX = toCanvasX(face.boundaries[0].x + (face.boundaries[1].x - face.boundaries[0].x) / 2);
                var centerY = toCanvasY(face.boundaries[0].y);
                var bottomX = toCanvasX(face.boundaries[1].x);
                var bottomY = toCanvasY(face.boundaries[1].y);
                $('.face-frame')
                    .css('left', x)
                    .css('top', y)
                    .css('width', bottomX - x)
                    .css('height', bottomY - y)
                    .css('display', 'block');
                for (var i = 0; i < face.landmarks.length; i++) {
                    var l = face.landmarks[i];
                    $('#landsmark-marker-' + i)
                        .css('left', toCanvasX(l.x))
                        .css('top', toCanvasY(l.y))
                        .css('display', 'block');
                }
                self._setKenburnsFocus(centerX, centerY);
            }
            else {
                $('.face-frame').css('display', 'none');
                $('.landsmark-marker').css('display', 'none');
                self._setKenburnsFocus($('body').width() / 2, $('body').height() / 3);
            }
        }

        // cycle through the images of the albums assigned to each slide
        self.onShowNext = function (event, newIndex, direction) {
            // reinit state of the previous slide (which is still the current) if zoomed
            if ($('#slideshow ul li div:nth(' + self.currentSlide + ')').hasClass('zoomed')) {
                $('#slideshow ul li div:nth(' + self.currentSlide + ')').removeClass('zoomed')
                $('#slideshow ul li div:nth(' + self.currentSlide + ')').css('transform', 'scale(1)')
                        .css('transition', '')
                        .css('animation-name', '');
            }
            // fix issue where direction is inverted (1 should be front)
            direction = -direction;
            // fix issue where going from 0 to X (reverse) actually returns a normal direction
            if (direction == 1 && newIndex == self.slideSetSize - 1 && self.currentSlide == 0)
                direction = -1;
            if (direction == -1 && newIndex == 0 && self.currentSlide == self.slideSetSize - 1)
                direction = 1;
            // console.log("Call next: ", newIndex, direction);
            self.currentSlide = newIndex;
            self.realCurrentSlide += direction;
            if (self.realCurrentSlide < 0)
                self.realCurrentSlide += self.album.picturesDetails.length;
            if (self.realCurrentSlide >= self.album.picturesDetails.length)
                self.realCurrentSlide -= self.album.picturesDetails.length;
            self.controls.updateCurrentPicture(self.realCurrentSlide)
            // TODO: update the zoom pointer, to point to the center of one of the faces, if there is one

            // don't do anything more if the size of the slideset IS total number of slides.
            if (self.slideSetSize == self.album.picturesDetails.length)
                return;

            console.log("Displaying slide: ", $('#slideshow ul li div:nth(' + newIndex + ')').attr('data-slide-idx'));
            // edit slide nb currentSlide + slideSetSize / 2 * direction
            // set its background to slide realCurrentSlide + slideSetSize / 2 * direction
            var slideToEdit = self.currentSlide + Math.floor(self.slideSetSize / 2) * direction
            var newImgIdx = self.realCurrentSlide + Math.floor(self.slideSetSize / 2) * direction

            // if new image index is below 0, it should be the last of the album
            if (newImgIdx < 0)
                newImgIdx = self.album.picturesDetails + newImgIdx;
            if (newImgIdx >= self.album.picturesDetails.length)
                newImgIdx = newImgIdx - self.album.picturesDetails.length;

            if (slideToEdit < 0)
                slideToEdit = self.slideSetSize + slideToEdit;
            else if (slideToEdit >= self.slideSetSize)
                slideToEdit = slideToEdit - self.slideSetSize;

            if (!self.album.picturesDetails[newImgIdx].url) { debugger; return; }

            preloadPictures([self.album.picturesDetails[newImgIdx].url], function () {
                console.log("Slide " + slideToEdit + " replaced by " + newImgIdx);
                $('#slideshow ul li div:nth(' + slideToEdit + ')').attr('data-slide-idx', newImgIdx);
                $('#slideshow ul li img:nth(' + slideToEdit + ')').attr('src', self.album.picturesDetails[newImgIdx].url);
                $('#slideshow ul li div:nth(' + slideToEdit + ')').css(
                    'background-image', 'url("' + self.album.picturesDetails[newImgIdx].url + '")');
            });
        }

        self.loadPictures = function () {
            spinLoading();
            $.ajax({
                url: '/api/album/display',
                type: 'get',
                dataType: 'json',
                data: {albumId: self.albumId},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while loading album, see logs for details.", {status:'danger'});
                    spinLoading('stop');
                },
                success: function (album) {
                    self.album = album;
                    self.controls = new Controls(album, self.deleteModal);
                    if (self.realCurrentSlide < 0)
                        self.realCurrentSlide += self.album.picturesDetails.length;
                    if (self.realCurrentSlide >= self.album.picturesDetails.length)
                        self.realCurrentSlide = self.realCurrentSlide % self.album.picturesDetails.length;
                    self.controls.updateCurrentPicture(self.realCurrentSlide)
                    preloadPictures(album.picturesDetails.slice(self.realCurrentSlide, self.realCurrentSlide + 1).map(p => p.url), function () {
                        self.slideSetSize = Math.min(self.maxSimulateousLoad, album.picturesDetails.length);
                        // only the 30 first pics
                        for (var i = self.realCurrentSlide; i < self.realCurrentSlide + self.slideSetSize; i++) {
                            var pic = i;
                            if (pic > self.realCurrentSlide + Math.floor(self.slideSetSize / 2))
                                pic -= self.slideSetSize;
                            if (pic < 0)
                                pic += self.album.picturesDetails.length;
                            if (pic >= self.album.picturesDetails.length)
                                pic -= self.album.picturesDetails.length;
                            $('#slideshow ul').append(
                                '<li><img src="' + album.picturesDetails[pic].url + '"></li>')
                            };
                            self.ukSlideshow = $.UIkit.slideshow('#slideshow');
                        self.ukSlideshow.on('uk.slideshow.show', self.onShowNext);
                        self.ukSlideshow.on('uk.slideshow.beforeshow', self.beforeShowNext)
                        self.ukSlideshow.init();
                        self.beforeShowNext(null, 0, 0)
                        // set to pause or play according to autoplay option
                        self.pause = !self.ukSlideshow.options.autoplay;
                        // update interface
                        if (self.pause)
                            $('#pause').addClass('active');
                        else {
                            $('#play').addClass('active');
                            setTimeout(function () {
                                $('#play').removeClass('active');
                            }, 3000);
                        }
                        self.events();
                        self.controls.loadTags();
                        spinLoading('stop');
                    })
                }
            });
        }
        self.loadPictures();

        self.onDeletePicture = function () {
            self.deleteModal.hide();
            spinLoading();
            $.ajax({
                url: '/api/album/picture',
                type: 'delete',
                dataType: 'json',
                data: {albumId: self.albumId, pictureIdx: self.realCurrentSlide},
                error: function (e) {
                    spinLoading('stop');
                    console.error(e);
                    $.UIkit.notify("An error occured while deleting picture" +
                        self.album.pictures[self.realCurrentSlide] +
                        ", see logs for details.", {status:'danger'});
                },
                success: function () {
                    // not working because of the cache of the browser
                    // $('#slideshow ul').html('');
                    // new Slideshow(self.albumId, self.realCurrentSlide);
                    window.location.href = '/slideshow/albumId=' +
                        self.albumId + '/pictureIdx=' + self.realCurrentSlide;
                }
            });
        }

        self.onDeleteAlbum = function () {
            if (self.albumId == 'random' || self.albumId == 'starred')
                return
            self.deleteModal.hide();
            spinLoading();
            $.ajax({
                url: '/api/album/album',
                type: 'delete',
                dataType: 'json',
                data: {albumId: self.albumId},
                error: function (e) {
                    spinLoading('stop');
                    console.error(e);
                    $.UIkit.notify("An error occured while deleting album, see logs for details.", {status:'danger'});
                },
                success: function () {
                    // todo: change me to the list of albums
                    window.location.href = '/albums';
                }
            });
        }

        self.togglePause = function () {
            if (self.pause) {
                self.ukSlideshow.start();
                self.pause = false;
            }
            else {
                self.ukSlideshow.stop()
                self.pause = true
            }
            $('#pause').toggleClass('active');
            if (!self.pause) {
                $('#play').toggleClass('active');
                setTimeout(function () {
                   $('#play').removeClass('active');
                }, 3000);
            }
            else
                $('#play').removeClass('active');
        }

        self.mousePos = {x: $('body').width() / 2, y: $('body').height() / 2};
        self.onKeyDown = function (e) {
            if (e.altKey || e.shiftKey || e.ctrlKey) {
                self.mousePos = self.currentMousePos;
            }
            switch (e.keyCode) {
                case 37:  // left
                    self.ukSlideshow.previous()
                    break;
                case 39: // right
                    self.ukSlideshow.next()
                    break;
                case 32:
                    self.togglePause()
                    break;
                case 27: // escape
                    break;  // open control panel? check that it does not kill the zoom....
                case 46: // delete
                    if (!self.album)
                        return
                    self.deleteModal.show();
                    break;
                case 13: // enter
                    if (self.deleteModal.isActive())
                        self.onDeletePicture();
                    break;
                case 107: // +
                    e.preventDefault();
                    self.performZoom(scaleFactor);
                    break
                case 109: // -
                    e.preventDefault();
                    self.performZoom(1.0 / scaleFactor);
                    break;
            };
        }

        self.$appearingSlide = function () {
            return $('#slideshow ul li:nth-child(' + (self.appearingSlide + 1) + ') div');
        }

        self._getKenburnsFocus =  function () {
            var currentTO = self.$appearingSlide()
                .css('transform-origin') || (self.mousePos.x + 'px ' + self.mousePos.y + 'px');
            currentTO = currentTO.split(' ');
            return {
                x:  parseInt(currentTO[0].slice(0, -2)),
                y:  parseInt(currentTO[1].slice(0, -2))
            }
        }

        self._setKenburnsFocus = function (x, y) {
            $('.focus-marker').css('left', x);
            $('.focus-marker').css('top', y);
            $('.focus-marker').css('display', 'block');
            self.$appearingSlide().css('transform-origin', x + 'px ' + y + 'px');
        }

        self.currentMousePos = {x: $('body').width() / 2, y: $('body').height() / 2};
        self.hideCursorTimeout = null;
        self.onMouseMove = function (e) {
            self.currentMousePos = {x: e.pageX, y: e.pageY};
            if ((!e.altKey && !e.shiftKey && !e.ctrlKey) || self.deleteModal.isActive() || self.controls.isActive) {
                $('#slideshow ul').css('cursor', 'default');
                clearTimeout(self.hideCursorTimeout);
                self.hideCursorTimeout = setTimeout(function () {
                    $('#slideshow ul').css('cursor', 'none');
                }, CURSOR_DISAPPEAR_TIMEOUT);
                return;
            }
            else {
                $('#slideshow ul').css('cursor', 'none');
                clearTimeout(self.hideCursorTimeout);
            }
            // legacy
            var scaleFactor = self.$appearingSlide().css('transform');
            scaleFactor = parseFloat(scaleFactor.substring(7, scaleFactor.indexOf(',')));
            // var w = $(this).width();
            // var h = $(this).height();
            // var relX = (e.pageX - w / 2) * 3; // * scale factor ?
            // var relY = (e.pageY - h/2) * 3; // * scale factor ?
            currentTO = self._getKenburnsFocus();
            var deltaX = self.currentMousePos.x - self.mousePos.x;
            var deltaY = self.currentMousePos.y - self.mousePos.y;
            self.mousePos = self.currentMousePos;
            var relX = currentTO.x + deltaX / (scaleFactor / 10);
            var relY = currentTO.y + deltaY / (scaleFactor / 10);
            self._setKenburnsFocus(relX, relY);
        };

        var scaleFactor = 1.3;
        self.onMouseZoom = function (event) {
            if (event.originalEvent.wheelDelta !== undefined) {
                if (event.originalEvent.wheelDelta <= 0)
                    self.performZoom(1.0 / scaleFactor);
                else
                    self.performZoom(scaleFactor);
            }
            else {
                if (event.originalEvent.detail >= 0)
                    self.performZoom(1.0 / scaleFactor);
                else
                    self.performZoom(scaleFactor);
            }
        };

        self.performZoom = function (factor) {
            $this = self.$appearingSlide();
            var cur_transform = $this.css('transform');
            if (!$this.hasClass('zoomed')) {
                $this.addClass('zoomed')
                $this.css('transform', cur_transform)
                    .css('transition', '-webkit-transform 200ms ease')
                    .css('transition', 'transform 200ms ease')
                    .css('animation-name', 'none');
            }
            var scale = cur_transform.substring(7, cur_transform.indexOf(','));
            scale = parseFloat(scale);
            scale *= factor;
            if (scale <= 1)
                scale = 1;
            $this.css('transform', 'scale(' + scale + ')');
            if (!self.pause)
                self.togglePause()

        }

        self.lastTrUpdate = null;
        self.events = function () {
            $('#delete-picture').off().click(self.onDeletePicture);
            $('#delete-album').off().click(self.onDeleteAlbum);
            var mouse_timer = null;
            $('body').mousedown(function (e) {
                switch (e.which) {
                    case 2:
                        // if timer is not set, this means we can safely call next.
                        // otherwise, this means we are still waiting for another quick
                        // double-click and we want to display the previous one
                        if (!mouse_timer) {
                            mouse_timer = setTimeout(function () {
                                mouse_timer = null;
                                self.ukSlideshow.next();
                            }, 250);
                        }
                        else {
                            clearTimeout(mouse_timer);
                            mouse_timer = null;
                            self.ukSlideshow.previous();
                        }
                }
            });
            $('body').mousemove(self.onMouseMove);
            $('body').keydown(self.onKeyDown);
            $('#slideshow ul li div').off().bind('mousewheel DOMMouseScroll', self.onMouseZoom);
        }
    };
    window.Slideshow = Slideshow;
});