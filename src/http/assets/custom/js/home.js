function findKeyframesRule(rule) {
  var ss = document.styleSheets;
  for (var i = 0; i < ss.length; ++i) {
    for (var j = 0; j < ss[i].cssRules.length; ++j) {
      if (ss[i].cssRules[j].type == window.CSSRule.WEBKIT_KEYFRAMES_RULE &&
      ss[i].cssRules[j].name == rule) {
        return ss[i].cssRules[j]; }
    }
  }
  return null;
}

$(function () {

    function Home() {
        var self = this;

        self.vids = []

        self.loadVidsTime = 5;
        self.nbMinVids = 5;
        self.nbMaxVids = 15;

        self.iter = 0;

        self.onAnimationEnd = function () {
            self.iter += 1
            var keyframes = findKeyframesRule('scrolling');
            keyframes.deleteRule('0%');
            keyframes.deleteRule('100%');
            console.log("Translate from " + (self.iter * 500) + 'px to ' + ((self.iter + 1) * 500) + 'px')
            keyframes.appendRule('0% { transform: translate(0, -' + (self.iter * 500) + 'px); }');
            keyframes.appendRule('100% { transform: translate(0, -' + ((self.iter + 1) * 500) + 'px); }');

            // restart the animation
            var vidContainerInner = document.getElementById('vid-container-inner');
            vidContainerInner.classList.remove('run-animation');
            vidContainerInner.offsetWidth = vidContainerInner.offsetWidth;
            vidContainerInner.classList.add('run-animation');
        }

        function prefixedEvent(element, type, callback) {
            var pfx = ["webkit", "moz", "MS", "o", ""];
            for (var p = 0; p < pfx.length; p++) {
                if (!pfx[p]) type = type.toLowerCase();
                element.addEventListener(pfx[p]+type, callback, false);
            }
        }

        prefixedEvent(
            document.getElementById('vid-container-inner'),
            'AnimationEnd',
            self.onAnimationEnd);

        // called every X seconds, this function will set the visibility to hidden for the vids
        // that are not visible anymore, and load more videos to keep having new videos comming
        self.updateScrollingVids = function () {
            var nb_hidden = 0;
            $('#vid-container .vid-snap-parent').each(function (index) {
                // if not visible anymore, replace by something that takes less memory (no images) but that have the same height
                if ($(this).position().top < -300) {
                    self.vids.splice(index, 1); // is this fixing the memory issue>
                    // this uses less memory
                    $(this).replaceWith('<div class="vid-snap-replacement" style="height: ' + $(this).height() + 'px;"></div>');
                    // $(this).css('visibility', 'hidden');
                    nb_hidden += 1;
                }
            });
            console.log(nb_hidden + " vidSnaps have been removed.");
            setTimeout(function () {
                // there is no need to have more than 20 vids waiting to be displayed
                if ($('#vid-container .vid-snap-parent').length < self.nbMaxVids)
                    return self.loadVids();
                // if loadVids is not called, updateScrollingVids will not be called either.
                setTimeout(self.updateScrollingVids, self.loadVidsTime * 1000);
            // if not enough videos are loaded, quickly load more until it reaches the configured threshold
            }, $('#vid-container .vid-snap-parent').length > self.nbMinVids ? self.loadVidsTime * 1000 : 100);
        }

        self.onRcvVids = function (vids) {
            console.log(vids);
            var toPreload = [];
            for (var i = 0; i < vids.length; i++) {
                toPreload.push(vids[i].snapshots[vids[i].thumbnail]);
            };
            preloadPictures(toPreload, function () {
                for (var i = 0; i < vids.length; i++) {
                    self.vids.push(new VidSnap('#vid-container #vid-container-inner', vids[i], {
                        width: 1,
                        append: true
                        // expandOnHover: i == vids.length - 1 ? 'bottom left' : 'top left'
                    }));
                };
                // spinLoading('stop');
                self.updateScrollingVids();
            });
        }

        self.loadVids = function () {
            $.ajax({
                url: '/api/home/display',
                type: 'get',
                data: {
                    nb_tags: 2,
                    nb_vids: 3
                },
                dataType: 'json',
                success: self.onRcvVids,
                error: function (e) {
                    $.UIkit.notify("An error occured while loading videos, see logs for details.", {status:'danger'});
                    // spinLoading('stop');
                    console.error(e);
                }
            })
        }

        self.slideshow = null;
        self.loadAlbum = function () {
            $.ajax({
                url: '/api/album/display',
                type: 'get',
                dataType: 'json',
                data: {albumId: 'starred'},
                error: function (e) {
                    console.error(e);
                    $.UIkit.notify("An error occured while loading album, see logs for details.", {status:'danger'});
                    spinLoading('stop');
                },
                success: function (album) {
                    preloadPictures(album.picturesURL.slice(1, 4), function () {
                        for (var i = 1; i < Math.min(album.picturesURL.length, 20); i++) {
                            $('#pic-container ul').append(
                                '<li><img src="' + album.picturesURL[i] + '"></li>');
                        };
                        self.slideshow = $.UIkit.slideshow('#pic-container', {autoplay: true, animation: 'random-fx', duration: 2000});
                        spinLoading('stop');
                        // self.slideshow.init();
                    });
                }
            });
        }
        spinLoading();
        self.loadVids();
        self.loadAlbum();
    }
    home = new Home();
})